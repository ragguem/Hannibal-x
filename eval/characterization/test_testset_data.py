"""Interpréteur sur le jeu réel de 1541 messages (données hors dépôt).

    HX_KB=/chemin/kb/signals.json HX_TESTSET=/chemin/tests/testset.jsonl uv run pytest -m data

Le seuil de non-régression est un nombre de cas réussis par champ, dans `data_baseline.json`
(aucun texte n'y figure). Tant qu'il vaut null, le test rapporte la mesure et passe en « skipped ».
"""

import json
import os
from pathlib import Path

import pytest
from legacy_harness import HERE, legacy_module

pytestmark = pytest.mark.data

BASELINE = HERE / "data_baseline.json"


def _paths() -> tuple[Path, Path]:
    kb, testset = os.environ.get("HX_KB"), os.environ.get("HX_TESTSET")
    if not kb or not testset:
        pytest.skip("HX_KB et HX_TESTSET non définis (données hors dépôt)")
    return Path(kb), Path(testset)


@pytest.mark.parametrize("field", ["spoken_text", "written_text"])
def test_interpreter_score_does_not_regress(field: str) -> None:
    kb_path, testset_path = _paths()
    interpret = legacy_module("interpret")
    evaluate = legacy_module("evaluate")
    kb = interpret.KB(kb_path)
    lines = testset_path.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    passed = sum(evaluate.check(c, interpret.interpret(c[field], kb))[0] for c in cases)

    floor = json.loads(BASELINE.read_text(encoding="utf-8"))[field]
    if floor is None:
        pytest.skip(f"{field} : {passed}/{len(cases)} réussis ; reporter ce nombre dans data_baseline.json")
    assert passed >= floor, f"{field} : {passed}/{len(cases)} réussis, seuil {floor}"
