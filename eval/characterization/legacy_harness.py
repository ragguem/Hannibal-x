"""Rejoue les cas de `cases/` sur l'ancien code (`legacy/`) et rend des sorties JSON.

Les sorties figées dans `golden/` décrivent le comportement à conserver ; la nouvelle
implémentation sera vérifiée contre les mêmes fichiers.
"""

from __future__ import annotations

import importlib
import json
import math
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LEGACY_APP = REPO / "legacy" / "app_v3"
LEGACY_HX = REPO / "legacy" / "hx" / "scripts"
CASES = HERE / "cases"
GOLDEN = HERE / "golden"
FLOAT_TOLERANCE = 1e-6


def legacy_module(name: str) -> ModuleType:
    for path in (LEGACY_APP, LEGACY_HX):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return importlib.import_module(name)


def load_cases(name: str) -> Any:
    return json.loads((CASES / f"{name}.json").read_text(encoding="utf-8"))


def canon(value: Any) -> Any:
    """Forme JSON stable : tuples en listes, flottants arrondis à 9 décimales."""
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, (list, tuple)):
        return [canon(v) for v in value]
    if isinstance(value, dict):
        return {str(k): canon(v) for k, v in value.items()}
    return value


def run_interpret() -> list[dict[str, Any]]:
    interpret = legacy_module("interpret")
    cases = load_cases("interpret")
    kb = interpret.KB(HERE / cases["kb"])
    return [{"input": text, "output": canon(interpret.interpret(text, kb))} for text in cases["texts"]]


def run_mtp() -> list[dict[str, Any]]:
    mtp = legacy_module("mtp")
    cases = load_cases("mtp")
    out = []
    for text in cases["texts"]:
        parsed = mtp.parse(text, cases["ships"], cases["sender"])
        entry: dict[str, Any] = {"input": text, "parse": parsed}
        if parsed["ok"]:
            entry["fr_message"] = mtp.fr_message(parsed["to"], parsed["orders"])
            entry["to_text"] = mtp.to_text(parsed["to"], parsed["orders"], cases["sender"])
        out.append(canon(entry))
    return out


def run_sim() -> dict[str, Any]:
    sim = legacy_module("sim")
    cases = load_cases("sim")
    ships, contacts = cases["ships"], cases["contacts"]
    path_cases = []
    for c in cases["paths"]:
        kwargs = {"horizon": c["horizon"], **({"step": c["step"]} if "step" in c else {})}
        path_cases.append({"input": c, "output": sim.path(ships[c["ship"]], c["orders"], **kwargs)})
    cpa_cases = []
    for c in cases["cpa_now"]:
        own = c.get("own_inline") or ships[c["own"]]
        contact = c.get("contact_inline") or contacts[c["contact"]]
        cpa_cases.append({"input": c, "output": sim.cpa_now(own, contact)})
    return canon(
        {
            "apply_orders": [
                {"input": c, "output": sim.apply_orders(c["hdg"], c["sog"], c["orders"])}
                for c in cases["apply_orders"]
            ],
            "paths": path_cases,
            "ghosts": [
                {"input": c, "output": sim.ghost(ships, c["to"], c["orders"], contacts, c["horizon"])}
                for c in cases["ghosts"]
            ],
            "cpa_now": cpa_cases,
        }
    )


def run_reco() -> list[dict[str, Any]]:
    reco = legacy_module("reco")
    return [
        canon(
            {
                "input": s["name"],
                "output": reco.recommend(s["state"], s["player"], s["guide"], s["pending"], s["reported"]),
            }
        )
        for s in load_cases("reco")["scenarios"]
    ]


def run_hxbridge() -> dict[str, Any]:
    bridge = legacy_module("hxbridge")
    interpret = legacy_module("interpret")
    cases = load_cases("hxbridge")
    ships, me, speed = cases["ships"], cases["me"], cases["speed_kn"]
    alt = cases["fix_frame_me_is_ship"]

    interp_cases = load_cases("interpret")
    kb = interpret.KB(HERE / interp_cases["kb"])
    from_interpret = []
    for text in interp_cases["texts"]:
        interp = interpret.interpret(text, kb)
        from_interpret.append(
            {
                "input": text,
                "to_orders": bridge.to_orders(interp, speed),
                "fr_signal": {json.dumps(to): bridge.fr_signal(interp, to) for to in cases["fr_signal_to"]},
            }
        )

    return canon(
        {
            "fix_frame": [{"input": t, "output": bridge.fix_frame(t, ships, me)} for t in cases["fix_frame"]],
            "fix_frame_me_is_ship": [
                {"input": t, "output": bridge.fix_frame(t, ships, alt["me"])} for t in alt["texts"]
            ],
            "reply_word": [{"input": t, "output": bridge.reply_word(t, ships)} for t in cases["reply_word"]],
            "destination": [
                {"input": c, "output": bridge.destination(c["interp"], ships, c["default"])}
                for c in cases["destination"]
            ],
            "to_orders_direct": [
                {
                    "input": c,
                    "to_orders": bridge.to_orders(c, speed),
                    "fr_signal": {json.dumps(to): bridge.fr_signal(c, to) for to in cases["fr_signal_to"]},
                }
                for c in cases["to_orders_direct"]
            ],
            "from_interpret": from_interpret,
        }
    )


RUNNERS: dict[str, Callable[[], Any]] = {
    "interpret": run_interpret,
    "mtp": run_mtp,
    "sim": run_sim,
    "reco": run_reco,
    "hxbridge": run_hxbridge,
}


def golden_path(name: str) -> Path:
    return GOLDEN / f"{name}.json"


def read_golden(name: str) -> Any:
    return json.loads(golden_path(name).read_text(encoding="utf-8"))


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def differences(expected: Any, actual: Any, where: str = "$") -> list[str]:
    """Écarts entre deux sorties ; les flottants sont comparés à FLOAT_TOLERANCE près."""
    if isinstance(expected, float) or isinstance(actual, float):
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            close = math.isclose(expected, actual, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE)
            return [] if close else [f"{where}: {expected!r} != {actual!r}"]
        return [f"{where}: {expected!r} != {actual!r}"]
    if isinstance(expected, dict) and isinstance(actual, dict):
        out = [f"{where}.{k}: clé absente" for k in expected.keys() - actual.keys()]
        out += [f"{where}.{k}: clé en trop" for k in actual.keys() - expected.keys()]
        for k in expected.keys() & actual.keys():
            out += differences(expected[k], actual[k], f"{where}.{k}")
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{where}: longueur {len(expected)} != {len(actual)}"]
        return [
            d
            for i, (e, a) in enumerate(zip(expected, actual, strict=True))
            for d in differences(e, a, f"{where}[{i}]")
        ]
    return [] if expected == actual else [f"{where}: {expected!r} != {actual!r}"]
