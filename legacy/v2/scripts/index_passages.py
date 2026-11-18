#!/usr/bin/env python3
"""HANNIBAL X v2 : indexation et recherche des passages dans pgvector (schema v2).

Tout est local : PostgreSQL + pgvector (conteneur hannibal-pg), embeddings bge-m3
par Ollama (conteneur hannibal-ollama), comme la v1. La table public.hx_chunks de
la v1 n'est jamais touchee.

  index_passages.py passages.jsonl [--force]      indexe (idempotent par id)
  index_passages.py --search "question" [--pub MTP-01] [-k 5] [--json]
  index_passages.py --stats
  index_passages.py --delete-pub NOM              retire une publication

Une ligne de passages.jsonl = un objet : id, pub, text (obligatoires), et
edition, chapter, section, article, title, page, pdf_page, kind (facultatifs).

Variables d'environnement : HX_PG, HX_OLLAMA, HX_EMBED (memes valeurs par defaut que la v1).
"""
import argparse, json, os, sys, time
import psycopg, requests

PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
OLLAMA = os.environ.get("HX_OLLAMA", "http://127.0.0.1:11435")
EMBED = os.environ.get("HX_EMBED", "bge-m3")
DIM, BATCH, MAXC = 1024, 16, 6000
COLS = ["id", "pub", "edition", "chapter", "section", "article", "title", "page", "pdf_page", "kind", "text"]


def embed(texts):
    out = []
    for i in range(0, len(texts), BATCH):
        r = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED, "input": texts[i:i + BATCH], "keep_alive": "2m"}, timeout=600)
        r.raise_for_status(); out += r.json()["embeddings"]
    if out and len(out[0]) != DIM: sys.exit(f"dimension {len(out[0])} au lieu de {DIM}")
    return out


def vec(v): return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def to_embed(d):
    head = " — ".join(str(d[k]) for k in ("pub", "chapter", "section", "article", "title") if d.get(k))
    return (head + "\n" + d["text"])[:MAXC]


def index(path, force):
    docs, bad = [], 0
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line: continue
        d = json.loads(line)
        if not d.get("id") or not d.get("pub") or not (d.get("text") or "").strip(): bad += 1; continue
        docs.append(d)
    ids = [d["id"] for d in docs]
    if len(set(ids)) != len(ids): sys.exit("identifiants en double dans le fichier")
    with psycopg.connect(PG) as con:
        known = {} if force else dict(con.execute("SELECT id, md5(text) FROM v2.passages WHERE id = ANY(%s)", (ids,)).fetchall())
        import hashlib
        todo = [d for d in docs if known.get(d["id"]) != hashlib.md5(d["text"].encode()).hexdigest()]
        print(f"{len(docs)} passages lus ({bad} ignores), {len(docs) - len(todo)} deja a jour, {len(todo)} a indexer", flush=True)
        t0 = time.time()
        for i in range(0, len(todo), 64):
            part = todo[i:i + 64]; vs = embed([to_embed(d) for d in part])
            with con.cursor() as cur:
                cur.executemany(
                    "INSERT INTO v2.passages (" + ",".join(COLS) + ",embedding,indexed_at) VALUES (" + ",".join(["%s"] * len(COLS)) + ",%s::vector,now()) "
                    "ON CONFLICT (id) DO UPDATE SET " + ",".join(f"{c}=EXCLUDED.{c}" for c in COLS[1:]) + ",embedding=EXCLUDED.embedding,indexed_at=now()",
                    [tuple((int(d[c]) if c == "pdf_page" and d.get(c) not in (None, "") else (None if d.get(c) in (None, "") else (d[c] if c == "pdf_page" else str(d[c])))) for c in COLS) + (vec(v),) for d, v in zip(part, vs)])
            con.commit()
            print(f"  {min(i + 64, len(todo))}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    print("termine")


def search(q, pub, k, as_json):
    v = vec(embed([q])[0])
    sql = "SELECT id, pub, chapter, section, article, title, page, pdf_page, kind, text, 1 - (embedding <=> %s::vector) AS score FROM v2.passages "
    args = [v]
    if pub: sql += "WHERE pub = ANY(%s) "; args.append(pub)
    sql += "ORDER BY embedding <=> %s::vector LIMIT %s"; args += [v, k]
    with psycopg.connect(PG) as con:
        con.execute("SET hnsw.ef_search = 100")
        rows = con.execute(sql, args).fetchall()
    keys = ["id", "pub", "chapter", "section", "article", "title", "page", "pdf_page", "kind", "text", "score"]
    res = [dict(zip(keys, r)) for r in rows]
    if as_json: print(json.dumps(res, ensure_ascii=False)); return
    for r in res:
        ref = " ".join(str(x) for x in (r["pub"], r["chapter"], r["article"]) if x)
        print(f"{r['score']:.3f}  {ref}  p.{r['page']} (pdf {r['pdf_page']})  [{r['id']}]\n       {(r['title'] or '')[:80]}\n       {r['text'][:220].replace(chr(10), ' ')}\n")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("file", nargs="?"); a.add_argument("--force", action="store_true")
    a.add_argument("--search"); a.add_argument("--pub", action="append"); a.add_argument("-k", type=int, default=5); a.add_argument("--json", action="store_true")
    a.add_argument("--stats", action="store_true"); a.add_argument("--delete-pub")
    o = a.parse_args()
    if o.search: return search(o.search, o.pub, o.k, o.json)
    if o.stats:
        with psycopg.connect(PG) as con:
            for r in con.execute("SELECT pub, count(*), count(embedding) FROM v2.passages GROUP BY 1 ORDER BY 1").fetchall(): print(f"{r[0]:<14} {r[1]:>6} passages, {r[2]:>6} vecteurs")
            print("total", con.execute("SELECT count(*) FROM v2.passages").fetchone()[0])
        return
    if o.delete_pub:
        with psycopg.connect(PG) as con: print(con.execute("DELETE FROM v2.passages WHERE pub = %s", (o.delete_pub,)).rowcount, "passages retires")
        return
    if not o.file: a.error("fichier passages.jsonl attendu")
    index(o.file, o.force)


if __name__ == "__main__": main()
