#!/usr/bin/env python3
"""Genere, pour chaque passage, les questions auxquelles il repond (3 en anglais + 3 en francais) avec le modele local,
et les indexe (table v2.pquestions). But : mieux retrouver un passage a partir d'une question, surtout en francais.
Reprise possible : les passages deja traites sont sautes. N'affiche que des compteurs.
Usage : v2run.sh gen_questions.py [--pubs MTP-01-VOL1,ATP-16] [--limit N]"""
import json, os, sys, time, argparse, psycopg, requests
PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
OLLAMA = os.environ.get("HX_OLLAMA", "http://127.0.0.1:11435"); LLM = os.environ.get("HX_LLM", "gemma3:12b"); EMBED = os.environ.get("HX_EMBED", "bge-m3")
ap = argparse.ArgumentParser(); ap.add_argument("--pubs", default="MTP-01-VOL1,ATP-16,MXP-02,AJP-3.1,AJP-3.3.3,AJP-3,AJP-6,ATP-16.1,AJP-3.3,AJP-3.20,ATP-28"); ap.add_argument("--limit", type=int, default=0); o = ap.parse_args()
SYS = ("You receive one extract from a NATO naval publication. Write 3 different questions in English that an officer or a trainee could ask and that THIS extract answers precisely, "
       "then the same 3 questions in French. Each question must be self-contained (name the subject explicitly; never say 'the extract', 'this text' or 'above'). "
       "Use the vocabulary an operator would use, not a copy of the sentences. Return JSON {\"en\": [..3..], \"fr\": [..3..]}.")
with psycopg.connect(PG, autocommit=True) as con:
    con.execute("CREATE TABLE IF NOT EXISTS v2.pquestions (id bigserial PRIMARY KEY, passage_id text NOT NULL, pub text NOT NULL, lang text, question text NOT NULL, embedding vector(1024))")
    con.execute("CREATE INDEX IF NOT EXISTS pquestions_hnsw ON v2.pquestions USING hnsw (embedding vector_cosine_ops)")
    con.execute("CREATE INDEX IF NOT EXISTS pquestions_pid ON v2.pquestions (passage_id)")
    done = {r[0] for r in con.execute("SELECT DISTINCT passage_id FROM v2.pquestions").fetchall()}
    n = ok = bad = 0; t0 = time.time()
    for pub in o.pubs.split(","):
        rows = con.execute("SELECT id, title, text FROM v2.passages WHERE pub = %s AND kind IN ('text','table','figure_text') AND length(text) > 200 ORDER BY pdf_page, id", (pub,)).fetchall()
        for pid, title, text in rows:
            if pid in done: continue
            if o.limit and n >= o.limit: break
            n += 1
            try:
                r = requests.post(f"{OLLAMA}/api/chat", timeout=300, json={"model": LLM, "stream": False, "format": "json", "options": {"temperature": 0, "num_ctx": 8192},
                    "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": f"{pub} — {title or ''}\n\n{text[:2400]}"}]})
                d = json.loads(r.json()["message"]["content"])
                qs = [("en", str(q).strip()) for q in (d.get("en") or [])[:3]] + [("fr", str(q).strip()) for q in (d.get("fr") or [])[:3]]
                qs = [(l, q) for l, q in qs if 15 < len(q) < 300]
                if not qs: bad += 1; continue
                e = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED, "input": [q for _, q in qs]}, timeout=120).json()["embeddings"]
                with con.cursor() as cur:
                    cur.executemany("INSERT INTO v2.pquestions (passage_id, pub, lang, question, embedding) VALUES (%s,%s,%s,%s,%s::vector)",
                                    [(pid, pub, l, q, "[" + ",".join(f"{x:.6f}" for x in v) + "]") for (l, q), v in zip(qs, e)])
                ok += 1
            except Exception: bad += 1
            if n % 50 == 0: print(f"{pub} traites {n} ok {ok} echecs {bad} {round((time.time() - t0) / n, 1)} s/passage", flush=True)
    print(f"FIN traites {n} ok {ok} echecs {bad} total questions {con.execute('SELECT count(*) FROM v2.pquestions').fetchone()[0]}", flush=True)
