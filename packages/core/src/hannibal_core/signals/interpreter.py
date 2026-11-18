#!/usr/bin/env python3
"""Interpreteur deterministe : message radio (texte) -> signal MTP + reference.

Aucune IA ici. Le message est normalise, la trame radio est retiree, le groupe
de signal est reconstruit puis cherche dans kb/signals.json. Le sens renvoye est
le texte exact de la publication. Tout ce qui n'est pas trouve est signale comme
tel, jamais devine.

Usage en ligne de commande :
    python interpret.py kb/signals.json "CHARLIE THIS IS HANNIBAL TURN STARBOARD NINER OVER"

Usage en module :
    from interpret import KB, interpret
    kb = KB("kb/signals.json")
    res = interpret("...", kb)

Statuts renvoyes :
    ok                 signal trouve (params eventuels dans res["params"])
    unknown_signal     groupe absent de la publication
    spare              code present mais sans sens attribue
    not_releasable     contenu non diffuse dans cette edition
    invalid_parameter  parametre hors limites
    missing_parameter  parametre obligatoire absent (bord PORT/STBD)
    empty              aucun signal dans le message
"""

import json
import re
from pathlib import Path
from typing import Any

LETTERS = {
    "ALFA": "A",
    "ALPHA": "A",
    "BRAVO": "B",
    "CHARLIE": "C",
    "DELTA": "D",
    "ECHO": "E",
    "FOXTROT": "F",
    "GOLF": "G",
    "HOTEL": "H",
    "INDIA": "I",
    "JULIETT": "J",
    "JULIET": "J",
    "KILO": "K",
    "LIMA": "L",
    "MIKE": "M",
    "NOVEMBER": "N",
    "OSCAR": "O",
    "PAPA": "P",
    "QUEBEC": "Q",
    "ROMEO": "R",
    "SIERRA": "S",
    "TANGO": "T",
    "UNIFORM": "U",
    "VICTOR": "V",
    "WHISKEY": "W",
    "WHISKY": "W",
    "XRAY": "X",
    "X-RAY": "X",
    "YANKEE": "Y",
    "ZULU": "Z",
}
DIGITS = {
    "ZERO": "0",
    "ONE": "1",
    "TWO": "2",
    "THREE": "3",
    "TREE": "3",
    "FOUR": "4",
    "FOWER": "4",
    "FIVE": "5",
    "FIFE": "5",
    "FOR": "4",
    "TOO": "2",
    "WON": "1",
    "ATE": "8",
    "OH": "0",
    "SIX": "6",
    "SEVEN": "7",
    "EIGHT": "8",
    "NINE": "9",
    "NINER": "9",
}
WORDS = {
    "EMERGENCY": "EMERG",
    "EMERG": "EMERG",
    "FORMATION": "FORM",
    "FORM": "FORM",
    "INTERROGATIVE": "INT",
    "INT": "INT",
    "STARBOARD": "STBD",
    "STARBORD": "STBD",
    "STBD": "STBD",
    "PORT": "PORT",
    "ANSWER": "ANS",
    "ANS": "ANS",
    "NEGAT": "NEGAT",
    "DESIG": "DESIG",
    "TACK": "TACK",
    "CORPEN": "CORPEN",
    "CORP": "CORPEN",
    "CORPIN": "CORPEN",
    "CORPAN": "CORPEN",
    "CORPON": "CORPEN",
    "TURN": "TURN",
    "SPEED": "SPEED",
    "STATION": "STATION",
    "SCREEN": "SCREEN",
}
KEYWORDS = {"FORM", "STATION", "TURN", "CORPEN", "SPEED", "SCREEN", "EMERG"}
# nombres dits "comme dans la vie courante" (hors procedure, mais frequents) : fifteen, twenty five
TEENS = {
    "TEN": "10",
    "ELEVEN": "11",
    "TWELVE": "12",
    "THIRTEEN": "13",
    "FOURTEEN": "14",
    "FIFTEEN": "15",
    "SIXTEEN": "16",
    "SEVENTEEN": "17",
    "EIGHTEEN": "18",
    "NINETEEN": "19",
}
TENS = {
    "TWENTY": 20,
    "THIRTY": 30,
    "FORTY": 40,
    "FIFTY": 50,
    "SIXTY": 60,
    "SEVENTY": 70,
    "EIGHTY": 80,
    "NINETY": 90,
}
SIDES = {"PORT", "STBD"}
# en-tetes a parametres : (mot-cle, forme) -> en-tete de la publication
RANGE_HEADS = {
    ("TURN", "side_num"): "TURN [PORT or STBD] [1 to 36] or [000 to 359]",
    ("CORPEN", "side_num"): "CORPEN [PORT or STBD] [1 to 18] or [000 to 359]",
}


