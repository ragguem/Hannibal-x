"""Lance la recherche v2 sur un fichier de questions (jsonl : id, question) et ecrit les resultats pour evaluate_search.py.
Usage : v2run.sh search_batch.py eval/queries.jsonl eval/results_bge.jsonl [-k 10]"""
import json, sys, psycopg
sys.path.insert(0, "scripts")
from index_passages import embed, vec, PG
k = int(sys.argv[sys.argv.index("-k") + 1]) if "-k" in sys.argv else 10
qs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
with psycopg.connect(PG) as con, open(sys.argv[2], "w", encoding="utf-8") as out:
    con.execute("SET hnsw.ef_search = 200")
    for q in qs:
        v = vec(embed([q["question"]])[0])
        rows = con.execute("SELECT id, pub, pdf_page, kind, 1 - (embedding <=> %s::vector) FROM v2.passages ORDER BY embedding <=> %s::vector LIMIT %s", (v, v, k)).fetchall()
        out.write(json.dumps({"id": q["id"], "hits": [{"pub": r[1], "pdf_page": r[2], "score": round(float(r[4]), 4), "pid": r[0], "kind": r[3]} for r in rows]}, ensure_ascii=False) + "\n")
print(len(qs), "questions traitees")
