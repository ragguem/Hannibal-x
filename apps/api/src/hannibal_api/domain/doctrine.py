"""Questions de doctrine (architecture 1.1.0 § 7) : chaque réponse ou refus laisse une trace rejouable."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

ASK_PERMISSION = "doctrine:ask"
CLASSIFIED_PERMISSION = "doctrine:classified"


@dataclass(frozen=True, slots=True)
class DoctrineTrace:
    """Ligne de `ops.doctrine_traces` : question, réponse ou motif du refus, et de quoi la rejouer."""

    id: str
    actor_id: str
    question: str
    language: str
    publication: str | None
    status: str
    refusal_reason: str | None
    answer: str
    model: str
    index_version: str
    duration_ms: int
    cited: list[dict[str, Any]] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)


def order_parameters(orders: Sequence[Mapping[str, Any]]) -> dict[str, int | str]:
    """Valeurs décodées d'un ordre, celles que l'explication doit reprendre sans les altérer."""
    parameters: dict[str, int | str] = {}
    for order in orders:
        kind = order.get("type")
        if kind == "CORPEN" and "cap" in order:
            parameters["true_course"] = round(float(order["cap"]))
        elif kind == "TURN" and "deg" in order:
            parameters["relative_degrees"] = round(float(order["deg"]))
            parameters["side"] = str(order.get("side", ""))
        elif kind == "SPEED" and "kn" in order:
            parameters["speed_knots"] = round(float(order["kn"]))
    return parameters
