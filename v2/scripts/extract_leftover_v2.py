#!/usr/bin/env python3
"""Recupere le texte que le decoupage principal a laisse de cote (contenu des figures, tableaux sans filets, encadres).

Pour chaque page : les blocs de texte dont les mots ne se retrouvent pas dans les passages deja extraits de cette page
sont regroupes en passages `figure_text`, rattaches a la legende de figure de la page (sinon au dernier article de la page).
N'affiche que des compteurs.  Usage : extract_leftover.py fichier.pdf passages.jsonl --out complement.jsonl
"""
import sys, re, json, argparse, collections, pymupdf
ap = argparse.ArgumentParser(); ap.add_argument("pdf"); ap.add_argument("passages"); ap.add_argument("--out", required=True)
ap.add_argument("--min-words", type=int, default=25); ap.add_argument("--max-words", type=int, default=260); o = ap.parse_args()
W = lambda s: re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-/\.]*", s.lower())
P = [json.loads(l) for l in open(o.passages, encoding="utf-8") if l.strip()]
by = collections.defaultdict(list)
for p in P: by[p["pdf_page"]].append(p)
d = pymupdf.open(o.pdf); N = len(d)
# lignes repetees sur beaucoup de pages (en-tetes, pieds, mentions) : a ignorer
rep = collections.Counter()
for pg in d:
    seen = set()
    for b in pg.get_text("blocks"):
        if b[6] == 0:
            for line in b[4].split("\n"):
                k = re.sub(r"\d+", "#", line.strip().lower())
                if k and k not in seen: seen.add(k); rep[k] += 1
REP = {k for k, n in rep.items() if n >= max(6, N // 25)}
out, stats = [], collections.Counter()
for i, pg in enumerate(d):
    n = i + 1; mine = by.get(n, [])
    if any(p["kind"] in ("toc", "glossary") for p in mine): stats["pages_sommaire_glossaire_ignorees"] += 1; continue
    near = mine + by.get(n - 1, [])          # un passage commence page n-1 peut se poursuivre page n
    have = collections.Counter(w for p in near for w in W(p["text"] + " " + (p.get("title") or "")))
    H = pg.rect.height; cand = []
    joined = " " + " ".join(W(" ".join(p["text"] + " " + (p.get("title") or "") for p in near))) + " "
    for b in sorted([b for b in pg.get_text("blocks") if b[6] == 0], key=lambda b: (round(b[1] / 14), b[0])):
        if b[1] < 45 or b[3] > H - 40: continue
        lines = [l.strip() for l in b[4].split("\n") if l.strip() and re.sub(r"\d+", "#", l.strip().lower()) not in REP]
        txt = " ".join(lines); ws = W(txt)
        if not ws or re.search(r"intentionally\s+blank|not\s+releasable|\.{6,}", txt, re.I): continue
        if sum(1 for w in ws if len(w) == 1) > len(ws) / 2: continue          # texte vertical ou lettres isolees
        k = min(4, len(ws))
        covered = (" " + " ".join(ws[:k]) + " ") in joined or (" " + " ".join(ws[-k:]) + " ") in joined
        cand.append((txt, len(ws), covered, (b[0], b[1], b[2], b[3])))
    big = sum(w for t, w, c, bb in cand if not c and w >= 3)
    # page retenue si assez de texte non repris ; on y garde alors aussi les petites cases (codes, pavillons) meme si le mot existe ailleurs
    keep = [(bb, t) for t, w, c, bb in cand if not c or w <= 2] if big >= o.min_words else []
    # rangees : les blocs qui se chevauchent verticalement sont sur la meme ligne de tableau (ex. « PREP | At the dip: ... »)
    rows = []
    for bb, t in sorted(keep, key=lambda x: -(x[0][3] - x[0][1])):
        for r in rows:
            a = r[0][0]; ov = min(a[3], bb[3]) - max(a[1], bb[1]); h = min(a[3] - a[1], bb[3] - bb[1])
            if h > 0 and ov / h >= 0.5: r.append((bb, t)); break
        else: rows.append([(bb, t)])
    rows.sort(key=lambda r: r[0][0][1])
    left = [re.sub(r"(\w)- (?=[a-z])", r"\1", " | ".join(t for bb, t in sorted(r, key=lambda x: x[0][0]))) for r in rows]
    words = sum(len(W(t)) for t in left)
    if words < o.min_words: stats["pages_sans_reste"] += 1; continue
    cap = next((p for p in mine if p["kind"] == "figure_caption"), None); ref = cap or (mine[-1] if mine else None)
    if ref is None:
        prev = [p for p in P if p["pdf_page"] < n]; ref = prev[-1] if prev else P[0]
    title = (cap["text"] if cap else (ref.get("title") or ""))[:200]
    chunks, cur, cw = [], [], 0
    for t in left:
        w = len(W(t))
        if cur and cw + w > o.max_words: chunks.append("\n".join(cur)); cur, cw = [], 0
        cur.append(t); cw += w
    if cur: chunks.append("\n".join(cur))
    for j, c in enumerate(chunks):
        out.append({"id": f"{ref['pub']}|p{n}|fig{j+1}", "pub": ref["pub"], "edition": ref.get("edition"), "chapter": ref.get("chapter"), "chapter_title": ref.get("chapter_title"),
                    "section": ref.get("section"), "article": ref.get("article"), "title": title, "page": ref.get("page") if ref["pdf_page"] == n else None, "pdf_page": n,
                    "kind": "figure_text", "text": c[:2600]})
    stats["pages_avec_reste"] += 1; stats["passages"] += len(chunks); stats["mots"] += words; stats["avec_legende"] += 1 if cap else 0
with open(o.out, "w", encoding="utf-8") as f:
    for p in out: f.write(json.dumps(p, ensure_ascii=False) + "\n")
print(json.dumps(dict(stats, pages=N), ensure_ascii=False))
