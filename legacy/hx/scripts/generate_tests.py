#!/usr/bin/env python3
"""Generateur du jeu de test HANNIBAL X a partir de la table des signaux.

Usage :
    python generate_tests.py kb/signals.json tests [--seed 7] [--per-signal 1]

Principe : le script fabrique chaque message A PARTIR de la table. La bonne
reponse (signal, sens exact, reference) est donc connue d'avance. Il produit
aussi des messages volontairement fautifs, pour verifier que le systeme signale
le probleme au lieu d'inventer une interpretation.

Sorties :
    testset.jsonl   un cas par ligne (texte parle, texte ecrit, reponse attendue)
    testset.csv     vue a plat du meme jeu
    testset_stats.json

Categories de cas :
    clean_param      signal de manoeuvre avec parametres (cap, bord, vitesse...)
    clean_fixed      signal sans blanc a remplir : message complet tel quel
    needs_params     signal dont le sens contient des blancs : seule
                     l'identification est verifiee (a completer par l'expert)
    variant_asr      meme message, orthographe "radio" differente (ALPHA, NINE...)
    err_unknown      groupe qui n'existe pas dans la publication
    err_spare        code prevu mais non attribue (ligne vide dans la publication)
    err_not_releasable  contenu remplace par NOT RELEASABLE
    err_out_of_range parametre hors limites (cap 400, TURN 40...)
    err_missing_side TURN/CORPEN sans PORT ni STBD (art. 601 : toujours indique)

Limite connue : MTP 1(D) Vol. II donne les formes parlees des groupes
(art. 119, p. 1-12) mais pas la procedure radiotelephonique complete. Les
trames d'appel ("THIS IS", "EXECUTE TO FOLLOW", "OVER") sont donc des gabarits
a faire valider par l'expert ; seul le gabarit "immediate_execute" reprend
l'exemple imprime p. 7-7 et 8-3.
"""
import argparse
import csv
import json
import random
import re
from pathlib import Path

PHONETIC = {
    "A": "ALFA", "B": "BRAVO", "C": "CHARLIE", "D": "DELTA", "E": "ECHO",
    "F": "FOXTROT", "G": "GOLF", "H": "HOTEL", "I": "INDIA", "J": "JULIETT",
    "K": "KILO", "L": "LIMA", "M": "MIKE", "N": "NOVEMBER", "O": "OSCAR",
    "P": "PAPA", "Q": "QUEBEC", "R": "ROMEO", "S": "SIERRA", "T": "TANGO",
    "U": "UNIFORM", "V": "VICTOR", "W": "WHISKEY", "X": "XRAY", "Y": "YANKEE",
    "Z": "ZULU",
}
DIGITS = {"0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
          "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINER"}
# formes parlees des pavillons speciaux (MTP 1(D) Vol. II, p. 1-12)
SPOKEN_WORD = {"EMERG": "EMERGENCY", "FORM": "FORMATION", "INT": "INTERROGATIVE",
               "STBD": "STARBOARD", "ANS": "ANSWER", "NEGAT": "NEGAT", "DESIG": "DESIG",
               "PORT": "PORT", "CORPEN": "CORPEN", "TURN": "TURN", "SPEED": "SPEED",
               "STATION": "STATION", "SCREEN": "SCREEN", "TACK": "TACK"}
# variantes d'orthographe frequentes en sortie de reconnaissance vocale
ASR_VARIANTS = {"ALFA": "ALPHA", "JULIETT": "JULIET", "XRAY": "X-RAY", "NINER": "NINE",
                "WHISKEY": "WHISKY", "STARBOARD": "STARBORD", "FORMATION": "FORM",
                "EMERGENCY": "EMERG"}

DEFAULT_SHIPS = ["ALFA", "HANNIBAL", "CHARLIE", "DELTA"]   # noms du simulateur
KEYWORDS = ("FORM", "STATION", "TURN", "CORPEN", "SPEED", "SCREEN", "EMERG")


def speak_token(tok):
    """Un element ecrit ('TURN', 'STBD', '125', 'AD', 'J') -> mots parles."""
    if tok in SPOKEN_WORD:
        return [SPOKEN_WORD[tok]]
    if tok.isdigit():
        return [DIGITS[d] for d in tok]
    if re.fullmatch(r"[A-Z0-9]+", tok):          # groupe de lettres/chiffres : epele
        return [PHONETIC.get(c) or DIGITS[c] for c in tok]
    return [tok]


def speak(written):
    out = []
    for tok in written.split():
        out += speak_token(tok)
    return " ".join(out)


