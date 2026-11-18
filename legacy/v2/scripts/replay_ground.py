"""Rejoue le controle `grounded` sur des reponses deja produites (sans relancer le modele de redaction) : combien de bonnes reponses seraient refusees, combien de pieges bloques.
Usage (dans l'image hannibal-v2) : python3 scripts/replay_ground.py questions.jsonl resultats.jsonl"""
import json, sys, collections, psycopg
sys.path.insert(0, "scripts"); import hx2_service as S
Q = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[1], encoding="utf-8")}
c = collections.Counter(); why = collections.Counter()
with psycopg.connect(S.PG) as con:
    for l in open(sys.argv[2], encoding="utf-8"):
        a = json.loads(l)
        if a["status"] != "ok": c[(a["verdict"], "inchangé")] += 1; continue
        src = [{"text": " ".join(r[0] for r in con.execute("SELECT text || ' ' || coalesce(title,'') FROM v2.passages WHERE pub = %s AND pdf_page = %s", (x["pub"], x["pdf_page"])).fetchall()), "title": ""} for x in a["cited"]]
        enq, _ = S.expand(Q[a["id"]]["question"])
        ok, r = S.grounded(Q[a["id"]]["question"], a["answer"], src, enq)
        c[(a["verdict"], "gardé" if ok else "REFUSÉ")] += 1
        if not ok: why[("chiffre" if "chiffre" in r else "terme absent", a["verdict"])] += 1
for k in sorted(c): print(k, c[k])
print(dict(why))
