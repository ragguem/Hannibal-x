"""Experience : listes de candidats par methode (50 premiers) pour chaque question, enregistrees pour essais de fusion hors ligne."""
import json, sys, re, psycopg
sys.path.insert(0, "scripts")
import hx2_service as S
qs = [json.loads(l) for l in open("eval/questions.jsonl", encoding="utf-8")]
out = open("eval/exp_lists.jsonl", "w", encoding="utf-8"); N = 50
W = "kind <> 'toc' AND NOT (pub = ANY(%s))"; CL = list(S.CLASSIFIED)
with psycopg.connect(S.PG) as con:
    con.execute("SET hnsw.ef_search = 300")
    def dense(t):
        v = S.embed(t); return [list(r) for r in con.execute(f"SELECT id, pub, pdf_page, 1 - (embedding <=> %s::vector) FROM v2.passages WHERE {W} ORDER BY embedding <=> %s::vector LIMIT %s", (v, CL, v, N)).fetchall()]
    def lex(text):
        toks = []
        for t in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text):
            t = t.lower()
            if t not in S.STOP and t not in toks: toks.append(t)
        if not toks: return []
        return [list(r) for r in con.execute(f"SELECT id, pub, pdf_page, ts_rank_cd(tsv, qq, 32) FROM v2.passages, to_tsquery('english', %s) qq WHERE {W} AND tsv @@ qq ORDER BY 4 DESC LIMIT %s", (" | ".join(toks[:24]), CL, N)).fetchall()]
    for q in qs:
        enq, kw = S.expand(q["question"])
        out.write(json.dumps({"id": q["id"], "enq": enq, "kw": kw, "dense_orig": dense(q["question"]), "dense_en": dense(enq) if enq else [], "lex_en": lex(enq), "lex_kw": lex(enq + " " + " ".join(kw))}, ensure_ascii=False) + "\n"); out.flush()
print("fait")