def frame(written_signal, to, sender, method):
    """Habille le signal dans une trame radio. -> (texte ecrit, texte parle)."""
    sig_spoken = speak(written_signal)
    if method == "plain":
        w = f"{to} THIS IS {sender} {written_signal} OVER"
        s = f"{to} THIS IS {sender} {sig_spoken} OVER"
    elif method == "execute_to_follow":
        w = f"{to} THIS IS {sender} EXECUTE TO FOLLOW {written_signal} OVER"
        s = f"{to} THIS IS {sender} EXECUTE TO FOLLOW {sig_spoken} OVER"
    elif method == "immediate_execute":
        w = (f"{to} THIS IS {sender} IMMEDIATE EXECUTE {written_signal} I SAY AGAIN "
             f"{written_signal} STANDBY EXECUTE OVER")
        s = (f"{to} THIS IS {sender} IMMEDIATE EXECUTE {sig_spoken} I SAY AGAIN "
             f"{sig_spoken} STANDBY EXECUTE OVER")
    else:
        raise ValueError(method)
    return w, s


# ---------------------------------------------------------------- parametres
def param_variants(sig, rng):
    """Signaux dont l'en-tete decrit les parametres. -> liste (ecrit, params)."""
    head = sig["signal"]
    out = []
    m = re.match(r"^(TURN|CORPEN) \[PORT or STBD\] \[1 to (\d+)\] or \[000 to 359\]$", head)
    if m:
        kw, mx = m.group(1), int(m.group(2))
        side = rng.choice(["PORT", "STBD"]); tens = rng.randint(1, mx)
        out.append((f"{kw} {side} {tens}", {"side": side, "relative_tens_of_degrees": tens,
                                           "relative_degrees": tens * 10}))
        side = rng.choice(["PORT", "STBD"]); crs = rng.randrange(0, 360, 5)
        out.append((f"{kw} {side} {crs:03d}", {"side": side, "true_course": crs}))
        return out
    m = re.match(r"^(FORM|STATION|EMERG) [\[(]000 to 359[\])]$", head)
    if m:
        brg = rng.randrange(0, 360, 5)
        return [(f"{m.group(1)} {brg:03d}", {"true_bearing": brg})]
    m = re.match(r"^(FORM|STATION|EMERG) [\[(]PORT or STBD[\])] [\[(]0 to 18[\])]$", head)
    if m:
        side = rng.choice(["PORT", "STBD"]); tens = rng.randint(0, 18)
        return [(f"{m.group(1)} {side} {tens}", {"side": side,
                                                "relative_bearing_tens_of_degrees": tens,
                                                "relative_bearing_degrees": tens * 10})]
    m = re.match(r"^FORM (\d+) to (\d+)$", head)
    if m:
        n = rng.randint(int(m.group(1)), int(m.group(2)))
        return [(f"FORM {n}", {"formation_number": n})]
    if head == "SPEED":
        kn = rng.randint(5, 27)
        return [(f"SPEED {kn}", {"speed_knots": kn})]
    return out


def out_of_range(sig, rng):
    head = sig["signal"]
    m = re.match(r"^(TURN|CORPEN) \[PORT or STBD\] \[1 to (\d+)\] or \[000 to 359\]$", head)
    if m:
        kw, mx = m.group(1), int(m.group(2))
        side = rng.choice(["PORT", "STBD"])
        return [(f"{kw} {side} {rng.randint(mx + 1, 99)}", f"valeur relative au-dela de {mx}"),
                (f"{kw} {side} {rng.randint(360, 399)}", "cap au-dela de 359")]
    m = re.match(r"^(FORM|STATION|EMERG) [\[(]000 to 359[\])]$", head)
    if m:
        return [(f"{m.group(1)} {rng.randint(360, 399)}", "relevement au-dela de 359")]
    return []


