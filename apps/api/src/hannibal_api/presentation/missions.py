from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from hannibal_api.application.missions import MissionError, MissionRun, Missions, NotFound
from hannibal_contracts import missions as c
from hannibal_contracts.common import ErrorBody
from hannibal_platform.errors import error_body
from hannibal_platform.internal_auth import require_internal_token
from hannibal_platform.logging import get_logger
from hannibal_platform.settings import BaseServiceSettings

log = get_logger(__name__)


async def on_mission_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, MissionError):
        raise exc
    log.warning("request_refused", code=exc.code, **exc.context)
    status = HTTPStatus.NOT_FOUND if isinstance(exc, NotFound) else HTTPStatus.CONFLICT
    return JSONResponse(error_body(exc.code, exc.message), status_code=status)


ERRORS: dict[int | str, dict[str, Any]] = {
    HTTPStatus.UNAUTHORIZED: {"model": ErrorBody},
    HTTPStatus.FORBIDDEN: {"model": ErrorBody},
    HTTPStatus.NOT_FOUND: {"model": ErrorBody},
    HTTPStatus.CONFLICT: {"model": ErrorBody},
    HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorBody},
    HTTPStatus.SERVICE_UNAVAILABLE: {"model": ErrorBody},
}


def scenario_summary(sc: dict[str, Any]) -> c.ScenarioSummary:
    guide = next(f["nom"] for f in sc["flotte"] if f["role"] == "guide")
    return c.ScenarioSummary(
        id=sc["id"],
        title=sc["titre"],
        level=sc.get("niveau"),
        duration_s=int(sc["duree_s"]),
        summary=sc.get("resume"),
        briefing=sc.get("briefing"),
        ships=[guide] + [f["nom"] for f in sc["flotte"] if f["nom"] != guide],
        guide=guide,
    )


def _objective(o: dict[str, Any]) -> c.Objective:
    return c.Objective(text=o["texte"], deadline_s=o.get("avant_t"), done=bool(o["ok"]), t=o.get("t"))


def _debrief(d: dict[str, Any] | None) -> c.Debrief | None:
    if d is None:
        return None
    return c.Debrief(
        objectives=[_objective(o) for o in d["checks"]],
        score=d["score"],
        total=d["total"],
        min_ship_distance_m=d["min_ship_m"],
        min_cpa_nm=d["min_cpa"],
        classifications={
            k: c.ClassificationResult(chosen=v["choisie"], actual=v["reelle"])
            for k, v in d["classes"].items()
        },
    )


def mission_view(run: MissionRun) -> c.Mission:
    s = run.engine.state()
    return c.Mission(
        id=run.id,
        scenario_id=run.scenario_id,
        title=s["titre"],
        player=s["player"],
        guide=s["guide"],
        phase=c.MissionPhase.ENDED if s["ended"] or run.stopped else c.MissionPhase.RUNNING,
        t=s["t"],
        duration_s=s["duree"],
        formation=s["form"],
        guide_course=s["gcap"],
        guide_speed_kn=s["gspeed_kn"],
        ships=[
            c.Ship(
                name=x["name"],
                role=x["role"],
                x=x["x"],
                y=x["y"],
                heading=x["hdg"],
                speed_mps=x["sog"],
                status=x["etat"],
                status_fleet=x["etat_c"],
            )
            for x in s["ships"]
        ],
        contacts=[
            c.Contact(
                id=x["id"],
                type=x["type"],
                x=x["x"],
                y=x["y"],
                course=x["cap"],
                speed_kn=x["vit"],
                classification=x["cls"],
                state=x["etat"],
                range_nm=x["range_nm"],
                bearing=x["brg"],
                cpa_nm=x["cpa_nm"],
                tcpa_min=x["tcpa_min"],
            )
            for x in s["contacts"]
        ],
        messages=[
            c.RadioMessage(
                id=m["id"],
                t=m["t"],
                sender=m["from"],
                recipient=m["to"],
                en=m["en"],
                fr=m["fr"],
                kind=m["kind"],
            )
            for m in s["msgs"]
        ],
        plan=[c.PlannedOrder(t=p["t"], en=p["en"], fr=p["fr"]) for p in s["plan"]],
        pending_orders=[p["fr"] for p in s["pending"]],
        objectives=[_objective(o) for o in s["attendu"]],
        debrief=_debrief(s["debrief"]),
        autopilot=s["auto"],
        manual=s["manual"],
        helm=c.Helm(course=s["helm"]["cap"], speed_kn=s["helm"]["kn"], rudder=s["helm"]["rudder"]),
        station=None
        if s["station"] is None
        else c.Station(x=s["station"]["x"], y=s["station"]["y"], error_m=s["station"]["err"]),
        requests=[
            c.AuthorizationRequest(ship=r["ship"], contact_id=r.get("cid"), t=r["t"], fr=r["fr"])
            for r in s["requests"]
        ],
        detached=s["tasks"],
    )


