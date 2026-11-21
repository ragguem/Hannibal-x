"""Écrit les schémas JSON des contrats dans `packages/contracts/schemas/`.

Le test de dérive échoue si un modèle change sans régénération : `uv run hx-export-schemas`.
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from hannibal_contracts import CONTRACTS_VERSION, asr, audit, rerank, scenario, session
from hannibal_contracts import doctrine as d
from hannibal_contracts import missions as m
from hannibal_contracts import sim_bridge as sb
from hannibal_contracts.common import DependencyStatus, ErrorBody, Health, Readiness

MODELS: tuple[type[BaseModel], ...] = (
    ErrorBody,
    Health,
    DependencyStatus,
    Readiness,
    m.ScenarioSummary,
    m.StartMission,
    m.Mission,
    m.SubmitOrder,
    m.OrderOutcome,
    m.VoiceOrderOutcome,
    m.DecideCommand,
    m.Command,
    m.SetHelm,
    m.Helm,
    m.ClassifyContact,
    m.ReplyRequest,
    m.SetAutopilot,
    m.SimulateOrder,
    m.Simulation,
    m.Recommendation,
    audit.AuditEventView,
    audit.AuditPage,
    audit.AuditIntegrity,
    session.SignIn,
    session.SessionView,
    sb.SpawnFleet,
    sb.SteerFleet,
    sb.WorldState,
    sb.RecordManeuver,
    sb.ManeuverRecord,
    asr.Transcription,
    d.DoctrineQuestion,
    d.DoctrineAnswer,
    d.Publications,
    d.GlossaryResult,
    d.CommandExplanation,
    d.AskRequest,
    d.AskResponse,
    d.ExplainRequest,
    d.Explanation,
    rerank.RerankRequest,
    rerank.RerankResponse,
    scenario.ScenarioDocument,
)
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def render(model: type[BaseModel]) -> str:
    schema = model.model_json_schema()
    schema["$id"] = f"urn:hannibal-x:contracts:{CONTRACTS_VERSION}:{model.__name__}"
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def expected_files() -> dict[str, str]:
    return {f"{model.__name__}.json": render(model) for model in MODELS}


def main() -> int:
    SCHEMAS_DIR.mkdir(exist_ok=True)
    for name, content in expected_files().items():
        (SCHEMAS_DIR / name).write_text(content, encoding="utf-8", newline="\n")
    sys.stdout.write(f"{len(MODELS)} schémas écrits dans {SCHEMAS_DIR}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
