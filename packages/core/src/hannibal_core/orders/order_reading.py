"""Lecture d'un ordre de l'opérateur, du texte aux ordres du moteur (§ 7).

Repris de `Hannibal._build` (legacy/app_v3/server.py) sans registre ni appel réseau. Dans l'ordre : trame
rétablie, accusé (ROGER, WILCO) ou réponse à une demande (AFFIRMATIVE, NEGATIVE), interpréteur MTP sur la
table de la publication, puis syntaxe simplifiée du simulateur. Sans table MTP, seuls les accusés, les
réponses et la syntaxe simplifiée sont reconnus.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hannibal_core.orders import grammar
from hannibal_core.orders import mtp_mapping as mapping
from hannibal_core.orders.limits import DEFAULT_SPEED, SpeedLimits
from hannibal_core.signals import KB, interpret

MOTION = ("CORPEN", "TURN", "SPEED", "FORM", "RESUME")
NAME_THE_SHIP = "Dites le nom du navire, ou choisissez-le à l'écran."
ESCORT_NOTE = (
    "Vous commandez une escorte : seul le guide donne des ordres de manœuvre. "
    "Rendez compte au guide (ROGER, A STATION, M SPEED…)."
)


class ReadingMethod(StrEnum):
    REPLY = "reply"
    MTP = "mtp"
    SIMPLIFIED = "simplified"


@dataclass(frozen=True, slots=True)
class OrderContext:
    ships: Sequence[str]
    player: str
    guide: str
    speed_kn_of: Callable[[str], float]
    pending_requests: Sequence[str] = ()
    default_target: str = "TOUS"


def read_order(
    text: str, context: OrderContext, signal_table: KB | None = None, speed: SpeedLimits = DEFAULT_SPEED
) -> dict[str, Any]:
    """Texte -> lecture : `ok`, destinataires, ordres, textes EN et FR, statut MTP, notes et conseil."""
    if not text.strip():
        return _refused("Message vide.", status="empty")
    framed, frame_note = mapping.fix_frame(text, list(context.ships), context.player)
    reply = mapping.reply_word(framed, list(context.ships))
    if reply is not None:
        word, addressed = reply
        return _read_reply(word, addressed, context)
    if signal_table is None:
        parsed = grammar.parse(text, list(context.ships), speed=speed)
        if not parsed["ok"]:
            return _refused(parsed["error"], hint=parsed["hint"], status="unknown_signal")
        return _conclude(_simplified(parsed), context, [n for n in (frame_note,) if n])
    signal = _read_signal(framed, context, signal_table, speed)
    if frame_note:
        signal["notes"].insert(0, frame_note)
    if signal["status"] != "ok":
        parsed = grammar.parse(text, list(context.ships), speed=speed)
        if parsed["ok"]:
            simplified = _simplified(parsed)
            simplified["to_from_message"] = signal["to_from_message"]
            return _conclude(simplified, context, signal["notes"])
    return _conclude(signal, context, signal["notes"])


def _read_reply(word: str, addressed: str | None, context: OrderContext) -> dict[str, Any]:
    me, guide = context.player, context.guide
    pending = list(context.pending_requests)
    selected = context.default_target.lower()
    target = addressed or (
        selected if selected != "tous" and selected in context.ships else (pending[0] if pending else None)
    )
    notes: list[str] = []
    if word in ("roger", "wilco"):
        target = addressed or (guide if me != guide else target)
        written, orders, effect = word.upper(), [{"type": "ACK", "text": word.upper()}], None
        phrase = "bien reçu." if word == "roger" else "bien reçu, j'exécute."
        status_fr = "Accusé de réception"
    else:
        written = "AFFIRMATIVE" if word == "affirm" else "NEGATIVE"
        orders, effect = [{"type": "CAPT", "do": word}], "Le commandant du navire agit selon votre réponse."
        phrase = (
            "affirmatif, autorisation accordée." if word == "affirm" else "négatif, restez à votre poste."
        )
        status_fr = "Réponse reconnue"
        if target is not None and target not in pending:
            notes.append("Ce navire n'a pas de demande en attente.")
    if target is None:
        return _refused(NAME_THE_SHIP, status="empty")
    return {
        **_reading(ReadingMethod.REPLY, "ok", status_fr),
        "ok": True,
        "to": [target.upper()],
        "orders": orders,
        "written_signal": written,
        "en": f"{target.upper()} THIS IS {me.upper()} {written} OVER",
        "fr": f"À {target.capitalize()} : {phrase}",
        "effect": effect,
        "notes": notes,
    }


def _read_signal(framed: str, context: OrderContext, table: KB, speed: SpeedLimits) -> dict[str, Any]:
    interpretation = interpret(framed, table)
    notes: list[str] = []
    to, destination_note = mapping.destination(interpretation, list(context.ships), context.default_target)
    if destination_note:
        notes.append(destination_note)
    sender = interpretation.get("from")
    if sender and sender.upper() != context.player.upper():
        notes.append(f"L'émetteur énoncé ({sender}) n'est pas votre indicatif ({context.player.upper()}).")
    reference_ship = to[0].lower() if to and to != ["TOUS"] else context.guide
    speed_kn = context.speed_kn_of(reference_ship)
    groups = interpretation.get("groups") or [interpretation]
    orders: list[dict[str, Any]] = []
    effects: list[str] = []
    phrases: list[str] = []
    status = "ok"
    for group in groups:
        group_orders, effect = mapping.to_orders(group, speed_kn, speed)
        if group["status"] != "ok" and status == "ok":
            status = group["status"]
        if group_orders is None:
            group_orders = []
            group["status"] = "invalid_parameter"
            group.setdefault("warnings", []).append(effect)
            status = "invalid_parameter" if status == "ok" else status
        elif effect:
            effects.append(effect)
        orders += group_orders
        group["status_fr"] = mapping.STATUS_FR.get(group["status"], group["status"])
        if group["status"] == "ok":
            phrases.append(
                mapping.fr_signal(group, to)
                or (grammar.fr_message(to or ["TOUS"], group_orders) if group_orders else None)
                or f"Signal {group.get('signal') or ''} — sens d'après la publication : {group.get('meaning') or ''}"
            )
    return {
        **_reading(ReadingMethod.MTP, status, mapping.STATUS_FR.get(status, status)),
        "to": to,
        "to_from_message": bool(interpretation.get("to")),
        "orders": orders,
        "phrases": phrases,
        "effect": " ".join(effects) or None,
        "notes": notes,
        "signal": interpretation.get("signal"),
        "signal_id": interpretation.get("signal_id"),
        "reference": interpretation.get("reference"),
        "params": interpretation.get("params") or {},
        "warnings": interpretation.get("warnings") or [],
        "written_signal": interpretation.get("written_signal"),
        "groups": [
            {k: g.get(k) for k in ("status", "status_fr", "signal", "reference", "params", "written_signal")}
            for g in groups
        ],
    }


def _simplified(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        **_reading(ReadingMethod.SIMPLIFIED, "ok", "Syntaxe simplifiée reconnue"),
        "to": parsed["to"],
        "to_from_message": True,
        "orders": parsed["orders"],
        "effect": "Syntaxe simplifiée du simulateur, hors publication MTP.",
    }


def _conclude(reading: dict[str, Any], context: OrderContext, notes: list[str]) -> dict[str, Any]:
    """Règle de l'escorte, phrase française, texte émis et conseil."""
    me, guide = context.player, context.guide
    to, orders = reading["to"], reading["orders"]
    escort_blocked = False
    if me != guide:
        if not reading.pop("to_from_message", True):
            to = [guide.upper()]
            notes = [n for n in notes if not n.startswith("Destinataire non énoncé")]
        if any(o["type"] in MOTION or o["type"] == "CAPT" for o in orders):
            notes.append(ESCORT_NOTE)
            escort_blocked = True
    reading.pop("to_from_message", None)
    phrases = reading.pop("phrases", [])
    executable = reading["status"] == "ok" and not escort_blocked
    if escort_blocked:
        fr = "Message non envoyé : une escorte ne donne pas d'ordre de manœuvre."
    elif not executable:
        fr = reading["status_fr"] + "."
    elif reading["method"] is ReadingMethod.SIMPLIFIED:
        fr = grammar.fr_message(to, orders)
    else:
        fr = _join_phrases(phrases)
    reading.update(to=to, notes=notes, fr=fr, ok=bool(executable and to))
    if not reading["ok"]:
        reading["error"] = fr if not executable else next(iter(notes), NAME_THE_SHIP)
        reading["hint"] = None if executable else mapping.HINTS.get(reading["status"])
        reading["en"] = None
        return reading
    destination = "ALL SHIPS" if to == ["TOUS"] else to[0]
    reading["en"] = (
        grammar.to_text(to, orders, me)
        if reading["method"] is ReadingMethod.SIMPLIFIED
        else f"{destination} THIS IS {me.upper()} {reading['written_signal']} OVER"
    )
    return reading


def _join_phrases(phrases: list[str]) -> str:
    """« À Alfa : virer… » puis « À Alfa : prendre… » -> « À Alfa : virer… Puis : prendre… »."""
    first = phrases[0]
    who = first.split(" : ", 1)[0] if " : " in first else ""
    return first + "".join(
        " Puis : " + (p.split(" : ", 1)[1] if who and p.startswith(who + " : ") else p) for p in phrases[1:]
    )


def _reading(method: ReadingMethod, status: str, status_fr: str) -> dict[str, Any]:
    return {
        "ok": False,
        "method": method,
        "status": status,
        "status_fr": status_fr,
        "to": None,
        "orders": [],
        "en": None,
        "fr": None,
        "effect": None,
        "notes": [],
        "hint": None,
        "signal": None,
        "signal_id": None,
        "reference": None,
        "params": {},
        "warnings": [],
        "written_signal": None,
        "groups": [],
    }


def _refused(error: str, *, hint: str | None = None, status: str) -> dict[str, Any]:
    return {
        **_reading(ReadingMethod.MTP, status, mapping.STATUS_FR.get(status, status)),
        "error": error,
        "hint": hint,
    }
