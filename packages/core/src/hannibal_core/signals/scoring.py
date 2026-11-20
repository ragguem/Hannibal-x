"""Notation d'une interprétation face au résultat attendu d'un cas du jeu de test.

Un cas est réussi si le statut, le signal et les paramètres attendus sont retrouvés.
"""

from typing import Any

from hannibal_core.signals.interpreter import compact

UNRESOLVED_SIGNAL_STATUSES = ("spare", "not_releasable", "unknown_signal")


def score_interpretation(case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    """(réussi, raison de l'échec) ; `case["expected"]` suit le format du jeu de test."""
    expected = case["expected"]
    wanted_status = "ok" if expected["status"] == "ok_identification_only" else expected["status"]
    if result["status"] != wanted_status:
        return False, f"statut {result['status']} au lieu de {wanted_status}"
    if wanted_status == "ok":
        candidate_ids = [c["signal_id"] for c in result["candidates"]]
        if result["signal_id"] != expected["signal_id"] and expected["signal_id"] not in candidate_ids:
            return False, f"signal {result['signal']} au lieu de {expected['signal']}"
        for name, value in (expected.get("params") or {}).items():
            if result["params"].get(name) != value:
                return False, f"parametre {name} = {result['params'].get(name)} au lieu de {value}"
    elif wanted_status in UNRESOLVED_SIGNAL_STATUSES and compact(result["signal"] or "") != compact(
        expected["signal"]
    ):
        return False, f"signal {result['signal']} au lieu de {expected['signal']}"
    return True, ""
