#!/usr/bin/env python3
"""Recherche par mots-cles (BM25) dans les passages et les signaux du MTP 2.

Usage :
    python search.py kb "reduced tactical diameter" [-n 5]

Sans dependance ni modele : c'est la recherche de base, qui sert aussi de
reference pour mesurer plus tard l'apport d'une recherche par embeddings
(pgvector + modele multilingue) sur le serveur.
"""
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

STOP = set("the a an of to in on or and is are be by for with as at from this that it".split())


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


class Index:
    def __init__(self, kb_dir):
        kb = Path(kb_dir)
        self.docs = []
        for line in (kb / "passages.jsonl").read_text("utf-8").splitlines():
            p = json.loads(line)
            self.docs.append({"id": p["id"], "type": "passage", "reference": p["reference"],
                              "text": p["text"]})
        for s in json.loads((kb / "signals.json").read_text("utf-8")):
            if s["status"] == "assigned":
                self.docs.append({"id": s["id"], "type": "signal", "reference": s["reference"],
                                  "text": s["signal"] + " . . . " + s["full_text"]})
        self.tf = [Counter(tokens(d["text"])) for d in self.docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(t for c in self.tf for t in c)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query, n=5, k1=1.5, b=0.75):
        q = tokens(query)
        scored = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for t in q:
                if t in c:
                    s += self.idf[t] * c[t] * (k1 + 1) / (c[t] + k1 * (1 - b + b * self.len[i] / self.avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [dict(self.docs[i], score=round(s, 2)) for s, i in scored[:n]]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    n = int(sys.argv[sys.argv.index("-n") + 1]) if "-n" in sys.argv else 5
    for r in Index(sys.argv[1]).search(sys.argv[2], n):
        print(f"[{r['score']}] {r['type']} — {r['reference']}")
        print("    " + " ".join(r["text"].split())[:300])
