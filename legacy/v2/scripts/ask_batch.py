"""Passe les questions de controle dans /ask et mesure : repondu / refuse, bonne page citee, pieges refuses, duree.
Usage : python3 scripts/ask_batch.py eval/questions.jsonl eval/ask_results.jsonl"""
import json, sys, time, os, urllib.request
sys.path.insert(0, "eval")
from evaluate_search import pubkey
qs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
out = open(sys.argv[2], "w", encoding="utf-8"); S = {"ok_bonne_page": 0, "ok_autre_page": 0, "refus_a_tort": 0, "piege_refuse": 0, "piege_repondu": 0, "erreur": 0}; T = []
for i, q in enumerate(qs):
    trap = q.get("expected") == "none" or not q.get("pdf_page")
    try:
        extra = {}
        if os.environ.get("PUBFILTER") and not trap:          # l'utilisateur a choisi la publication
            M = {"MTP01I": "MTP-01-VOL1", "ATP16": "ATP-16", "ATP161": "ATP-16.1", "MXP02": "MXP-02", "AJP3": "AJP-3", "AJP31": "AJP-3.1", "AJP33": "AJP-3.3", "AJP333": "AJP-3.3.3", "AJP320": "AJP-3.20", "AJP6": "AJP-6"}
            extra = {"pubs": [M[pubkey(q["pub"])]]}
        req = urllib.request.Request(os.environ.get("HX2_EVAL_URL", "http://127.0.0.1:8774") + "/ask", data=json.dumps(dict({"q": q["question"], "lang": q.get("lang", "fr")}, **json.loads(os.environ.get("HX2_EVAL_EXTRA", "{}")), **extra)).encode(), headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=900).read())
    except Exception as e: r = {"status": "erreur", "error": str(e)[:200]}
    T.append(r.get("seconds", 0)); good = False
    if r.get("status") == "ok" and not trap:
        pages = q["pdf_page"] if isinstance(q["pdf_page"], list) else [q["pdf_page"]]
        for s in r["sources"]:
            if s["n"] in r["cited"] and pubkey(s["pub"]) == pubkey(q["pub"]) and any(abs(int(s["pdf_page"]) - int(p)) <= 1 for p in pages): good = True
    k = "erreur" if r.get("status") == "erreur" or "error" in r else ("piege_refuse" if r["status"] == "refus" else "piege_repondu") if trap else ("refus_a_tort" if r["status"] == "refus" else "ok_bonne_page" if good else "ok_autre_page")
    S[k] += 1
    out.write(json.dumps({"id": q["id"], "lang": q.get("lang"), "verdict": k, "status": r.get("status"), "reason": r.get("reason"), "seconds": r.get("seconds"), "answer": r.get("answer"), "cited": [{"pub": s["pub"], "article": s["article"], "page": s["page"], "pdf_page": s["pdf_page"]} for s in r.get("sources", []) if s["n"] in r.get("cited", [])], "top_score": (r.get("sources") or [{}])[0].get("score"), "draft": r.get("draft"), "query_en": (r.get("search") or {}).get("query_en"), "source_ids": [x.get("id") for x in r.get("sources", [])], "cited_n": r.get("cited")}, ensure_ascii=False) + "\n"); out.flush()
    print(i + 1, len(qs), k, r.get("seconds"), flush=True)
T = sorted(t for t in T if t); print("BILAN", json.dumps(S, ensure_ascii=False), "| duree mediane", T[len(T) // 2] if T else None, "s, max", T[-1] if T else None, flush=True)
