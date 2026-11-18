import json, sys
sys.path.insert(0, "eval")
from evaluate_search import pubkey
Q = {json.loads(l)["id"]: json.loads(l) for l in open("eval/questions.jsonl", encoding="utf-8")}
E = [json.loads(l) for l in open("eval/exp_lists.jsonl", encoding="utf-8")]
E = [e for e in E if Q[e["id"]].get("pdf_page")]
def ok(q, h):
    pages = q["pdf_page"] if isinstance(q["pdf_page"], list) else [q["pdf_page"]]
    return pubkey(h[1]) == pubkey(q["pub"]) and any(abs(int(h[2]) - int(p)) <= 1 for p in pages)
def rank(q, lst):
    for i, h in enumerate(lst):
        if ok(q, h): return i + 1
    return 999
def rep(name, f):
    rs = [rank(Q[e["id"]], f(e)) for e in E]; n = len(rs)
    print(f"{name:34s} top1 {100*sum(r<=1 for r in rs)/n:5.1f}  top5 {100*sum(r<=5 for r in rs)/n:5.1f}  top10 {100*sum(r<=10 for r in rs)/n:5.1f}  top20 {100*sum(r<=20 for r in rs)/n:5.1f}  top50 {100*sum(r<=50 for r in rs)/n:5.1f}")
def rrf(e, parts, c=60):
    sc, meta = {}, {}
    for name, w in parts:
        for i, h in enumerate(e[name]): sc[h[0]] = sc.get(h[0], 0) + w / (c + i + 1); meta[h[0]] = h
    return [meta[i] for i in sorted(sc, key=lambda x: -sc[x])]
def maxcos(e, names):
    sc, meta = {}, {}
    for nme in names:
        for h in e[nme]: sc[h[0]] = max(sc.get(h[0], 0), h[3]); meta[h[0]] = h
    return [meta[i] for i in sorted(sc, key=lambda x: -sc[x])]
for nme in ["dense_orig", "dense_en", "lex_en", "lex_kw"]: rep(nme, lambda e, nme=nme: e[nme])
rep("max cos orig+en", lambda e: maxcos(e, ["dense_orig", "dense_en"]))
rep("rrf orig+en", lambda e: rrf(e, [("dense_orig", 1), ("dense_en", 1)]))
rep("rrf orig+en+lex_en 0.5", lambda e: rrf(e, [("dense_orig", 1), ("dense_en", 1), ("lex_en", 0.5)]))
rep("rrf orig+en+lex_en 0.3", lambda e: rrf(e, [("dense_orig", 1), ("dense_en", 1), ("lex_en", 0.3)]))
rep("rrf orig 1 + en 0.5", lambda e: rrf(e, [("dense_orig", 1), ("dense_en", 0.5)]))
rep("rrf orig 1 + lex_en 0.3", lambda e: rrf(e, [("dense_orig", 1), ("lex_en", 0.3)]))
rep("union orig+en (top50 rappel)", lambda e: rrf(e, [("dense_orig", 1), ("dense_en", 1), ("lex_en", 1), ("lex_kw", 1)]))
for lang in ("fr", "en"):
    EE = [e for e in E if Q[e["id"]]["lang"] == lang]; n = len(EE)
    for nme in ("dense_orig", "dense_en"):
        rs = [rank(Q[e["id"]], e[nme]) for e in EE]; print(lang, nme, "top5", round(100*sum(r<=5 for r in rs)/n,1), "top20", round(100*sum(r<=20 for r in rs)/n,1))
