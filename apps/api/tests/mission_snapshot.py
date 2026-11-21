"""Photo de lancement telle que le back-office l'envoie, construite depuis un scénario du dépôt."""

import uuid
from pathlib import Path
from typing import Any

import yaml

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"
FRIGATE = {
    "class_code": "fregate",
    "min_speed_knots": 3,
    "max_speed_knots": 28,
    "turn_radius_meters": 600.0,
    "length_meters": 142.0,
}


def scenario_document(scenario_id: str) -> dict[str, Any]:
    return dict(yaml.safe_load((SCENARIOS_DIR / f"{scenario_id}.yaml").read_text(encoding="utf-8")))


def run_body(
    scenario_id: str = "contact_inconnu",
    player_ship: str = "hannibal",
    operator: str = "local",
    **options: Any,
) -> dict[str, Any]:
    document = scenario_document(scenario_id)
    return {
        "scenario_version": 1,
        "scenario": document,
        "player_ship": player_ship,
        "operator": operator,
        "ships": [{"call_sign": ship["nom"], **FRIGATE} for ship in document["flotte"]],
        **options,
    }


def run_path(mission_id: str | None = None) -> str:
    return f"/internal/missions/{mission_id or uuid.uuid4()}/run"
