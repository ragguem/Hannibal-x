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


CORE_MODULES = {
    "interpret": "hannibal_core.signals",
    "mtp": "hannibal_core.orders.grammar",
    "sim": "hannibal_core.orders.kinematics",
    "reco": "hannibal_core.orders.recommendations",
    "hxbridge": "hannibal_core.orders.mtp_mapping",
}
IMPLEMENTATIONS = ("legacy", "core")


def load(name: str, impl: str) -> ModuleType:
    """Module de l'ancien code ou son équivalent dans hannibal_core."""
    return legacy_module(name) if impl == "legacy" else importlib.import_module(CORE_MODULES[name])


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


def run_interpret(impl: str = "legacy") -> list[dict[str, Any]]:
    interpret = load("interpret", impl)
    cases = load_cases("interpret")
    kb = interpret.KB(HERE / cases["kb"])
    return [{"input": text, "output": canon(interpret.interpret(text, kb))} for text in cases["texts"]]


def run_mtp(impl: str = "legacy") -> list[dict[str, Any]]:
    mtp = load("mtp", impl)
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


def run_sim(impl: str = "legacy") -> dict[str, Any]:
    sim = load("sim", impl)
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


def run_reco(impl: str = "legacy") -> list[dict[str, Any]]:
    reco = load("reco", impl)
    return [
        canon(
            {
                "input": s["name"],
                "output": reco.recommend(s["state"], s["player"], s["guide"], s["pending"], s["reported"]),
            }
        )
        for s in load_cases("reco")["scenarios"]
    ]


def run_hxbridge(impl: str = "legacy") -> dict[str, Any]:
    bridge = load("hxbridge", impl)
    interpret = load("interpret", impl)
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


def legacy_server() -> ModuleType:
    """`legacy/app_v3/server.py` importé avec ROS remplacé par des bouchons (seul le calcul est exercé)."""
    if "server" in sys.modules:
        return sys.modules["server"]

    class Msg:
        def __init__(self, **kw: Any) -> None:
            self.__dict__.update(kw)

    class SetWaypoints:
        Request = Msg

    stubs = {
        "rclpy": {},
        "rclpy.node": {"Node": object},
        "rclpy.action": {"ActionClient": object},
        "rclpy.executors": {"SingleThreadedExecutor": object},
        "geographic_msgs": {},
        "geographic_msgs.msg": {"GeoPoint": Msg},
        "geometry_msgs": {},
        "geometry_msgs.msg": {"Pose": Msg},
        "lotusim_msgs": {},
        "lotusim_msgs.msg": {"VesselPositionArray": Msg, "MASCmd": Msg},
        "lotusim_msgs.action": {"MASCmdArray": Msg},
        "lotusim_msgs.srv": {"SetWaypoints": SetWaypoints},
    }
    saved = {name: sys.modules.get(name) for name in stubs}
    for name, attrs in stubs.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module
    try:
        return legacy_module("server")
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class _Clock:
    now = 0.0

    def time(self) -> float:
        return self.now


class _WaypointClient:
    def __init__(self, sent: dict[str, tuple[float, float]], name: str) -> None:
        self.sent, self.name = sent, name

    def call_async(self, req: Any) -> None:
        self.sent[self.name] = (req.path[0].latitude, req.path[0].longitude)


class LegacyFleet:
    """Même interface que `hannibal_core.fleet.FleetController`, branchée sur l'ancien serveur."""

    def __init__(self) -> None:
        import threading

        srv = legacy_server()
        self.clock = _Clock()
        srv.time = self.clock  # type: ignore[attr-defined]
        self.ros = object.__new__(srv.Ros)
        self.ros.st, self.ros.cli, self.ros.lock = {}, {}, threading.RLock()
        self.hannibal = object.__new__(srv.Hannibal)
        self.hannibal.ros = self.ros
        self.sent: dict[str, tuple[float, float]] = {}

    def turn_side(self, name: str, sign: int, deg: float) -> None:
        self.ros.turn_side(name, sign, deg)

    def control(
        self, run: dict[str, Any], states: dict[str, Any], now: float
    ) -> dict[str, tuple[float, float]]:
        self.clock.now = now
        self.ros.st = states
        for name in run["ships"]:
            self.ros.cli.setdefault(name, _WaypointClient(self.sent, name))
        self.sent.clear()
        self.hannibal.control(run)
        return dict(self.sent)


