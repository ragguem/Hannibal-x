import copy
import random
from pathlib import Path

import pytest
import yaml
from hannibal_core.scenario import ScenarioEngine, ScenarioError, load, validate

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "apps" / "api" / "scenarios"
FILES = sorted(p.name for p in CATALOG.glob("*.yaml"))


def read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_catalog_has_the_six_scenarios() -> None:
    assert FILES == [
        "changement_formation.yaml",
        "contact_inconnu.yaml",
        "exercice_formations.yaml",
        "interception_hostile.yaml",
        "menace_ennemie.yaml",
        "transit_colonne.yaml",
    ]


@pytest.mark.parametrize("name", FILES)
def test_catalog_scenario_is_valid(name: str) -> None:
    assert validate(read(CATALOG / name)) == []


BASE = read(CATALOG / "interception_hostile.yaml")


def broken(path: str, value: object) -> dict:
    doc = copy.deepcopy(BASE)
    node = doc
    keys = path.split(".")
    for k in keys[:-1]:
        node = node[int(k)] if k.isdigit() else node[k]
    last = keys[-1]
    if value is KeyError:
        del node[last]
    elif last.isdigit():
        node[int(last)] = value
    else:
        node[last] = value
    return doc


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("schema_version", 2, "schema_version"),
        ("titre", "", "titre"),
        ("duree_s", -1, "duree_s"),
        ("cap_initial", "nord", "cap_initial"),
        ("formation_depart", "losange", "formation de départ"),
        ("flotte.1.role", "guide", "un seul guide"),
        ("flotte.1.nom", "hannibal", "double"),
        ("flotte.2.nom", "zulu", "absent des formations"),
        ("flotte.3", "delta", "nom et rôle"),
        ("evenements.0.piste.vit_kn", KeyError, "vit_kn"),
        ("evenements.0.piste.cls_reel", "rouge", "classe réelle"),
        ("evenements.0.piste.rapports_nm", ["loin"], "rapports_nm"),
        ("evenements.1.apres_repousse", "TRK999", "inconnue"),
        ("evenements.0.t", "tôt", "t doit"),
        ("attendu.0.cls", "rouge", "classe inconnue"),
        ("attendu.1.repousse", "TRK999", "inconnue"),
        ("attendu.2", {"texte": "x"}, "attendu"),
        ("attendu.3", "rien", "texte attendu"),
    ],
)
def test_invalid_documents_are_rejected(path: str, value: object, message: str) -> None:
    errors = validate(broken(path, value))
    assert any(message in e for e in errors), errors
    with pytest.raises(ScenarioError):
        load(broken(path, value))


def test_invalid_events_orders_and_steps() -> None:
    assert validate([]) == ["le document doit être un dictionnaire"]
    doc = read(CATALOG / "contact_inconnu.yaml")
    doc["evenements"] += [
        {"t": 5, "de": "zulu", "a": "yankee", "ordres": [{"type": "JUMP"}, {"type": "TURN", "deg": 30}]},
        {"t": 6, "de": "hannibal", "a": "TOUS", "ordres": []},
        {"t": 7},
        {"de": "hannibal"},
        {"piste": {"id": "X"}},
        "rien",
    ]
    doc["attendu"].append({"texte": "x", "ordre": "JUMP"})
    doc["etapes"] = [{"key": "column"}, {"rel_tens": []}]
    doc["etapes_aleatoires"] = 0
    text = " | ".join(validate(doc))
    for part in (
        "émetteur inconnu",
        "destinataire inconnu",
        "JUMP",
        "« side » manquant",
        "ordres manquants",
        "piste ou ordres",
        "t ou apres_repousse",
        "dictionnaire attendu",
        "ordre connu",
        "etapes[0]",
        "etapes[1]",
        "etapes_aleatoires",
    ):
        assert part in text
    assert "flotte manquante" in validate({**doc, "flotte": []})
    assert "evenements doit être une liste" in validate({**doc, "evenements": {}})
    assert "attendu doit être une liste" in validate({**doc, "attendu": {}})
    assert "etapes doit être une liste non vide" in validate({**doc, "etapes": []})


class Clock:
    now = 50.0

    def __call__(self) -> float:
        return self.now


def engine(name: str, player: str, **kw: object) -> tuple[ScenarioEngine, Clock]:
    clock = Clock()
    rng = random.Random(1)  # noqa: S311
    return ScenarioEngine(load(read(CATALOG / name)), player, clock=clock, rng=rng, **kw), clock


def states_at(sc: dict) -> dict:
    cap = float(sc.get("cap_initial", 0))
    return {
        n: {"x": x, "y": y, "lat": 43.0, "lon": 6.0, "sog": 6.0, "hdg": cap}
        for n, (x, y) in ScenarioEngine.initial_positions(sc).items()
    }


def test_engine_runs_without_io_and_finishes() -> None:
    eng, clock = engine("transit_colonne.yaml", "alfa")
    st = states_at(eng.run["sc"])
    assert eng.run["msgs"][0]["fr"].endswith("escorte du guide HANNIBAL.")
    wp = eng.tick(st)
    assert set(wp) == {"hannibal", "alfa", "charlie", "delta"}
    assert eng.player_order("CHARLIE CORPEN 090")["error"] == "Seul le guide peut ordonner à un autre navire."
    assert eng.player_order("BONJOUR")["ok"] is False
    assert eng.reply("charlie", True)["ok"] is False
    assert eng.helm({"cap": 10})["ok"] is False
    assert eng.classify("TRK1", "hostile") is False
    assert eng.simulate("ALFA FORM 1")["ok"] is False
    assert eng.simulate("BONJOUR")["ok"] is False
    clock.now += 10_000
    eng.tick(st)
    assert eng.run["ended"]
    assert eng.run["debrief"]["total"] == len(eng.run["sc"]["attendu"])
    assert eng.tick(st) == {}


def test_drill_uses_the_injected_random() -> None:
    a, _ = engine("exercice_formations.yaml", "hannibal")
    b, _ = engine("exercice_formations.yaml", "hannibal")
    assert a.run["drill"]["steps"] == b.run["drill"]["steps"]
    assert len(a.run["drill"]["steps"]) == 5


def test_manual_helm_and_guide_plan() -> None:
    eng, clock = engine("transit_colonne.yaml", "hannibal", manual=True)
    st = states_at(eng.run["sc"])
    assert eng.helm({"rudder": 3, "dcap": 5, "dkn": 40})["helm"]["kn"] == 29.0
    assert eng.helm({"kn": -1})["helm"]["kn"] == 0.0
    clock.now += 60
    eng.tick(st)
    assert [m["kind"] for m in eng.run["msgs"]][-1] == "plan"
    assert eng.state()["station"] is None
