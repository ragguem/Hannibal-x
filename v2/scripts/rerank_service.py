#!/usr/bin/env python3
"""HANNIBAL X v2 — service de reclassement (bge-reranker-v2-m3 sur GPU, demi-precision), 127.0.0.1:8775.
POST /rerank {"queries": ["question", "reformulation anglaise"], "passages": ["...", ...]} -> {"scores": [...]} (meilleur score des requetes).
Ne tourne qu'en « mode demo » (voir demo_on.sh) : il a besoin d'environ 1,5 Go de memoire GPU."""
import json, os, http.server
os.environ.setdefault("HF_HOME", "/v2/models")
from sentence_transformers import CrossEncoder
DEV = os.environ.get("DEVICE", "cuda")
MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")     # ou un dossier local, ex. /v2/models/reranker-hannibal
M = CrossEncoder(MODEL, device=DEV, max_length=512)
if DEV == "cuda": M.model.half()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._json({"ok": True, "model": MODEL, "device": DEV})
    def do_POST(self):
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}")
            qs = [q for q in b.get("queries", []) if q][:3]; ps = [str(p)[:4000] for p in b.get("passages", [])][:60]
            best = [None] * len(ps)
            for q in qs:
                s = M.predict([(q, p) for p in ps], batch_size=16, show_progress_bar=False)
                best = [float(x) if y is None else max(float(x), y) for x, y in zip(s, best)]
            self._json({"scores": best})
        except Exception as e: self._json({"error": str(e)[:200]}, 500)
if __name__ == "__main__":
    print("reclassement sur 127.0.0.1:8775", flush=True); http.server.ThreadingHTTPServer(("127.0.0.1", 8775), H).serve_forever()
