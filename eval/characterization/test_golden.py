import pytest
from legacy_harness import RUNNERS, differences, golden_path, read_golden


@pytest.mark.parametrize("name", sorted(RUNNERS))
def test_legacy_matches_golden(name: str) -> None:
    assert golden_path(name).exists(), f"golden absent : python eval/characterization/regenerate.py {name}"
    diffs = differences(read_golden(name), RUNNERS[name]())
    assert not diffs, "\n".join(diffs[:20])


def test_differences_tolerates_float_noise() -> None:
    assert differences({"a": [1.0, 2]}, {"a": [1.0 + 1e-9, 2]}) == []
    assert differences({"a": 1.0}, {"a": 1.1}) != []
    assert differences({"a": 1}, {"b": 1}) != []
