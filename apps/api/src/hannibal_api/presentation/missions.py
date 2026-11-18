"""Routes de mission (§ 12). Traduit l'état du moteur (clés françaises héritées) vers les contrats."""

from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from hannibal_api.application.missions import MissionError, MissionRun, Missions, NotFound
from hannibal_contracts import missions as contracts
from hannibal_contracts.common import ErrorBody
from hannibal_platform.errors import error_body
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.logging import get_logger
from hannibal_platform.settings import BaseServiceSettings

log = get_logger(__name__)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorBody}
    for status in (
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        HTTPStatus.SERVICE_UNAVAILABLE,
    )
}

HELM_FIELD_TO_ENGINE_KEY = {
    "rudder": "rudder",
    "course_deg": "cap",
    "course_change_deg": "dcap",
    "speed_kn": "kn",
    "speed_change_kn": "dkn",
}


async def on_mission_error(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, MissionError):
        raise error
    log.warning("request_refused", code=error.code, **error.context)
    status = HTTPStatus.NOT_FOUND if isinstance(error, NotFound) else HTTPStatus.CONFLICT
    return JSONResponse(error_body(error.code, error.message), status_code=status)


def to_scenario_summary(scenario: dict[str, Any]) -> contracts.ScenarioSummary:
    guide = next(ship["nom"] for ship in scenario["flotte"] if ship["role"] == "guide")
    return contracts.ScenarioSummary(
        id=scenario["id"],
        title=scenario["titre"],
        level=scenario.get("niveau"),
        duration_s=int(scenario["duree_s"]),
        summary=scenario.get("resume"),
        briefing=scenario.get("briefing"),
        playable_ships=[guide] + [ship["nom"] for ship in scenario["flotte"] if ship["nom"] != guide],
        guide_ship=guide,
    )


def to_objective(check: dict[str, Any]) -> contracts.Objective:
    return contracts.Objective(
        description=check["texte"],
        deadline_s=check.get("avant_t"),
        achieved=bool(check["ok"]),
        achieved_at_s=check.get("t"),
    )


def to_debrief(debrief: dict[str, Any] | None) -> contracts.Debrief | None:
    if debrief is None:
        return None
    return contracts.Debrief(
        objectives=[to_objective(check) for check in debrief["checks"]],
        score=debrief["score"],
        objectives_total=debrief["total"],
        closest_ships_distance_m=debrief["min_ship_m"],
        closest_cpa_nm_by_contact=debrief["min_cpa"],
        classification_by_contact={
            contact_id: contracts.ClassificationResult(chosen=result["choisie"], actual=result["reelle"])
            for contact_id, result in debrief["classes"].items()
        },
    )


def to_ship(ship: dict[str, Any]) -> contracts.Ship:
    return contracts.Ship(
        name=ship["name"],
        role=ship["role"],
        east_m=ship["x"],
        north_m=ship["y"],
        heading_deg=ship["hdg"],
        speed_mps=ship["sog"],
        status_for_player=ship["etat"],
        status_for_fleet=ship["etat_c"],
    )


def to_contact(contact: dict[str, Any]) -> contracts.Contact:
    return contracts.Contact(
        id=contact["id"],
        category=contact["type"],
        east_m=contact["x"],
        north_m=contact["y"],
        course_deg=contact["cap"],
        speed_kn=contact["vit"],
        classification=contact["cls"],
        behaviour=contact["etat"],
        range_nm=contact["range_nm"],
        bearing_deg=contact["brg"],
        cpa_nm=contact["cpa_nm"],
        tcpa_min=contact["tcpa_min"],
    )


def to_radio_message(message: dict[str, Any]) -> contracts.RadioMessage:
    return contracts.RadioMessage(
        id=message["id"],
        sent_at_s=message["t"],
        sender=message["from"],
        recipient=message["to"],
        text_en=message["en"],
        text_fr=message["fr"],
        kind=message["kind"],
    )


def to_station(station: dict[str, Any] | None) -> contracts.Station | None:
    if station is None:
        return None
    return contracts.Station(east_m=station["x"], north_m=station["y"], offset_m=station["err"])


def to_helm(helm: dict[str, Any]) -> contracts.Helm:
    return contracts.Helm(
        course_deg=round(helm["cap"], 1), speed_kn=round(helm["kn"], 1), rudder=helm["rudder"]
    )


def to_mission(run: MissionRun) -> contracts.Mission:
    state = run.engine.state()
    return contracts.Mission(
        id=run.id,
        scenario_id=run.scenario_id,
        title=state["titre"],
        player_ship=state["player"],
        guide_ship=state["guide"],
        phase=contracts.MissionPhase.ENDED
        if state["ended"] or run.stopped
        else contracts.MissionPhase.RUNNING,
        elapsed_s=state["t"],
        duration_s=state["duree"],
        formation=state["form"],
        guide_course_deg=state["gcap"],
        guide_speed_kn=state["gspeed_kn"],
        ships=[to_ship(ship) for ship in state["ships"]],
        contacts=[to_contact(contact) for contact in state["contacts"]],
        radio_messages=[to_radio_message(message) for message in state["msgs"]],
        planned_orders=[
            contracts.PlannedOrder(planned_at_s=order["t"], text_en=order["en"], text_fr=order["fr"])
            for order in state["plan"]
        ],
        pending_orders=[order["fr"] for order in state["pending"]],
        objectives=[to_objective(check) for check in state["attendu"]],
        debrief=to_debrief(state["debrief"]),
        autopilot=state["auto"],
        manual_helm=state["manual"],
        helm=to_helm(state["helm"]),
        station=to_station(state["station"]),
        authorization_requests=[
            contracts.AuthorizationRequest(
                ship=request["ship"],
                contact_id=request.get("cid"),
                requested_at_s=request["t"],
                text_fr=request["fr"],
            )
            for request in state["requests"]
        ],
        reconnaissance_target_by_ship=state["tasks"],
    )