# ------------------------------------------------------------------- generation
def build(signals, seed=7, ships=None, per_signal=1, param_samples=10):
    rng = random.Random(seed)
    ships = ships or DEFAULT_SHIPS
    cases = []
    known = {s["signal"] for s in signals}

    def add(category, written_signal, expected, sig=None, method=None, note="",
            needs_expert=False, spoken_override=None):
        to = rng.choice(ships + ["ALL SHIPS"])
        sender = rng.choice([x for x in ships if x != to])
        method = method or rng.choice(["plain", "plain", "execute_to_follow", "immediate_execute"])
        w, s = frame(written_signal, to, sender, method)
        if spoken_override:
            s = spoken_override(s)
        case = {
            "id": f"T{len(cases) + 1:05d}", "category": category,
            "written_signal": written_signal, "written_text": w, "spoken_text": s,
            "to": to, "from": sender, "method": method,
            "expected": expected, "needs_expert": needs_expert, "note": note,
        }
        if sig is not None:
            case["expected"].update({
                "signal_id": sig["id"], "signal": sig["signal"],
                "reference": sig["reference"], "source_text": sig["full_text"],
                "blanks_in_meaning": sig["blanks"],
            })
        cases.append(case)
        return case

    assigned = [s for s in signals if s["status"] == "assigned"]
    for sig in assigned:
        head = sig["signal"]
        variants = [v for _ in range(param_samples) for v in param_variants(sig, rng)]
        variants = list({v[0]: v for v in variants}.values())      # sans doublons
        if variants:
            for written, params in variants:
                c = add("clean_param", written, {"status": "ok", "params": params}, sig)
                # variante d'orthographe sur le meme message
                if any(k in c["spoken_text"].split() for k in ASR_VARIANTS):
                    add("variant_asr", written, {"status": "ok", "params": params}, sig,
                        method=c["method"], note="memes mots, orthographe de reconnaissance vocale",
                        spoken_override=lambda t: " ".join(ASR_VARIANTS.get(x, x) for x in t.split()))
            for written, why in out_of_range(sig, rng):
                add("err_out_of_range", written,
                    {"status": "invalid_parameter", "reason": why, "base_signal": head}, None,
                    note="le systeme doit refuser et dire pourquoi")
            if head.startswith(("TURN [", "CORPEN [")):
                kw = head.split()[0]
                add("err_missing_side", f"{kw} {rng.randint(1, 18)}",
                    {"status": "missing_parameter", "missing": "PORT ou STBD",
                     "base_signal": head, "rule": "art. 601 / 701 : le bord doit etre indique"},
                    None, note="a confirmer par l'expert : ce groupe sans bord est-il toujours rejete ?",
                    needs_expert=True)
            continue
        if re.search(r"[\[(/]| or | to ", head):
            continue                      # en-tete a parametres non gere : laisse a l'expert
        for _ in range(per_signal):
            head = head.replace("*", "")
            if sig["blanks"] == 0 and not sig["has_lists"]:
                add("clean_fixed", head, {"status": "ok", "params": {}}, sig)
            else:
                add("needs_params", head,
                    {"status": "ok_identification_only", "params": None}, sig,
                    note="le sens contient des blancs ou des listes : l'expert indique comment "
                         "ils sont transmis et complete le message", needs_expert=True)

    # codes non attribues / non diffusables
    for sig in signals:
        if sig["status"] == "spare" and rng.random() < 0.25:
            rng_head = re.match(r"^FORM (\d+) to \d+$", sig["signal"])
            add("err_spare", f"FORM {rng_head.group(1)}" if rng_head else sig["signal"],
                {"status": "spare", "signal": sig["signal"], "reference": sig["reference"]}, None,
                note="code present dans la publication mais sans sens attribue")
        if sig["status"] == "not_releasable":
            add("err_not_releasable", sig["signal"],
                {"status": "not_releasable", "signal": sig["signal"],
                 "reference": sig["reference"]}, None,
                note="le systeme doit repondre 'non disponible', jamais deviner")

    # groupes inexistants
    groups = sorted({m.group(1) for s in signals
                     for m in [re.match(r"^([A-Z]{2})\d+$", s["signal"])] if m})
    made = 0
    while made < 60:
        if rng.random() < 0.6:
            code = f"{rng.choice(groups)}{rng.randint(170, 199)}"
        else:
            code = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2)) + str(rng.randint(1, 60))
            if code[:2] in groups:
                continue
        if code in known:
            continue
        add("err_unknown", code, {"status": "unknown_signal", "signal": code}, None,
            note="groupe absent de la publication")
        made += 1
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signals_json"); ap.add_argument("out_dir")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--per-signal", type=int, default=1)
    ap.add_argument("--param-samples", type=int, default=10,
                    help="tirages par signal de manoeuvre a parametres")
    ap.add_argument("--ships", default=",".join(DEFAULT_SHIPS))
    a = ap.parse_args()
    signals = json.loads(Path(a.signals_json).read_text("utf-8"))
    cases = build(signals, a.seed, [s.strip().upper() for s in a.ships.split(",")], a.per_signal,
                  a.param_samples)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    with open(out / "testset.jsonl", "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(out / "testset.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "method", "written_text", "spoken_text", "expected_status",
                    "expected_signal", "expected_params", "reference", "source_text",
                    "needs_expert", "note"])
        for c in cases:
            e = c["expected"]
            w.writerow([c["id"], c["category"], c["method"], c["written_text"], c["spoken_text"],
                        e.get("status"), e.get("signal") or e.get("base_signal", ""),
                        json.dumps(e.get("params"), ensure_ascii=False) if e.get("params") else "",
                        e.get("reference", ""), e.get("source_text", ""),
                        "oui" if c["needs_expert"] else "", c["note"]])
    stats = {}
    for c in cases:
        stats[c["category"]] = stats.get(c["category"], 0) + 1
    stats["total"] = len(cases)
    (out / "testset_stats.json").write_text(json.dumps(stats, indent=1), "utf-8")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
