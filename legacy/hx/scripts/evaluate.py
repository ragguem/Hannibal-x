#!/usr/bin/env python3
"""Mesure l'interpreteur sur le jeu de test.

Usage :
    python evaluate.py kb/signals.json tests/testset.jsonl [--field spoken_text]
                       [--transcripts transcripts.csv] [--out resultats.csv]

--field        spoken_text (defaut) ou written_text
--transcripts  CSV id,transcript : evalue sur la sortie d'une reconnaissance vocale
               au lieu du texte de reference (mesure de bout en bout)

Un cas est reussi si le statut, le signal et les parametres attendus sont retrouves.
"""
import argparse
import csv
import json
from pathlib import Path

from interpret import KB, compact, interpret


def check(case, res):
    e = case["expected"]
    want = "ok" if e["status"] == "ok_identification_only" else e["status"]
    if res["status"] != want:
        return False, f"statut {res['status']} au lieu de {want}"
    if want == "ok":
        if res["signal_id"] != e["signal_id"] and e["signal_id"] not in \
                [c["signal_id"] for c in res["candidates"]]:
            return False, f"signal {res['signal']} au lieu de {e['signal']}"
        if e.get("params"):
            for k, v in e["params"].items():
                if res["params"].get(k) != v:
                    return False, f"parametre {k} = {res['params'].get(k)} au lieu de {v}"
    elif want in ("spare", "not_releasable", "unknown_signal"):
        if compact(res["signal"] or "") != compact(e["signal"]):
            return False, f"signal {res['signal']} au lieu de {e['signal']}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("signals"); ap.add_argument("testset")
    ap.add_argument("--field", default="spoken_text")
    ap.add_argument("--transcripts"); ap.add_argument("--out")
    a = ap.parse_args()
    kb = KB(a.signals)
    cases = [json.loads(l) for l in Path(a.testset).read_text("utf-8").splitlines() if l.strip()]
    transcripts = None
    if a.transcripts:
        with open(a.transcripts, encoding="utf-8-sig") as f:
            transcripts = {r["id"]: r["transcript"] for r in csv.DictReader(f)}
        cases = [c for c in cases if c["id"] in transcripts]
    stats, rows = {}, []
    for c in cases:
        text = transcripts[c["id"]] if transcripts else c[a.field]
        res = interpret(text, kb)
        ok, why = check(c, res)
        s = stats.setdefault(c["category"], [0, 0])
        s[0] += ok; s[1] += 1
        rows.append([c["id"], c["category"], "OK" if ok else "ECHEC", why, text, res["status"],
                     res["signal"] or "", c["expected"].get("signal", "")])
    tot_ok = sum(v[0] for v in stats.values()); tot = sum(v[1] for v in stats.values())
    print(f"{'categorie':22s} reussis / total")
    for k, (ok, n) in sorted(stats.items()):
        print(f"{k:22s} {ok:5d} / {n:5d}  ({100 * ok / n:.1f} %)")
    print(f"{'TOTAL':22s} {tot_ok:5d} / {tot:5d}  ({100 * tot_ok / max(tot, 1):.1f} %)")
    if a.out:
        with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "category", "resultat", "raison", "texte", "statut_obtenu",
                        "signal_obtenu", "signal_attendu"])
            w.writerows(rows)


if __name__ == "__main__":
    main()
