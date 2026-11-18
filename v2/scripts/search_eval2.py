"""Mesure la recherche du service hx2 (mode hybrid ou dense). Usage : python3 scripts/search_eval2.py eval/queries.jsonl eval/results_X.jsonl [dense]"""
import json, sys, os, urllib.request
mode = sys.argv[3] if len(sys.argv) > 3 else "hybrid"
with open(sys.argv[2], "w", encoding="utf-8") as out:
    for l in open(sys.argv[1], encoding="utf-8"):
        q = json.loads(l)
        req = urllib.request.Request(os.environ.get("HX2_EVAL_URL", "http://127.0.0.1:8774") + "/search", data=json.dumps(dict({"q": q["question"], "k": 10, "mode": mode}, **json.loads(os.environ.get("EVAL_EXTRA", "{}")))).encode(), headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=600).read())
        out.write(json.dumps({"id": q["id"], "hits": [{"pub": h["pub"], "pdf_page": h["pdf_page"], "score": h.get("fused", h["score"])} for h in r["hits"]]}) + "\n")
print("fait")
