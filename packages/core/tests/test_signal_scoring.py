from hannibal_core.signals import score_interpretation


def interpreted(**overrides: object) -> dict:
    base = {"status": "ok", "signal": "TURN 9", "signal_id": "s-1", "candidates": [], "params": {}}
    return base | overrides


def test_matching_signal_and_params_pass() -> None:
    case = {"expected": {"status": "ok", "signal": "TURN 9", "signal_id": "s-1", "params": {"side": "STBD"}}}
    assert score_interpretation(case, interpreted(params={"side": "STBD"})) == (True, "")


def test_identification_only_counts_as_ok_and_accepts_a_candidate() -> None:
    case = {"expected": {"status": "ok_identification_only", "signal": "TURN 9", "signal_id": "s-2"}}
    assert score_interpretation(case, interpreted(candidates=[{"signal_id": "s-2"}]))[0]


def test_wrong_status_signal_or_param_fail_with_a_reason() -> None:
    expected = {"status": "ok", "signal": "TURN 9", "signal_id": "s-1", "params": {"side": "STBD"}}
    assert score_interpretation({"expected": expected}, interpreted(status="spare")) == (
        False,
        "statut spare au lieu de ok",
    )
    assert not score_interpretation({"expected": expected}, interpreted(signal_id="s-9"))[0]
    assert not score_interpretation({"expected": expected}, interpreted(params={"side": "PORT"}))[0]


def test_unresolved_signals_compare_codes_without_spaces() -> None:
    case = {"expected": {"status": "unknown_signal", "signal": "ZZ 12"}}
    assert score_interpretation(case, interpreted(status="unknown_signal", signal="ZZ12"))[0]
    assert not score_interpretation(case, interpreted(status="unknown_signal", signal=None))[0]
