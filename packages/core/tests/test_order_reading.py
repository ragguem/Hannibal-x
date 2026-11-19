from pathlib import Path

import pytest
from hannibal_core.orders.order_reading import OrderContext, ReadingMethod, read_order
from hannibal_core.signals import KB

SYNTHETIC_TABLE = Path(__file__).resolve().parents[3] / "eval/characterization/fixtures/kb_synthetic.json"
SHIPS = ("hannibal", "alfa", "charlie", "delta")


@pytest.fixture(scope="module")
def table() -> KB:
    return KB(SYNTHETIC_TABLE)


def context(player: str = "hannibal", **overrides: object) -> OrderContext:
    return OrderContext(
        ships=SHIPS,
        player=player,
        guide="hannibal",
        speed_kn_of=lambda _ship: 12.0,
        **overrides,  # type: ignore[arg-type]
    )


def test_mtp_signal_becomes_orders_with_its_reference(table: KB) -> None:
    reading = read_order("ALFA THIS IS HANNIBAL TURN STARBOARD NINER OVER", context(), table)
    assert reading["ok"] is True
    assert reading["method"] is ReadingMethod.MTP
    assert reading["reference"] == "FICTIF §1"
    assert reading["to"] == ["ALFA"]
    assert reading["orders"] == [{"type": "TURN", "deg": 90, "side": "STBD", "together": True}]
    assert reading["en"].startswith("ALFA THIS IS HANNIBAL TURN")
    assert reading["fr"].startswith("À Alfa : virer")


def test_missing_frame_is_restored_and_noted(table: KB) -> None:
    reading = read_order("ALFA TURN STARBOARD NINER", context(), table)
    assert reading["ok"] is True
    assert reading["to"] == ["ALFA"]
    assert reading["notes"] == ["Le message commence par ALFA : pris comme destinataire."]


def test_spare_code_is_refused_without_guessing(table: KB) -> None:
    reading = read_order("ALFA THIS IS HANNIBAL AB 12 OVER", context(), table)
    assert reading["ok"] is False
    assert reading["status"] == "spare"
    assert reading["en"] is None
    assert reading["error"].startswith("Code sans sens attribué")


def test_incomplete_signal_falls_back_to_simplified_syntax(table: KB) -> None:
    reading = read_order("ALFA THIS IS HANNIBAL CORPEN 090 OVER", context(), table)
    assert reading["ok"] is True
    assert reading["method"] is ReadingMethod.SIMPLIFIED
    assert reading["orders"][0] == {"type": "CORPEN", "cap": 90}


def test_missing_side_gets_a_hint(table: KB) -> None:
    reading = read_order("ALFA THIS IS HANNIBAL TURN NINER OVER", context(), table)
    assert reading["ok"] is False
    assert reading["status"] == "missing_parameter"
    assert "bord" in reading["hint"]


def test_simplified_syntax_is_the_fallback(table: KB) -> None:
    reading = read_order("ALL SHIPS SPEED 14", context(), table)
    assert reading["ok"] is True
    assert reading["to"] == ["TOUS"]
    assert reading["orders"][0]["type"] == "SPEED"


@pytest.mark.parametrize("signal_table", [None, "table"])
def test_escort_acknowledges_to_the_guide(signal_table: str | None, table: KB) -> None:
    reading = read_order("ROGER", context(player="alfa"), table if signal_table else None)
    assert reading["ok"] is True
    assert reading["method"] is ReadingMethod.REPLY
    assert reading["to"] == ["HANNIBAL"]
    assert reading["orders"] == [{"type": "ACK", "text": "ROGER"}]
    assert reading["en"] == "HANNIBAL THIS IS ALFA ROGER OVER"


def test_wilco_is_an_acknowledgement_with_execution() -> None:
    reading = read_order("HANNIBAL THIS IS ALFA WILCO OVER", context(player="alfa"))
    assert reading["orders"] == [{"type": "ACK", "text": "WILCO"}]
    assert reading["fr"] == "À Hannibal : bien reçu, j'exécute."


def test_affirmative_answers_the_pending_request() -> None:
    reading = read_order("AFFIRMATIVE", context(pending_requests=["charlie"]))
    assert reading["ok"] is True
    assert reading["to"] == ["CHARLIE"]
    assert reading["orders"] == [{"type": "CAPT", "do": "affirm"}]
    assert reading["notes"] == []


def test_answer_without_request_is_noted_and_without_ship_refused() -> None:
    answered = read_order("CHARLIE THIS IS HANNIBAL NEGATIVE OVER", context())
    assert answered["orders"] == [{"type": "CAPT", "do": "negat"}]
    assert answered["notes"] == ["Ce navire n'a pas de demande en attente."]
    assert read_order("NEGATIVE", context())["ok"] is False


def test_escort_does_not_order_maneuvers(table: KB) -> None:
    reading = read_order("ALL SHIPS THIS IS ALFA TURN STARBOARD NINER OVER", context(player="alfa"), table)
    assert reading["ok"] is False
    assert reading["error"] == "Message non envoyé : une escorte ne donne pas d'ordre de manœuvre."


def test_without_table_unknown_text_keeps_the_grammar_hint() -> None:
    reading = read_order("BONJOUR", context())
    assert reading["ok"] is False
    assert "Mots reconnus" in reading["hint"]