def compact(code):
    """Cle de recherche : 'MW 40' -> 'MW40', 'AV26*' -> 'AV26'."""
    code = code.replace("*", "")
    return re.sub(r"^([A-Z]{2}) (\d+)$", r"\1\2", code)


class KB:
    def __init__(self, path):
        self.signals = json.loads(Path(path).read_text("utf-8"))
        self.by_code: dict[str, list[dict[str, Any]]] = {}
        for s in self.signals:
            self.by_code.setdefault(compact(s["signal"]), []).append(s)
        self.heads = set(self.by_code)

    def get(self, code):
        return self.by_code.get(code, [])

    def find_head(self, prefix_regex):
        rx = re.compile(prefix_regex)
        return [s for s in self.signals if rx.match(s["signal"])]


# ------------------------------------------------------------ normalisation
def normalize(text):
    t = text.upper().replace("X-RAY", "XRAY").replace("X RAY", "XRAY").replace("STAND BY", "STANDBY")
    t = re.sub(r"[^A-Z0-9 ]", " ", t)  # "3-2", "8-Niner" : le tiret separe des chiffres
    return [w for w in t.split() if w]


def strip_frame(tokens):
    """Retire appel, mots de procedure et fin. -> (to, sender, method, corps, avertissements)."""
    warn, to, sender, method = [], None, None, "plain"
    t = list(tokens)
    if "THIS" in t and t.index("THIS") + 1 < len(t) and t[t.index("THIS") + 1] == "IS":
        i = t.index("THIS")
        to = " ".join(t[:i]) or None
        sender = t[i + 2] if i + 2 < len(t) else None
        t = t[i + 3 :]
    while t and t[-1] in ("OVER", "OUT"):
        t.pop()
    s = " ".join(t)
    if s.startswith("EXECUTE TO FOLLOW"):
        method, s = "execute_to_follow", s[len("EXECUTE TO FOLLOW") :].strip()
    elif s.startswith("IMMEDIATE EXECUTE"):
        method, s = "immediate_execute", s[len("IMMEDIATE EXECUTE") :].strip()
    s = re.sub(r"\s*STANDBY( EXECUTE)?$", "", s).strip()
    s = re.sub(r"\s*EXECUTE$", "", s).strip()
    if " I SAY AGAIN " in f" {s} ":
        first, _, second = s.partition("I SAY AGAIN")
        first, second = first.strip(), second.strip()
        if second and to_atoms(first.split()) != to_atoms(second.split()):
            warn.append("La repetition apres I SAY AGAIN ne correspond pas au premier enonce.")
        s = first
    return to, sender, method, s.split(), warn


def to_atoms(tokens):
    """Mots parles ou ecrits -> atomes ('K',mot) ('L',lettre) ('D',chiffres) ('S',bord) ('W',mot)."""
    atoms = []
    toks, tokens, i = list(tokens), [], 0
    while i < len(toks):  # "TWENTY FIVE" -> "25", "FIFTEEN" -> "15"
        w = toks[i]
        if w in TENS:
            unit = (
                DIGITS.get(toks[i + 1]) if i + 1 < len(toks) and toks[i + 1] not in ("ZERO", "OH") else None
            )
            if unit and len(toks[i + 1]) > 1:
                tokens.append(str(TENS[w] + int(unit)))
                i += 2
                continue
            tokens.append(str(TENS[w]))
        elif w in TEENS:
            tokens.append(TEENS[w])
        else:
            tokens.append(w)
        i += 1
    for w in tokens:
        if w in WORDS:
            v = WORDS[w]
            atoms.append(("K" if v in KEYWORDS else "S" if v in SIDES else "W", v))
        elif w in LETTERS:
            atoms.append(("L", LETTERS[w]))
        elif w in DIGITS:
            atoms.append(("D", DIGITS[w]))
        elif re.fullmatch(r"\d+", w):
            atoms.append(("D", w))
        elif re.fullmatch(r"[A-Z]", w):
            atoms.append(("L", w))
        elif re.fullmatch(r"[A-Z]{2}\d{1,3}", w):  # ecrit : AD4
            atoms += [("L", w[0]), ("L", w[1]), ("D", w[2:])]
        elif re.fullmatch(r"[A-Z]{2}", w):  # ecrit : BA, MW
            atoms += [("L", w[0]), ("L", w[1])]
        elif re.fullmatch(r"\d[A-Z]", w):  # ecrit : 7C
            atoms += [("D", w[0]), ("L", w[1])]
        else:
            atoms.append(("?", w))
    merged: list[tuple[str, str]] = []
    for kind, v in atoms:  # chiffres consecutifs -> un nombre
        if kind == "D" and merged and merged[-1][0] == "D":
            merged[-1] = ("D", merged[-1][1] + v)
        else:
            merged.append((kind, v))
    return merged


