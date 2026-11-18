"""Schéma des scénarios (`schema_version: 1`) : validation d'un document YAML déjà lu."""

from typing import Any

from hannibal_core.fleet.control import FORMS

SCHEMA_VERSION = 1
ROLES = ("guide", "escorte")
CLASSES = ("ami", "neutre", "hostile", "inconnu")
ORDER_FIELDS: dict[str, tuple[str, ...]] = {
    "CORPEN": ("cap",),
    "TURN": ("deg", "side"),
    "SPEED": ("kn",),
    "FORM": ("name",),
    "RESUME": (),
    "EMERG": ("text",),
    "ACK": ("text",),
}
TRACK_FIELDS = ("id", "type", "rel", "dist_nm", "cap", "vit_kn")


class ScenarioError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("scénario invalide : " + " ; ".join(errors))
        self.errors = errors


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _track(p: Any, where: str, err: list[str]) -> str | None:
    if not isinstance(p, dict):
        err.append(f"{where} : piste attendue")
        return None
    err += [f"{where} : champ « {k} » manquant" for k in TRACK_FIELDS if k not in p]
    if p.get("cls_reel", "inconnu") not in CLASSES:
        err.append(f"{where} : classe réelle inconnue « {p['cls_reel']} »")
    if not all(_num(d) for d in p.get("rapports_nm", [])):
        err.append(f"{where} : rapports_nm doit être une liste de distances")
    return p.get("id")


def validate(doc: Any) -> list[str]:
    """Liste des erreurs (vide si le document est valide)."""
    if not isinstance(doc, dict):
        return ["le document doit être un dictionnaire"]
    err: list[str] = []
    if doc.get("schema_version") != SCHEMA_VERSION:
        err.append(f"schema_version doit valoir {SCHEMA_VERSION}")
    for k in ("id", "titre", "niveau", "resume", "briefing"):
        if not isinstance(doc.get(k), str) or not doc[k].strip():
            err.append(f"champ texte « {k} » manquant")
    if not _num(doc.get("duree_s")) or doc["duree_s"] <= 0:
        err.append("duree_s doit être un nombre positif")
    for k in ("cap_initial", "vitesse_initiale_kn", "etapes_delai_s"):
        if k in doc and not _num(doc[k]):
            err.append(f"{k} doit être un nombre")
    f0 = doc.get("formation_depart", "column")
    if f0 not in FORMS:
        err.append(f"formation de départ inconnue « {f0} »")
    fleet = doc.get("flotte")
    names: list[str] = []
    if not isinstance(fleet, list) or not fleet:
        err.append("flotte manquante")
    else:
        for i, f in enumerate(fleet):
            if not isinstance(f, dict) or f.get("role") not in ROLES or not isinstance(f.get("nom"), str):
                err.append(f"flotte[{i}] : nom et rôle (guide ou escorte) attendus")
                continue
            names.append(f["nom"])
            if f0 in FORMS and f["nom"] not in FORMS[f0]:
                err.append(f"flotte[{i}] : navire « {f['nom']} » absent des formations")
        if sum(1 for f in fleet if isinstance(f, dict) and f.get("role") == "guide") != 1:
            err.append("la flotte doit avoir un seul guide")
        if len(set(names)) != len(names):
            err.append("noms de navires en double")
    tracks: set[str] = set()
    events = doc.get("evenements", [])
    if not isinstance(events, list):
        err.append("evenements doit être une liste")
        events = []
    for i, e in enumerate(events):
        w = f"evenements[{i}]"
        if not isinstance(e, dict):
            err.append(f"{w} : dictionnaire attendu")
            continue
        if "t" in e and not _num(e["t"]):
            err.append(f"{w} : t doit être un nombre")
        if "piste" in e:
            if "t" not in e and "apres_repousse" not in e:
                err.append(f"{w} : t ou apres_repousse attendu")
            tid = _track(e["piste"], w, err)
            if tid:
                tracks.add(tid)
        elif "t" in e:
            for k in ("de", "a"):
                if k not in e:
                    err.append(f"{w} : champ « {k} » manquant")
            if e.get("de") not in names:
                err.append(f"{w} : émetteur inconnu « {e.get('de')} »")
            if e.get("a") != "TOUS" and e.get("a") not in names:
                err.append(f"{w} : destinataire inconnu « {e.get('a')} »")
            orders = e.get("ordres")
            if not isinstance(orders, list) or not orders:
                err.append(f"{w} : ordres manquants")
                continue
            for j, o in enumerate(orders):
                t = o.get("type") if isinstance(o, dict) else None
                if t not in ORDER_FIELDS:
                    err.append(f"{w}.ordres[{j}] : type d'ordre inconnu « {t} »")
                    continue
                err += [f"{w}.ordres[{j}] : champ « {k} » manquant" for k in ORDER_FIELDS[t] if k not in o]
        else:
            err.append(f"{w} : piste ou ordres attendus")
    for i, e in enumerate(events):
        if isinstance(e, dict) and "apres_repousse" in e and e["apres_repousse"] not in tracks:
            err.append(f"evenements[{i}] : piste « {e['apres_repousse']} » inconnue")
    goals = doc.get("attendu", [])
    for i, a in enumerate(goals if isinstance(goals, list) else []):
        w = f"attendu[{i}]"
        if not isinstance(a, dict) or not isinstance(a.get("texte"), str):
            err.append(f"{w} : texte attendu")
            continue
        if "repousse" in a:
            ref = a["repousse"]
        elif "garde_nm" in a:
            ref = a.get("piste")
        elif "classe" in a:
            ref = a["classe"]
            if a.get("cls") not in CLASSES:
                err.append(f"{w} : classe inconnue « {a.get('cls')} »")
        elif "ordre" in a:
            ref = None
            if a["ordre"] not in ORDER_FIELDS or not _num(a.get("avant_t")):
                err.append(f"{w} : ordre connu et avant_t attendus")
        else:
            err.append(f"{w} : repousse, garde_nm, classe ou ordre attendu")
            continue
        if ref is not None and ref not in tracks:
            err.append(f"{w} : piste « {ref} » inconnue")
    if not isinstance(goals, list):
        err.append("attendu doit être une liste")
    steps = doc.get("etapes")
    if steps is not None:
        if not isinstance(steps, list) or not steps:
            err.append("etapes doit être une liste non vide")
        else:
            for i, s in enumerate(steps):
                ok = isinstance(s, dict) and (
                    all(isinstance(s.get(k), str) for k in ("key", "ordre", "texte"))
                    or (
                        isinstance(s.get("rel_tens"), list)
                        and s["rel_tens"]
                        and all(_num(x) for x in s["rel_tens"])
                    )
                )
                if not ok:
                    err.append(f"etapes[{i}] : key, ordre et texte, ou rel_tens attendus")
        n = doc.get("etapes_aleatoires")
        if n is not None and (not isinstance(n, int) or n < 1):
            err.append("etapes_aleatoires doit être un entier positif")
    return err


def load(doc: Any) -> dict[str, Any]:
    """Document validé, prêt pour `ScenarioEngine` ; lève `ScenarioError` sinon."""
    errors = validate(doc)
    if errors:
        raise ScenarioError(errors)
    return dict(doc)
