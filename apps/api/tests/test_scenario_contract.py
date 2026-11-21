from pathlib import Path

import pytest
import yaml
from hannibal_core.scenario.schema import validate
from pydantic import ValidationError

from hannibal_contracts.scenario import ScenarioDocument

SCENARIOS = sorted((Path(__file__).resolve().parents[1] / "scenarios").glob("*.yaml"))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_catalog_scenarios_match_the_published_contract_and_the_core_rules(path: Path) -> None:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert ScenarioDocument.model_validate(document).id == path.stem
    assert validate(document) == []


def test_contract_refuses_an_unknown_top_level_field() -> None:
    document = yaml.safe_load(SCENARIOS[0].read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        ScenarioDocument.model_validate({**document, "meteo": "grain"})


def test_contract_refuses_a_fleet_member_without_a_known_role() -> None:
    document = yaml.safe_load(SCENARIOS[0].read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        ScenarioDocument.model_validate({**document, "flotte": [{"nom": "alfa", "role": "capitaine"}]})
