"""Rejoue les cas de `cases/` sur hannibal_core et rend des sorties JSON.

Les sorties figées dans `golden/` décrivent le comportement à conserver. Elles ont été enregistrées
sur l'ancien code avant sa suppression (ADR 0002), puis ajustées pour les écarts voulus du README.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from hannibal_core import grounding
from hannibal_core import signals as interpreter
from hannibal_core.fleet import FleetController
from hannibal_core.orders import grammar as mtp
from hannibal_core.orders import kinematics as sim
from hannibal_core.orders import mtp_mapping as bridge
from hannibal_core.orders import recommendations as reco
from hannibal_core.scenario import ScenarioEngine

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCENARIOS = REPO / "apps" / "api" / "scenarios"
CASES = HERE / "cases"
GOLDEN = HERE / "golden"
FLOAT_TOLERANCE = 1e-6


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
    cases = load_cases("interpret")
    kb = interpreter.KB(HERE / cases["kb"])
    return [{"input": text, "output": canon(interpreter.interpret(text, kb))} for text in cases["texts"]]


def run_mtp() -> list[dict[str, Any]]:
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
    cases = load_cases("hxbridge")
    ships, me, speed = cases["ships"], cases["me"], cases["speed_kn"]
    alt = cases["fix_frame_me_is_ship"]

    interp_cases = load_cases("interpret")
    kb = interpreter.KB(HERE / interp_cases["kb"])
    from_interpret = []
    for text in interp_cases["texts"]:
        interp = interpreter.interpret(text, kb)
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


class _Clock:
    now = 0.0

    def time(self) -> float:
        return self.now


def run_fleet() -> list[dict[str, Any]]:
    """Boucle fermée : contrôleur à 2 Hz et physique simple (cap vers le point de route à 4°/s,
    vitesse visée par la loi de la carotte), échantillonnée pas à pas."""
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
        fleet = FleetController()
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


class ScenarioUnderTest:
    """`ScenarioEngine` sur un scénario du catalogue, avec horloge simulée et aléa initialisé."""

    def __init__(self, case: dict[str, Any], clock: _Clock) -> None:
        path = SCENARIOS / f"{case['scenario']}.yaml"
        sc = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.spawned = ScenarioEngine.initial_positions(sc)
        self.engine = ScenarioEngine(
            sc,
            case["player"],
            clock=clock.time,
            rng=random.Random(case.get("seed", 0)),  # noqa: S311
            auto=bool(case.get("auto")),
            manual=bool(case.get("manual")),
        )

    def reply(self, ship: str, yes: bool) -> dict[str, Any]:
        r = self.engine.reply(ship, yes)
        r.pop("en", None)
        return r

    def __getattr__(self, name: str) -> Any:
        return getattr(self.engine, name)


def run_scenario() -> list[dict[str, Any]]:
    """Missions complètes en boucle fermée (physique de `run_fleet`) : messages, ordres, pistes, débrief."""
    cases = load_cases("scenario")
    lat0, lon0, dt = cases["origin"]["lat"], cases["origin"]["lon"], cases["dt"]
    m = 111320.0

    def geo(x: float, y: float) -> tuple[float, float]:
        lat = lat0 + y / m
        return lat, lon0 + x / (m * math.cos(math.radians(lat)))

    def local(lat: float, lon: float) -> tuple[float, float]:
        return (lon - lon0) * m * math.cos(math.radians(lat)), (lat - lat0) * m

    out = []
    for case in cases["runs"]:
        clock = _Clock()
        clock.now = 1000.0
        eng: Any = ScenarioUnderTest(case, clock)
        run = eng.run
        cap = float(run["sc"].get("cap_initial", 0))
        ships = {n: {"x": x, "y": y, "sog": 0.0, "hdg": cap} for n, (x, y) in eng.spawned.items()}
        samples, results, msgs, seen = [], [], [], 0
        for tick in range(case["ticks"]):
            t = tick * dt
            clock.now = 1000.0 + t
            for act in case.get("actions", []):
                if act["t"] != t:
                    continue
                if "order" in act:
                    results.append([t, eng.player_order(act["order"])])
                elif "approve" in act:
                    results.append([t, eng.approve(act["approve"])])
                elif "reply" in act:
                    results.append([t, eng.reply(*act["reply"])])
                elif "classify" in act:
                    results.append([t, eng.classify(*act["classify"])])
                elif "helm" in act:
                    results.append([t, eng.helm(act["helm"])["ok"]])
                elif "auto" in act:
                    results.append([t, eng.set_auto(act["auto"])])
                elif "simulate" in act:
                    results.append([t, eng.simulate(act["simulate"])])
                elif "recommend" in act:
                    results.append([t, eng.recommend()])
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
            waypoints = eng.tick(states)
            msgs += [x for x in run["msgs"] if x["id"] > seen]
            seen = max([seen] + [x["id"] for x in run["msgs"]])
            if tick % cases["sample_every"] == 0:
                samples.append(
                    canon(
                        {
                            "t": t,
                            "waypoints": waypoints,
                            "positions": ships,
                            "group": {k: run.get(k) for k in ("gcap", "gspeed", "form", "axis", "form_key")},
                            "ships": {
                                n: {k: sh.get(k) for k in ("mode", "cap", "v", "err")}
                                for n, sh in run["ships"].items()
                            },
                            "contacts": {
                                cid: {k: c.get(k) for k in ("x", "y", "cap", "etat", "cls", "blk")}
                                for cid, c in run["contacts"].items()
                            },
                            "pending": len(run["pending"]),
                        }
                    )
                )
            if run["ended"]:
                break
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
        out.append(
            canon(
                {
                    "name": case["name"],
                    "spawn": eng.spawned,
                    "samples": samples,
                    "results": results,
                    "msgs": msgs,
                    "plog": run["plog"],
                    "drill": run["drill"],
                    "ended_at": t,
                    "state": eng.state(),
                }
            )
        )
    return out


def _fake_corpus(cases: dict[str, Any]) -> tuple[Callable[[str], bool], Callable[[str], bool]]:
    text = "\n".join(cases["corpus"])

    def lookup(word: bool) -> Callable[[str], bool]:
        def found(term: str) -> bool:
            pattern = grounding.corpus_pattern(term, word).replace("\\m", r"\b").replace("\\M", r"\b")
            return bool(pattern) and re.search(pattern, text, re.I) is not None

        return found

    return lookup(False), lookup(True)


def run_grounding() -> dict[str, Any]:
    """Contrôle d'ancrage et termes inconnus du service de doctrine, sur un corpus inventé."""
    cases = load_cases("grounding")
    in_corpus, in_corpus_word = _fake_corpus(cases)
    abbrs = [tuple(x) for x in cases["glossary"]["abbrs"]]
    words = [tuple(x) for x in cases["glossary"]["words"]]
    out: dict[str, Any] = {"grounded": [], "unknown": []}
    for c in cases["grounded"]:
        ok, why = grounding.grounded(
            c["q"],
            c["ans"],
            c["cited"],
            c.get("enq", ""),
            in_corpus=in_corpus,
            in_corpus_word=in_corpus_word,
            word=c.get("word", False),
        )
        out["grounded"].append([ok, why])
    for c in cases["unknown"]:
        out["unknown"].append(
            grounding.unknown_terms(
                c["q"],
                c.get("query_en", ""),
                in_corpus=in_corpus,
                in_corpus_word=in_corpus_word,
                suggest_for=lambda k: grounding.suggest(k, abbrs, words, in_corpus_word),
            )
        )
    out["no_answer"] = grounding.NO_ANSWER
    return out


RUNNERS: dict[str, Callable[[], Any]] = {
    "grounding": run_grounding,
    "interpret": run_interpret,
    "mtp": run_mtp,
    "fleet": run_fleet,
    "scenario": run_scenario,
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
