"""Interpréteur sur le jeu réel de 1541 messages (données hors dépôt).

    HX_KB=/chemin/kb/signals.json HX_TESTSET=/chemin/tests/testset.jsonl uv run pytest -m data

Le seuil de non-régression est un nombre de cas réussis par champ (aucun texte n'y figure). Il est lu dans
`data_baseline.json` s'il y est renseigné, sinon dans `data_baseline.local.json` (non commité, propre à la
machine qui détient les données). Au premier passage, le test écrit sa mesure dans ce fichier local et passe :
les passages suivants ne doivent pas faire moins bien.
"""

import json
import os
from pathlib import Path

import pytest
from legacy_harness import HERE, IMPLEMENTATIONS, legacy_module, load

pytestmark = pytest.mark.data

COMMITTED_BASELINE = HERE / "data_baseline.json"
LOCAL_BASELINE = HERE / "data_baseline.local.json"


def _read_floor(field: str) -> int | None:
    committed = json.loads(COMMITTED_BASELINE.read_text(encoding="utf-8")).get(field)
    if committed is not None:
        return int(committed)
    if LOCAL_BASELINE.exists():
        local = json.loads(LOCAL_BASELINE.read_text(encoding="utf-8")).get(field)
        return None if local is None else int(local)
    return None


def _record_floor(field: str, passed: int) -> None:
    recorded = json.loads(LOCAL_BASELINE.read_text(encoding="utf-8")) if LOCAL_BASELINE.exists() else {}
    recorded[field] = passed
    LOCAL_BASELINE.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _paths() -> tuple[Path, Path]:
    kb, testset = os.environ.get("HX_KB"), os.environ.get("HX_TESTSET")
    if not kb or not testset:
        pytest.skip("HX_KB et HX_TESTSET non définis (données hors dépôt)")
    return Path(kb), Path(testset)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
@pytest.mark.parametrize("field", ["spoken_text", "written_text"])
def test_interpreter_score_does_not_regress(field: str, impl: str) -> None:
    kb_path, testset_path = _paths()
    interpret = load("interpret", impl)
    evaluate = legacy_module("evaluate")
    kb = interpret.KB(kb_path)
    lines = testset_path.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    passed = sum(evaluate.check(c, interpret.interpret(c[field], kb))[0] for c in cases)

    floor = _read_floor(field)
    if floor is None:
        _record_floor(field, passed)
        return
    assert passed >= floor, f"{field} : {passed}/{len(cases)} réussis, seuil {floor}"