# ------------------------------------------------------------ recherche
def _result(status, **kw):
    r = {
        "status": status,
        "signal": None,
        "signal_id": None,
        "meaning": None,
        "reference": None,
        "params": {},
        "extra": [],
        "warnings": [],
        "candidates": [],
    }
    r.update(kw)
    return r


def _from_entries(entries, code, params=None, extra=None):
    assigned = [e for e in entries if e["status"] == "assigned"]
    if not entries:
        return _result("unknown_signal", signal=code)
    if not assigned:
        e = entries[0]
        return _result(e["status"], signal=e["signal"], signal_id=e["id"], reference=e["reference"])
    e = assigned[0]
    r = _result(
        "ok",
        signal=e["signal"],
        signal_id=e["id"],
        meaning=e["full_text"],
        reference=e["reference"],
        params=params or {},
        extra=extra or [],
        candidates=[
            {"signal_id": x["id"], "reference": x["reference"], "meaning": x["full_text"]} for x in assigned
        ],
    )
    if len(assigned) > 1:
        r["warnings"].append(
            f"Le code {code} figure {len(assigned)} fois dans la publication : voir les references proposees."
        )
    if e.get("contains_not_releasable"):
        r["warnings"].append("Une partie de ce signal est NOT RELEASABLE dans cette edition.")
    if e["blanks"] and not (params or extra):
        r["warnings"].append(f"Le sens comporte {e['blanks']} element(s) a preciser, non fournis.")
    return r


def lookup(atoms, kb):
    """Reconnait le groupe en tete des atomes."""
    if not atoms:
        return _result("empty")
    kinds = "".join(k for k, _ in atoms)
    vals = [v for _, v in atoms]
    rest = lambda n: [v for _, v in atoms[n:]]

    # INT + mot-cle
    if kinds.startswith("WK") and vals[0] == "INT":
        return _from_entries(kb.get(f"INT {vals[1]}"), f"INT {vals[1]}", extra=rest(2))
    # lettre + mot-cle (signal d'information) : "A SPEED"
    if kinds.startswith("LK"):
        code = f"{vals[0]} {vals[1]}"
        ents = kb.get(code) or kb.find_head(rf"^{vals[0]} {vals[1]}( |$)")
        return _from_entries(ents, code, extra=rest(2))
    if kinds.startswith("K"):
        kw = vals[0]
        # mot-cle + lettre : "TURN A", "EMERG C"
        if kinds.startswith("KL"):
            if kinds.startswith("KLD") and kb.get(f"{kw} {vals[1]}{vals[2]}"):  # "SPEED R2"
                code = f"{kw} {vals[1]}{vals[2]}"
                return _from_entries(kb.get(code), code, extra=rest(3))
            code = f"{kw} {vals[1]}"
            ents = kb.get(code) or kb.find_head(rf"^{re.escape(code)}( [\[(]|$| PORT)")
            return _from_entries(ents, code, extra=rest(2))
        # mot-cle + bord + nombre : TURN/CORPEN
        if kinds.startswith("KS") and kw in ("TURN", "CORPEN"):
            head = RANGE_HEADS[(kw, "side_num")]
            mx = 36 if kw == "TURN" else 18
            if kinds.startswith("KSD"):
                num = vals[2]
                if len(num) == 3:
                    if int(num) > 359:
                        return _result(
                            "invalid_parameter",
                            signal=head,
                            warnings=[f"Cap {num} hors limites (000 a 359)."],
                        )
                    p = {"side": vals[1], "true_course": int(num)}
                else:
                    if not 1 <= int(num) <= mx:
                        return _result(
                            "invalid_parameter",
                            signal=head,
                            warnings=[f"Valeur {num} hors limites (1 a {mx} dizaines de degres)."],
                        )
                    p = {
                        "side": vals[1],
                        "relative_tens_of_degrees": int(num),
                        "relative_degrees": int(num) * 10,
                    }
                    if len(atoms) > 3 and vals[3] == "ANS":
                        p["relative_degrees"] += 5
                return _from_entries(kb.get(head), head, params=p, extra=rest(3))
            return _from_entries(kb.get(f"{kw} {vals[1]}"), f"{kw} {vals[1]}", extra=rest(2))
        if kinds.startswith("KD") and kw in ("TURN", "CORPEN"):
            return _result(
                "missing_parameter",
                signal=RANGE_HEADS[(kw, "side_num")],
                warnings=["Le bord (PORT ou STBD) doit etre indique."],
            )
        # relevement relatif : FORM/STATION/EMERG + bord + 0..18
        if kinds.startswith("KSD") and kw in ("FORM", "STATION", "EMERG"):
            ents = kb.find_head(rf"^{kw} [\[(]PORT or STBD[\])] [\[(]0 to 18[\])]$")
            if not 0 <= int(vals[2]) <= 18:
                return _result(
                    "invalid_parameter",
                    signal=ents[0]["signal"] if ents else kw,
                    warnings=[f"Valeur {vals[2]} hors limites (0 a 18)."],
                )
            p = {
                "side": vals[1],
                "relative_bearing_tens_of_degrees": int(vals[2]),
                "relative_bearing_degrees": int(vals[2]) * 10,
            }
            return _from_entries(ents, f"{kw} {vals[1]} {vals[2]}", params=p, extra=rest(3))
        if kinds.startswith("KD"):
            num = vals[1]
            if kw == "SPEED":
                if num == "0":
                    return _from_entries(kb.get("SPEED 0"), "SPEED 0", extra=rest(2))
                return _from_entries(
                    kb.get("SPEED"), "SPEED", params={"speed_knots": int(num)}, extra=rest(2)
                )
            if len(num) == 3 and kw in ("FORM", "STATION", "EMERG"):
                ents = kb.find_head(rf"^{kw} [\[(]000 to 359[\])]$")
                if int(num) > 359:
                    return _result(
                        "invalid_parameter",
                        signal=ents[0]["signal"] if ents else kw,
                        warnings=[f"Relevement {num} hors limites (000 a 359)."],
                    )
                return _from_entries(ents, f"{kw} {num}", params={"true_bearing": int(num)}, extra=rest(2))
            exact = kb.get(f"{kw} {num}")
            if exact:
                return _from_entries(exact, f"{kw} {num}", extra=rest(2))
            if kw == "FORM":
                for s in kb.find_head(r"^FORM \d+ to \d+$"):
                    lo, hi = map(int, re.findall(r"\d+", s["signal"]))
                    if lo <= int(num) <= hi:
                        return _from_entries(
                            [s], s["signal"], params={"formation_number": int(num)}, extra=rest(2)
                        )
            return _result("unknown_signal", signal=f"{kw} {num}")
        return _from_entries(kb.get(kw), kw, extra=rest(1))  # mot-cle seul
    # vocabulaire principal : deux lettres + nombre
    if kinds.startswith("LLD"):
        code = f"{vals[0]}{vals[1]}{vals[2]}"
        return _from_entries(kb.get(code), code, extra=rest(3))
    # table d'action : chiffre + lettre
    if kinds.startswith("DL") and len(vals[0]) == 1:
        code = f"{vals[0]}{vals[1]}"
        return _from_entries(kb.get(code), code, extra=rest(2))
    # groupe de deux lettres (groupes directeurs, indicateurs de position)
    if kinds.startswith("LL"):
        code = f"{vals[0]}{vals[1]}"
        return _from_entries(kb.get(code), code, extra=rest(2))
    return _result("unknown_signal", signal=" ".join(vals))


