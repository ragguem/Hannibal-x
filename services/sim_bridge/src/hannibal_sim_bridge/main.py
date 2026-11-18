"""Lancement : `uvicorn --factory hannibal_sim_bridge.main:create_app`."""

import time
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Response, status

from hannibal_contracts import sim_bridge as contract
from hannibal_platform.app import create_service_app
from hannibal_platform.errors import Conflict, DependencyUnavailable, NotFound
from hannibal_platform.internal_auth import require_internal_token
from hannibal_sim_bridge import __version__
from hannibal_sim_bridge.registry import ManeuverConflict, ManeuverRegistry, RecordedManeuver
from hannibal_sim_bridge.settings import SimBridgeSettings, WorldKind
from hannibal_sim_bridge.world import KinematicWorld, World, WorldUnavailable

WORLD_DEPENDENCY = "lotusim"


def build_world(settings: SimBridgeSettings) -> World:
    if settings.world is WorldKind.KINEMATIC:
        return KinematicWorld(settings.origin_lat_lon, time.monotonic)
    from hannibal_sim_bridge.ros import RosWorld

    return RosWorld(settings.lotusim_world, settings.vessel_model, settings.command_timeout_s)


def _record_view(record: RecordedManeuver) -> contract.ManeuverRecord:
    return contract.ManeuverRecord(
        command_id=record.command_id, maneuver=record.maneuver, recorded_at=record.recorded_at
    )


def sim_bridge_router(world: World, registry: ManeuverRegistry, settings: SimBridgeSettings) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_internal_token(settings))])

    async def guarded[T](call: Awaitable[T]) -> T:
        try:
            return await call
        except WorldUnavailable as error:
            raise DependencyUnavailable(WORLD_DEPENDENCY, str(error)) from error

    @router.post("/ships", status_code=status.HTTP_204_NO_CONTENT)
    async def spawn_fleet(body: contract.SpawnFleet) -> Response:
        ships = {ship.name: (ship.east_m, ship.north_m, ship.heading_deg) for ship in body.ships}
        await guarded(world.spawn(ships))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.delete("/ships", status_code=status.HTTP_204_NO_CONTENT)
    async def clear_fleet() -> Response:
        await guarded(world.clear())
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.put("/waypoints", status_code=status.HTTP_204_NO_CONTENT)
    async def steer_fleet(body: contract.SteerFleet) -> Response:
        waypoints = {name: (point.lat, point.lon) for name, point in body.waypoints.items()}
        await guarded(world.steer(waypoints))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/state")
    async def read_state() -> contract.WorldState:
        states = await guarded(world.states())
        return contract.WorldState(
            ships={name: contract.ShipState.model_validate(state) for name, state in states.items()}
        )

    @router.post("/maneuvers", status_code=status.HTTP_201_CREATED)
    async def record_maneuver(body: contract.RecordManeuver, response: Response) -> contract.ManeuverRecord:
        try:
            record, created = registry.record(body.command_id, body.maneuver)
        except ManeuverConflict as error:
            raise Conflict("identifiant déjà enregistré avec une autre manœuvre") from error
        if not created:
            response.status_code = status.HTTP_200_OK
        return _record_view(record)

    @router.get("/maneuvers/{command_id}")
    async def read_maneuver(command_id: str) -> contract.ManeuverRecord:
        record = registry.get(command_id)
        if record is None:
            raise NotFound("manœuvre inconnue")
        return _record_view(record)

    return router


def create_app(
    settings: SimBridgeSettings | None = None,
    world: World | None = None,
    registry: ManeuverRegistry | None = None,
) -> FastAPI:
    settings = settings or SimBridgeSettings()
    world = world or build_world(settings)
    registry = registry or ManeuverRegistry(settings.registry_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await world.start()
        yield
        await world.stop()

    app = create_service_app(
        settings,
        version=__version__,
        title="Hannibal X sim-bridge",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_local else None,
        redoc_url=None,
    )
    app.include_router(sim_bridge_router(world, registry, settings))
    return app
