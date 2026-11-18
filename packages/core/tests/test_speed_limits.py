import pytest
from hannibal_core.orders import grammar, mtp_mapping
from hannibal_core.orders.limits import DEFAULT_SPEED, SpeedLimits


def test_bornes_par_defaut() -> None:
    assert (DEFAULT_SPEED.min_kn, DEFAULT_SPEED.max_kn) == (3, 28)


@pytest.mark.parametrize(
    ("kn", "expected", "noted"), [(12, 12, False), (28, 28, False), (40, 28, True), (1, 3, True)]
)
def test_clamp(kn: float, expected: int, noted: bool) -> None:
    k, note = DEFAULT_SPEED.clamp(kn)
    assert k == expected
    assert (note is not None) is noted


def test_bornes_invalides_refusees() -> None:
    with pytest.raises(ValueError, match="bornes"):
        SpeedLimits(min_kn=20, max_kn=10)


def test_clavier_et_signal_appliquent_la_meme_limite() -> None:
    limits = SpeedLimits(min_kn=5, max_kn=18)
    typed = grammar.parse("SPEED 25", ["alfa"], speed=limits)
    signal, note = mtp_mapping.to_orders(
        {"status": "ok", "signal": "SPEED", "params": {"speed_knots": 25}}, 12, speed=limits
    )
    assert typed["orders"] == signal == [{"type": "SPEED", "kn": 18}]
    assert typed["notes"] == [note]
