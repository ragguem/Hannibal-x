#!/usr/bin/env python3
"""Fabrique les donnees d'entrainement du modele de reclassement a partir des questions generees (v2.pquestions).
Pour chaque question : son passage (positif) + 3 passages proches mais differents (negatifs difficiles, tires de la recherche actuelle).
Sortie : train_rerank.jsonl {"q","pos","negs":[...]} (dans le dossier donne). N'affiche que des compteurs. Le texte ne quitte pas le serveur.
Usage : v2run.sh build_rerank_data.py data_train [--max 12000]"""
import json, os, sys, random, psycopg
PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
out = sys.argv[1]; MAX = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 12000
os.makedirs(out, exist_ok=True); random.seed(7)
with psycopg.connect(PG) as con:
    con.execute("SET hnsw.ef_search = 80")
    ids = [r[0] for r in con.execute("SELECT id FROM v2.pquestions ORDER BY id").fetchall()]
    random.shuffle(ids); ids = ids[:MAX]; n = 0
    with open(os.path.join(out, "train_rerank.jsonl"), "w", encoding="utf-8") as f:
        for qid in ids:
            q, pid, pub, emb = con.execute("SELECT question, passage_id, pub, embedding FROM v2.pquestions WHERE id = %s", (qid,)).fetchone()
            pos = con.execute("SELECT coalesce(title,'') || '. ' || text, pdf_page FROM v2.passages WHERE id = %s", (pid,)).fetchone()
            if not pos: continue
            rows = con.execute("SELECT coalesce(title,'') || '. ' || text FROM v2.passages WHERE id <> %s AND kind <> 'toc' AND NOT (pub = %s AND abs(pdf_page - %s) <= 1) ORDER BY embedding <=> %s LIMIT 12", (pid, pub, pos[1], emb)).fetchall()
            negs = [r[0][:2000] for r in rows[2:]]          # on saute les 2 plus proches (souvent un autre passage qui repond aussi)
            if len(negs) < 3: continue
            f.write(json.dumps({"q": q, "pos": pos[0][:2000], "negs": random.sample(negs, 3)}, ensure_ascii=False) + "\n"); n += 1
            if n % 2000 == 0: print("exemples", n, flush=True)
print("FIN exemples", n, flush=True)