def simulation_view(r: dict[str, Any]) -> c.Simulation:
    if not r["ok"]:
        return c.Simulation(accepted=False, error=r["error"], hint=r.get("hint"))
    return c.Simulation(
        accepted=True,
        recipients=r["to"],
        fr=r["fr"],
        paths={n: [(p[0], p[1], p[2]) for p in pts] for n, pts in r["paths"].items()},
        cpa=[
            c.ContactCpa(
                ship=x["ship"],
                contact=x["contact"],
                cpa_nm=x["cpa_nm"],
                tcpa_s=x["tcpa_s"],
                cpa_nm_without_order=x["cpa_nm_sans_ordre"],
                risk=x["risque"],
            )
            for x in r["cpa"]
        ],
        ships_min=[
            c.ShipsPassing(a=x["a"], b=x["b"], distance_m=x["dist_m"], t_s=x["t_s"], risk=x["risque"])
            for x in r["ships_min"]
        ],
    )


Operator = Annotated[
    str, Header(alias="X-Hx-User", description="Utilisateur authentifié, posé par le back-office")
]


def missions_router(missions: Missions, settings: BaseServiceSettings) -> APIRouter:
    router = APIRouter(
        prefix="/v1", tags=["missions"], dependencies=[Depends(require_internal_token(settings))]
    )

    @router.get("/scenarios", response_model=list[c.ScenarioSummary], responses=ERRORS)
    async def list_scenarios() -> list[c.ScenarioSummary]:
        return [scenario_summary(sc) for sc in missions.list_scenarios()]

    @router.post("/missions", status_code=HTTPStatus.CREATED, response_model=c.Mission, responses=ERRORS)
    async def start_mission(body: c.StartMission, operator: Operator = "local") -> c.Mission:
        run = await missions.start(
            body.scenario_id, body.player, operator=operator, autopilot=body.autopilot, manual=body.manual
        )
        return mission_view(run)

    @router.get("/missions/{mission_id}", response_model=c.Mission, responses=ERRORS)
    async def read_mission(mission_id: str) -> c.Mission:
        return mission_view(missions.read(mission_id))

    @router.delete("/missions/{mission_id}", status_code=HTTPStatus.NO_CONTENT, responses=ERRORS)
    async def stop_mission(mission_id: str) -> Response:
        await missions.stop(mission_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/missions/{mission_id}/orders", response_model=c.OrderOutcome, responses=ERRORS)
    async def submit_order(mission_id: str, body: c.SubmitOrder) -> c.OrderOutcome:
        r = missions.submit_order(mission_id, body.text)
        return c.OrderOutcome(
            accepted=r["ok"], en=r.get("en"), fr=r.get("fr"), error=r.get("error"), hint=r.get("hint")
        )

    @router.post("/missions/{mission_id}/simulations", response_model=c.Simulation, responses=ERRORS)
    async def simulate_order(mission_id: str, body: c.SimulateOrder) -> c.Simulation:
        return simulation_view(missions.simulate(mission_id, body.text))

    @router.get(
        "/missions/{mission_id}/recommendations", response_model=list[c.Recommendation], responses=ERRORS
    )
    async def recommend(mission_id: str) -> list[c.Recommendation]:
        return [c.Recommendation(**r) for r in missions.recommend(mission_id)]

    @router.post("/missions/{mission_id}/helm", response_model=c.Helm, responses=ERRORS)
    async def set_helm(mission_id: str, body: c.SetHelm) -> c.Helm:
        keys = {
            "rudder": "rudder",
            "course": "cap",
            "course_delta": "dcap",
            "speed_kn": "kn",
            "speed_delta": "dkn",
        }
        change = {keys[k]: v for k, v in body.model_dump(exclude_none=True).items()}
        h = missions.set_helm(mission_id, change)
        return c.Helm(course=round(h["cap"], 1), speed_kn=round(h["kn"], 1), rudder=h["rudder"])

    @router.post(
        "/missions/{mission_id}/contacts/{contact_id}/classification",
        status_code=HTTPStatus.NO_CONTENT,
        responses=ERRORS,
    )
    async def classify_contact(mission_id: str, contact_id: str, body: c.ClassifyContact) -> Response:
        missions.classify(mission_id, contact_id, body.classification.value)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post(
        "/missions/{mission_id}/requests/{ship}/reply", status_code=HTTPStatus.NO_CONTENT, responses=ERRORS
    )
    async def reply_request(mission_id: str, ship: str, body: c.ReplyRequest) -> Response:
        missions.reply(mission_id, ship, body.approve)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.put("/missions/{mission_id}/autopilot", status_code=HTTPStatus.NO_CONTENT, responses=ERRORS)
    async def set_autopilot(mission_id: str, body: c.SetAutopilot) -> Response:
        missions.set_autopilot(mission_id, body.enabled)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
