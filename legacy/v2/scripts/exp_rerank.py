"""Experience : reclassement des 30 meilleurs candidats par bge-reranker-v2-m3 (processeur). Mesure top 1/5/10 et duree."""
import json, sys, time, os, psycopg
os.environ.setdefault("HF_HOME", "/v2/models")
sys.path.insert(0, "eval")
from evaluate_search import pubkey
from sentence_transformers import CrossEncoder
import torch; torch.set_num_threads(int(os.environ.get("THREADS", "8")))
NC = int(os.environ.get("NC", "30")); ML = int(os.environ.get("ML", "384"))
DEV = os.environ.get("DEVICE", "cpu")
m = CrossEncoder("BAAI/bge-reranker-v2-m3", device=DEV, max_length=ML)
if DEV == "cuda": m.model.half()
Q = {json.loads(l)["id"]: json.loads(l) for l in open("eval/questions.jsonl", encoding="utf-8")}
E = [json.loads(l) for l in open("eval/exp_lists.jsonl", encoding="utf-8")]
PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
def ok(q, h):
    pages = q["pdf_page"] if isinstance(q["pdf_page"], list) else [q["pdf_page"]]
    return pubkey(h[1]) == pubkey(q["pub"]) and any(abs(int(h[2]) - int(p)) <= 1 for p in pages)
def rank(q, lst):
    for i, h in enumerate(lst):
        if ok(q, h): return i + 1
    return 999
R = {"avant": [], "rerank_en": [], "rerank_orig": [], "rerank_max": []}; T = []; out = open("eval/exp_rerank.jsonl", "w")
with psycopg.connect(PG) as con:
    for e in E:
        q = Q[e["id"]]
        sc, meta = {}, {}
        for nme in ("dense_orig", "dense_en"):
            for h in e[nme]: sc[h[0]] = max(sc.get(h[0], 0), h[3]); meta[h[0]] = h
        cand = [meta[i] for i in sorted(sc, key=lambda x: -sc[x])][:NC]
        txt = {r[0]: ((r[1] or "") + ". " + r[2])[:1600] for r in con.execute("SELECT id, title, text FROM v2.passages WHERE id = ANY(%s)", ([c[0] for c in cand],)).fetchall()}
        t0 = time.time(); s_en = m.predict([(e["enq"] or q["question"], txt[c[0]]) for c in cand], batch_size=16, show_progress_bar=False); T.append(time.time() - t0)
        s_or = s_en if os.environ.get("FAST") else m.predict([(q["question"], txt[c[0]]) for c in cand], batch_size=16, show_progress_bar=False)
        by = lambda s: [c for _, c in sorted(zip(s, cand), key=lambda x: -x[0])]
        lists = {"avant": cand, "rerank_en": by(s_en), "rerank_orig": by(s_or), "rerank_max": by([max(a, b) for a, b in zip(s_en, s_or)])}
        out.write(json.dumps({"id": e["id"], "top_en": float(max(s_en)), "top_orig": float(max(s_or)), "trap": not q.get("pdf_page")}) + "\n"); out.flush()
        if q.get("pdf_page"):
            for k in R: R[k].append(rank(q, lists[k]))
        print(e["id"], round(T[-1], 1), flush=True)
for k, rs in R.items():
    n = len(rs); print(f"{k:12s} top1 {100*sum(r<=1 for r in rs)/n:5.1f}  top3 {100*sum(r<=3 for r in rs)/n:5.1f}  top5 {100*sum(r<=5 for r in rs)/n:5.1f}  top8 {100*sum(r<=8 for r in rs)/n:5.1f}  top10 {100*sum(r<=10 for r in rs)/n:5.1f}")
T.sort(); print("duree reclassement (1 requete): mediane", round(T[len(T)//2], 1), "s, max", round(T[-1], 1), "| candidats", NC, "| longueur max", ML)