def split_groups(atoms):
    """Plusieurs signaux dans un meme message : coupe sur TACK et devant chaque mot-cle."""
    groups: list[list[tuple[str, str]]] = []
    cur: list[tuple[str, str]] = []
    for k, v in atoms:
        if k == "W" and v == "TACK":
            if cur:
                groups.append(cur)
                cur = []
            continue
        if k == "K" and cur:
            info = len(cur) == 1 and cur[0][0] == "L"  # "A SPEED" : signal d'information
            interrogative = len(cur) == 1 and cur[0] == ("W", "INT")
            if not info and not interrogative:
                groups.append(cur)
                cur = []
        cur.append((k, v))
    if cur:
        groups.append(cur)
    return groups or [[]]


def interpret(text, kb):
    to, sender, method, body, warn = strip_frame(normalize(text))
    atoms = to_atoms(body)
    results = []
    for g in split_groups(atoms):
        r = lookup(g, kb)
        if r["extra"]:
            r["warnings"].append("Elements a la suite du groupe, non interpretes : " + " ".join(r["extra"]))
        r["written_signal"] = " ".join(v for _, v in g)
        results.append(r)
    res = dict(results[0])
    bad = next((r for r in results if r["status"] != "ok"), None)
    if bad is not None and len(results) > 1:
        res["status"] = bad["status"]
    unknown = [v for k, v in atoms if k == "?"]
    if unknown:
        warn.append("Mots non reconnus : " + " ".join(unknown))
    res.update({"to": to, "from": sender, "method": method, "written_signal": " ".join(v for _, v in atoms)})
    res["warnings"] = warn + [w for r in results for w in r["warnings"]]
    res["groups"] = [
        {
            k: r.get(k)
            for k in (
                "status",
                "signal",
                "signal_id",
                "meaning",
                "reference",
                "params",
                "extra",
                "warnings",
                "written_signal",
            )
        }
        for r in results
    ]
    return res