def _fleet_controller(impl: str) -> Any:
    if impl == "legacy":
        return LegacyFleet()
    from hannibal_core.fleet import FleetController

    return FleetController()


def run_fleet(impl: str = "legacy") -> list[dict[str, Any]]:
    """Boucle fermée : contrôleur à 2 Hz et physique simple commune (cap vers le point de route à 4°/s,
    vitesse visée par la loi de la carotte), pour comparer les deux implémentations pas à pas."""
    cases = load_cases("fleet")
    lat0, lon0, dt = cases["origin"]["lat"], cases["origin"]["lon"], cases["dt"]
    m = 111320.0

    def geo(x: float, y: float) -> tuple[float, float]:
        lat = lat0 + y / m
        return lat, lon0 + x / (m * math.cos(math.radians(lat)))

    def local(lat: float, lon: float) -> tuple[float, float]:
        return (lon - lon0) * m * math.cos(math.radians(lat)), (lat - lat0) * m

    out = []
    for sc in cases["scenarios"]:
        fleet = _fleet_controller(impl)
        run = json.loads(json.dumps(sc["run"]))
        run["ships"] = {n: {"mode": "formation", "dI": 0.0, "cap": 0.0, "v": 0.0} for n in sc["ships"]}
        ships = {n: dict(s) for n, s in sc["ships"].items()}
        samples = []
        for tick in range(sc["ticks"]):
            t = tick * dt
            for ev in sc["events"]:
                if ev["t"] != t:
                    continue
                if "turn_side" in ev:
                    fleet.turn_side(*ev["turn_side"])
                elif "helm" in ev:
                    run["helm"].update(ev["helm"])
                elif "ship" in ev:
                    run["ships"][ev["ship"]].update(ev["set"])
                else:
                    run.update(ev["set"])
            states = {}
            for n, s in ships.items():
                lat, lon = geo(s["x"], s["y"])
                states[n] = {
                    "x": s["x"],
                    "y": s["y"],
                    "lat": lat,
                    "lon": lon,
                    "sog": s["sog"],
                    "hdg": s["hdg"],
                }
            waypoints = fleet.control(run, states, 1000.0 + t)
            if tick % cases["sample_every"] == 0:
                samples.append(
                    canon(
                        {
                            "t": t,
                            "waypoints": waypoints,
                            "ships": {
                                n: {k: run["ships"][n].get(k) for k in ("dI", "err", "slot")} for n in ships
                            },
                            "positions": ships,
                        }
                    )
                )
            for n, (wlat, wlon) in waypoints.items():
                s = ships[n]
                wx, wy = local(wlat, wlon)
                dist = math.hypot(wx - s["x"], wy - s["y"])
                brg = math.degrees(math.atan2(wx - s["x"], wy - s["y"])) % 360
                turn = ((brg - s["hdg"] + 540.0) % 360.0) - 180.0
                s["hdg"] = (s["hdg"] + max(-4.0 * dt, min(4.0 * dt, turn))) % 360
                target = 1.6 + 0.414 * dist
                s["sog"] += max(-0.4 * dt, min(0.4 * dt, target - s["sog"]))
            for s in ships.values():
                r = math.radians(s["hdg"])
                s["x"] += s["sog"] * math.sin(r) * dt
                s["y"] += s["sog"] * math.cos(r) * dt
        out.append({"name": sc["name"], "samples": samples, "gtrack": len(run.get("gtrack", []))})
    return out


RUNNERS: dict[str, Callable[[str], Any]] = {
    "interpret": run_interpret,
    "mtp": run_mtp,
    "fleet": run_fleet,
    "sim": run_sim,
    "reco": run_reco,
    "hxbridge": run_hxbridge,
}


def golden_path(name: str, impl: str = "legacy") -> Path:
    """`golden/core/<nom>.json` fige un écart voulu du cœur (README, « Écarts voulus »)."""
    override = GOLDEN / "core" / f"{name}.json"
    return override if impl == "core" and override.exists() else GOLDEN / f"{name}.json"


def read_golden(name: str, impl: str = "legacy") -> Any:
    return json.loads(golden_path(name, impl).read_text(encoding="utf-8"))


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