def to_simulation(result: dict[str, Any]) -> contracts.Simulation:
    if not result["ok"]:
        return contracts.Simulation(accepted=False, refusal_reason=result["error"], hint=result.get("hint"))
    return contracts.Simulation(
        accepted=True,
        recipients=result["to"],
        text_fr=result["fr"],
        track_by_ship={
            ship: [contracts.TrackPoint(east_m=east, north_m=north, at_s=at) for east, north, at in points]
            for ship, points in result["paths"].items()
        },
        contact_cpas=[
            contracts.ContactCpa(
                ship=cpa["ship"],
                contact_id=cpa["contact"],
                cpa_nm=cpa["cpa_nm"],
                tcpa_s=cpa["tcpa_s"],
                cpa_nm_without_order=cpa["cpa_nm_sans_ordre"],
                at_risk=cpa["risque"],
            )
            for cpa in result["cpa"]
        ],
        ships_passings=[
            contracts.ShipsPassing(
                ship_a=passing["a"],
                ship_b=passing["b"],
                distance_m=passing["dist_m"],
                at_s=passing["t_s"],
                at_risk=passing["risque"],
            )
            for passing in result["ships_min"]
        ],
    )


def to_order_outcome(result: dict[str, Any]) -> contracts.OrderOutcome:
    return contracts.OrderOutcome(
        accepted=result["ok"],
        text_en=result.get("en"),
        text_fr=result.get("fr"),
        refusal_reason=result.get("error"),
        hint=result.get("hint"),
    )


AuthenticatedUser = Annotated[
    str, Header(alias="X-Hx-User", description="Utilisateur authentifié, posé par le back-office")
]


def missions_router(missions: Missions, settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(
        prefix="/v1", tags=["missions"], dependencies=[Depends(require_internal_token(settings))]
    )

    @router.get("/scenarios", response_model=list[contracts.ScenarioSummary], responses=ERROR_RESPONSES)
    async def list_scenarios() -> list[contracts.ScenarioSummary]:
        return [to_scenario_summary(scenario) for scenario in missions.list_scenarios()]

    @router.post(
        "/missions",
        status_code=HTTPStatus.CREATED,
        response_model=contracts.Mission,
        responses=ERROR_RESPONSES,
    )
    async def start_mission(
        body: contracts.StartMission, user: AuthenticatedUser = "local"
    ) -> contracts.Mission:
        run = await missions.start(
            body.scenario_id,
            body.player_ship,
            operator=user,
            autopilot=body.autopilot,
            manual_helm=body.manual_helm,
        )
        return to_mission(run)

    @router.get("/missions/{mission_id}", response_model=contracts.Mission, responses=ERROR_RESPONSES)
    async def read_mission(mission_id: str) -> contracts.Mission:
        return to_mission(missions.read(mission_id))

    @router.delete("/missions/{mission_id}", status_code=HTTPStatus.NO_CONTENT, responses=ERROR_RESPONSES)
    async def stop_mission(mission_id: str) -> Response:
        await missions.stop(mission_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post(
        "/missions/{mission_id}/orders", response_model=contracts.OrderOutcome, responses=ERROR_RESPONSES
    )
    async def submit_order(mission_id: str, body: contracts.SubmitOrder) -> contracts.OrderOutcome:
        return to_order_outcome(missions.submit_order(mission_id, body.text))

    @router.post(
        "/missions/{mission_id}/simulations", response_model=contracts.Simulation, responses=ERROR_RESPONSES
    )
    async def simulate_order(mission_id: str, body: contracts.SimulateOrder) -> contracts.Simulation:
        return to_simulation(missions.simulate_order(mission_id, body.text))

    @router.get(
        "/missions/{mission_id}/recommendations",
        response_model=list[contracts.Recommendation],
        responses=ERROR_RESPONSES,
    )
    async def recommend(mission_id: str) -> list[contracts.Recommendation]:
        return [contracts.Recommendation(**advice) for advice in missions.recommend(mission_id)]

    @router.post("/missions/{mission_id}/helm", response_model=contracts.Helm, responses=ERROR_RESPONSES)
    async def set_helm(mission_id: str, body: contracts.SetHelm) -> contracts.Helm:
        change = {
            HELM_FIELD_TO_ENGINE_KEY[name]: value
            for name, value in body.model_dump(exclude_none=True).items()
        }
        return to_helm(missions.set_helm(mission_id, change))

    @router.post(
        "/missions/{mission_id}/contacts/{contact_id}/classification",
        status_code=HTTPStatus.NO_CONTENT,
        responses=ERROR_RESPONSES,
    )
    async def classify_contact(mission_id: str, contact_id: str, body: contracts.ClassifyContact) -> Response:
        missions.classify_contact(mission_id, contact_id, body.classification.value)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post(
        "/missions/{mission_id}/requests/{ship}/reply",
        status_code=HTTPStatus.NO_CONTENT,
        responses=ERROR_RESPONSES,
    )
    async def reply_request(mission_id: str, ship: str, body: contracts.ReplyRequest) -> Response:
        missions.reply_request(mission_id, ship, body.approve)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.put(
        "/missions/{mission_id}/autopilot", status_code=HTTPStatus.NO_CONTENT, responses=ERROR_RESPONSES
    )
    async def set_autopilot(mission_id: str, body: contracts.SetAutopilot) -> Response:
        missions.set_autopilot(mission_id, body.enabled)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
