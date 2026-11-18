#!/usr/bin/env python3
"""Découpe une publication OTAN (familles ATP/MTP/MXP et AJP) en passages référencés.

Usage : extract_pub.py fichier.pdf --pub CODE --edition "..." --out passages.jsonl --report rapport.json [--debug]

Seule dépendance : pymupdf. Sans --debug, le script n'affiche que des compteurs (jamais le texte du document).
Un passage = un article ou paragraphe numéroté, recoupé au-delà de ~350 mots.
Champs : id, pub, edition, chapter, chapter_title, section, article, title, page (numéro imprimé), pdf_page, kind, text.
kind : text | table | figure_caption | glossary | toc (les sommaires/index sont comptés mais non écrits, sauf --keep-toc).
"""
import argparse, collections, hashlib, json, re, statistics, sys
import pymupdf

MAXW = 350
LABEL = re.compile(r"^(?:(?:[A-Za-z]{1,8}\d{0,2}[A-Z]?|\d{1,2}[A-Z]?)(?:-\d{1,2})?-)?\d{1,4}$|^[ivxlcdm]{1,7}$|^[IVXLCDM]{1,7}$")
CLASSIF = re.compile(r"^\(?\s*(NATO|OTAN)[ \-/]*(UNCLASSIFIED|RESTRICTED|CONFIDENTIAL|SECRET|SANS CLASSIFICATION)[^a-z]*$|^\(?This page is NATO[- ]UNCLASSIFIED\)?$", re.I)
BLANK = re.compile(r"^(THIS PAGE )?(IS )?(INTENTIONALLY|LEFT) (LEFT )?BLANK\.?$|^INTENTIONALLY BLANK$", re.I)
CHAP = re.compile(r"^(?:CHAPTER|Chapter)\s+((?:[A-Z]{3})?\d{1,2})\b\s*[–—\-:]?\s*(.*)$")
ANNEX = re.compile(r"^(?:ANNEX|Annex|APPENDIX|Appendix)\s+((?:[A-Z]{3})?\d{0,2}[A-Z]|\d{1,2})\b\s*(?:[–—\-:]|to\b)?\s*(.*)$")
SECT = re.compile(r"^(?:SECTION|Section)\s+([IVXLC]{1,6}|\d{1,2})\b\s*[–—\-:]\s*(.*)$")
PART = re.compile(r"^(?:PART|Part)\s+([IVXLC]{1,6}|\d{1,2})\b\s*[–—\-:]\s*(.*)$")
GLOSS = re.compile(r"^(LEXICON|GLOSSARY|LIST OF ACRONYMS( AND ABBREVIATIONS)?|Lexicon|Glossary)$")
TOCH = re.compile(r"^(TABLE OF CONTENTS|CONTENTS|INDEX|LIST OF EFFECTIVE PAGES|LIST OF ILLUSTRATIONS|LIST OF TABLES|LIST OF FIGURES|RECORD OF CHANGES)\b", re.I)
# articles : 3202 / 10120 / 2A10 / 6G101 / B101 / GBR0131 / « SURFEX 319 » (titre en gras, à la marge)
ART_A = re.compile(r"^(\d{4,5}|\d{1,2}[A-Z]\d{2,3}|[A-Z]\d{3}|[A-Z]{3}\d{4}|[A-Z]{3}\d{1,2}[A-Z]\d{2,3}|[A-Z]{3,9} \d{3})(?:\s*[—–]\s*|\s+)(\S.*)$")
# paragraphes AJP : 1.23 / 1.23. / A.4 / 1.2.3.
ART_J = re.compile(r"^((?:\d{1,2}|[A-Z])(?:\.\d{1,3}){1,3})\.?(?:\s+(\S.*))?$")
PARA = re.compile(r"^(\d{1,2})\.\s+([A-Z].*)$")
SUB = re.compile(r"^(?:[a-z]{1,2}\.|\(\d{1,2}\)|\([a-z]{1,2}\)|\d{1,2}\.|[•–\-])\s")
CAPT = re.compile(r"^(Figure|Fig\.|Table|Tableau)\s+((?:[A-Z]{3})?\d{0,2}[A-Z]?(?:[-.]\d{1,2}){0,2}[-.]?\d{1,2})\s*[.–—\-:]?\s*(.*)$")
NOREL = re.compile(r"NOT\s+RELEASABLE", re.I)
LIG = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
ENDW = {"off", "staff", "cliff", "stuff", "tariff", "takeoff", "cutoff", "standoff", "handoff", "liftoff", "payoff", "stiff", "layoff", "turnoff", "runoff", "take-off", "stand-off", "cast-off", "hand-off", "cut-off", "buff", "bluff", "sheriff", "wi-fi", "wifi"}


def fix_lig(t):
    """Les ligatures (fi, fl, ff…) sont souvent suivies d'un blanc parasite : « signiﬁ cant » -> « significant »."""
    if not any(c in t for c in LIG): return t
    def rep(m):
        pre, lig, sp, nxt = m.group(1), LIG[m.group(2)], m.group(3), m.group(4)
        if sp and nxt and nxt.islower() and (pre + lig).lower() not in ENDW: return pre + lig + nxt
        return pre + lig + sp + nxt
    return re.sub(r"([A-Za-z\-]*)([ﬀ-ﬄ])( *)([A-Za-z]?)", rep, t)


def norm(t): return re.sub(r"\s+", " ", t).strip()


def read_pages(doc):
    """Lignes par page : (y, x, taille, gras, texte), fusionnées quand elles sont sur la même ligne de base."""
    pages, fonts = [], collections.Counter()
    for p in doc:
        raw = []; H = p.rect.height
        for b in p.get_text("dict", flags=pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]:
            for l in b.get("lines", []):
                if abs(l.get("dir", (1, 0))[0]) < 0.9: continue          # texte tourné (figures)
                for s in l["spans"]:
                    if not s["text"].strip(): continue
                    raw.append([s["bbox"][1], s["bbox"][0], s["bbox"][3], s["bbox"][2], round(s["size"], 1), bool(s["flags"] & 16) or "Bold" in s["font"] or "Black" in s["font"], s["text"]])
                    fonts[(round(s["size"], 1), raw[-1][5])] += len(s["text"])
        pages.append(raw)
    body = max(((k, v) for k, v in fonts.items() if not k[1]), key=lambda kv: kv[1], default=((11.0, False), 0))[0][0] if fonts else 11.0
    out = []
    for pi, raw in enumerate(pages):
        raw.sort(key=lambda s: (round(s[0] / 3), s[1])); H = doc[pi].rect.height
        lines = []
        for s in raw:
            if s[4] < body - 2.6: continue                                # appels de note, exposants
            edge = s[0] < 0.068 * H or s[0] > 0.80 * H                     # en-tête / pied : ne pas souder « 3-4 » et « EDITION… »
            if lines and abs(lines[-1]["y"] - s[0]) < 3.5 and s[1] >= lines[-1]["x1"] - 2 and not (edge and s[1] - lines[-1]["x1"] > 14):
                L = lines[-1]; gap = s[1] - L["x1"]
                L["t"] += ("   " if gap > 14 else " " if gap > 1.2 and not L["t"].endswith(" ") else "") + s[6]; L["x1"] = s[3]; L["bold"] = L["bold"] and s[5]; L["nb"] += len(s[6]) if s[5] else 0
            else: lines.append({"y": s[0], "x": s[1], "y1": s[2], "x1": s[3], "size": s[4], "bold": s[5], "b0": s[5], "nb": len(s[6]) if s[5] else 0, "t": s[6]})
        for L in lines: L["t"] = re.sub(r"^C HAPTER\b", "CHAPTER", re.sub(r"^A NNEX\b", "ANNEX", norm(fix_lig(L["t"]))))
        out.append([L for L in lines if L["t"]])
    return out, body


nfoot = [0]


def strip_running(doc, pages, body=11.0):
    """Retire en-têtes et pieds de page répétés ; renvoie le numéro imprimé de chaque page."""
    n = len(pages); cnt = collections.Counter(); zone = []
    for i, lines in enumerate(pages):
        H = doc[i].rect.height; z = []
        for L in lines:
            if L["y"] < 0.12 * H or L["y"] > 0.80 * H:
                k = ("T" if L["y"] < 0.5 * H else "B", "<L>" if LABEL.match(L["t"]) else re.sub(r"\d+", "#", L["t"]))
                z.append((L, k))
        for k in {k for _, k in z}: cnt[k] += 1
        zone.append(z)
    thr = max(4, int(0.04 * n)); labels, kept = [], []
    nJ = sum(1 for lines in pages for L in lines if not L["bold"] and re.match(r"^\d{1,2}\.\d{1,3}\.?\s+[A-Z]", L["t"]) or L["bold"] and re.match(r"^\d{1,2}\.\d{1,2}\.\d{1,2}\.?\s", L["t"]))
    nA = sum(1 for lines in pages for L in lines if L["b0"] and ART_A.match(L["t"]))
    famJ = nJ > nA
    for i, lines in enumerate(pages):
        H = doc[i].rect.height; drop = set(); lab = None; cands = []
        for L, k in zone[i]:
            if cnt[k] >= thr or CLASSIF.match(L["t"]):
                drop.add(id(L))
                if k[1] == "<L>": cands.append(L)
        # numéro imprimé : de préférence en bas, sinon en haut ; jamais le code de la publication (identique partout)
        cands.sort(key=lambda L: (0 if L["y"] > 0.5 * H else 1, -L["y"]))
        if cands: lab = cands[0]["t"]
        labels.append(lab)
        rest = [L for L in lines if id(L) not in drop and L["y"] >= 0.068 * H and not CLASSIF.match(L["t"]) and not BLANK.match(L["t"])]
        # notes de bas de page : bloc final en petit corps qui commence par un numéro
        cut = None
        if famJ:                                                          # uniquement pour la famille AJP (les ATP ont des tableaux en petit corps)
            for k in range(len(rest) - 1, -1, -1):
                L = rest[k]
                if L["size"] > body - 1.4 or L["y"] < 0.45 * H or L["bold"]: break
                cut = k
        if cut is not None: nfoot[0] += len(rest) - cut; rest = rest[:cut]
        kept.append(rest)
    return kept, labels


def is_toc_page(lines, front):
    if len(lines) < 4: return False
    lead = sum(1 for L in lines if re.search(r"\.{4,}|(\. ){4,}", L["t"]))
    hit = sum(1 for L in lines if re.search(r"\.{4,}|(\. ){4,}", L["t"]) or re.search(r"\s(?:[A-Za-z]{0,8}\d{0,2}[A-Z]?-)?\d{1,3}$|\s[ivxlIVXL]{1,6}$", L["t"]) and len(L["t"]) < 110)
    if front: return lead >= 3 or hit / len(lines) >= 0.45
    return lead >= 8 and hit / len(lines) >= 0.35


def tables_of(page):
    res = []
    try:
        if len(page.get_cdrawings()) < 4: return res                      # pas de filets : pas de tableau tracé
        words = None
        for t in page.find_tables().tables:
            if t.row_count < 2 or t.col_count < 2: continue
            if words is None: words = page.get_text("words", flags=pymupdf.TEXT_PRESERVE_LIGATURES)
            rows = []
            for r in t.rows:                                              # texte des cellules reconstruit mot à mot (les espaces sont conservés)
                cells = []
                for c in r.cells:
                    if c is None: cells.append(""); continue
                    x0, y0, x1, y1 = c
                    ws = [w for w in words if x0 - 1 <= (w[0] + w[2]) / 2 <= x1 + 1 and y0 - 1 <= (w[1] + w[3]) / 2 <= y1 + 1]
                    ws.sort(key=lambda w: (round(w[1] / 4), w[0])); cells.append(norm(fix_lig(" ".join(w[4] for w in ws))))
                if any(cells): rows.append(cells)
            if len(rows) < 2 or sum(1 for r in rows for c in r if c) < 4: continue
            txt = "\n".join(" | ".join(r) for r in rows)
            res.append((pymupdf.Rect(t.bbox), txt))
    except Exception:
        pass
    return res


def chap_from_label(lab):
    if not lab: return None, None
    if re.fullmatch(r"[ivxlcdmIVXLCDM]+", lab): return "FRONT", "front"
    m = re.match(r"^(.+?)-\d+$", lab)
    if not m: return None, None                                           # numérotation continue : pas d'information
    pre = m.group(1); low = pre.lower()
    if low.startswith(("gloss", "lex", "loa", "acr", "abb")): return pre, "glossary"
    if low.startswith(("index", "lep", "toc", "ref")): return pre, "toc"
    return pre, "body"


def split_units(units, maxw=MAXW):
    """units : [(texte, page, pdf_page)] -> morceaux d'au plus ~maxw mots, coupés aux limites d'alinéa puis de phrase."""
    flat = []
    for t, pg, pp in units:
        w = t.split()
        if len(w) <= maxw: flat.append((t, pg, pp)); continue
        sents = re.split(r"(?<=[.;:])\s+(?=[A-Z(])", t); cur = []
        for s in sents:
            if cur and len(" ".join(cur + [s]).split()) > maxw: flat.append((" ".join(cur), pg, pp)); cur = []
            sw = s.split()
            while len(sw) > maxw: flat.append((" ".join(sw[:maxw]), pg, pp)); sw = sw[maxw:]
            cur.append(" ".join(sw))
        if cur: flat.append((" ".join(cur), pg, pp))
    out, cur, n = [], [], 0
    for t, pg, pp in flat:
        k = len(t.split())
        if cur and n + k > maxw: out.append(cur); cur, n = [], 0
        cur.append((t, pg, pp)); n += k
    if cur: out.append(cur)
    return [("\n".join(u[0] for u in c), c[0][1], c[0][2]) for c in out]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf"); ap.add_argument("--pub", required=True); ap.add_argument("--edition", default="")
    ap.add_argument("--out", required=True); ap.add_argument("--report", required=True)
    ap.add_argument("--keep-toc", action="store_true"); ap.add_argument("--no-tables", action="store_true"); ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    doc = pymupdf.open(a.pdf)
    pages, body = read_pages(doc)
    pages, labels = strip_running(doc, pages, body)
    anomalies = collections.Counter(); notrel = 0
    # état courant
    st = {"chapter": "FRONT", "ctitle": "", "section": "", "article": None, "title": "", "mode": "front", "label_mode": None, "para": None, "lastj": {}}
    titles = {}
    passages = []          # dicts sans id
    cur = None             # passage texte en cours : {meta..., units:[(t,page,pdf)]}
    family = collections.Counter()

    def close():
        nonlocal cur
        if cur and cur["units"]:
            for txt, pg, pp in split_units(cur["units"]):
                if len(txt.strip()) < 3: continue
                p = {k: cur[k] for k in ("chapter", "chapter_title", "section", "article", "title", "kind")}
                p.update(page=pg, pdf_page=pp, text=txt); passages.append(p)
        cur = None

    def kind_now(): return "glossary" if st["mode"] == "glossary" else "toc" if st["mode"] == "toc" else "text"

    def open_new(first=None, pg=None, pp=None):
        nonlocal cur
        close()
        cur = {"chapter": st["chapter"], "chapter_title": st["ctitle"], "section": st["section"], "article": st["article"], "title": st["title"], "kind": kind_now(), "units": []}
        if first: cur["units"].append((first, pg, pp))

    def emit(kind, text, pg, pp, title=None):
        passages.append({"chapter": st["chapter"], "chapter_title": st["ctitle"], "section": st["section"], "article": st["article"], "title": title if title is not None else st["title"], "kind": kind, "page": pg, "pdf_page": pp, "text": text})

    covered, nonblank, toc_pages, ntables = set(), 0, 0, 0
    seen_body = False
    for i, lines in enumerate(pages):
        pp = i + 1; lab = labels[i]; page = doc[i]
        if not lines: continue
        nonblank += 1
        notrel += sum(1 for L in lines if NOREL.search(L["t"]))
        pre, lmode = chap_from_label(lab)
        if lmode == "front" and seen_body: pre, lmode = None, None           # chiffre romain isolé au milieu du corps
        if lmode == "body": seen_body = True
        if pre and pre != st.get("label_pre"):
            # changement de chapitre d'après le numéro de page imprimé (« 3-12 » -> chapitre 3)
            close(); st["label_pre"] = pre
            if lmode == "front": st.update(chapter="FRONT", mode="front")
            else:
                st.update(chapter=pre, ctitle=titles.get(pre, ""), section="", article=None, title="", para=None, mode="glossary" if lmode == "glossary" else "toc" if lmode == "toc" else "body")
        opens = any(L["size"] >= body + 1.5 and (CHAP.match(L["t"]) or ANNEX.match(L["t"])) for L in lines[:4]) and lmode != "front" and (seen_body or lab)
        toc = st["mode"] == "toc" or (is_toc_page(lines, st["mode"] == "front") and not opens)
        if opens:                                                         # page d'ouverture de chapitre avec mini-sommaire : on retire ses lignes
            keep = []
            for k, L in enumerate(lines):
                lead = re.search(r"\.{4,}|(\. ){4,}", L["t"]); nxt = lines[k + 1] if k + 1 < len(lines) else None
                if lead or (nxt is not None and re.search(r"\.{4,}|(\. ){4,}", nxt["t"]) and nxt["x"] > L["x"] + 8 and not L["bold"]): continue
                keep.append(L)
            lines = keep
        if toc:
            toc_pages += 1; close()
            if a.keep_toc: emit("toc", "\n".join(L["t"] for L in lines), lab, pp, title="")
            covered.add(pp); continue
        tabs = [] if a.no_tables else tables_of(page)
        margin = collections.Counter(round(L["x"]) for L in lines if not L["bold"]).most_common(1)
        left = min((L["x"] for L in lines), default=0); mode_x = margin[0][0] if margin else left
        captions = []
        done_tab = set()
        for L in lines:
            t = L["t"]; headish = L["b0"] and (L["bold"] or L["nb"] >= 0.5 * len(t)) or L["size"] >= body + 1.5
            atleft = L["x"] <= min(mode_x, left + 30) + 6
            # tableaux : le texte situé dans un tableau détecté est remplacé par le tableau lui-même
            inside = None
            for k, (r, txt) in enumerate(tabs):
                if r.y0 - 2 <= L["y"] <= r.y1 + 2 and r.x0 - 3 <= L["x"] <= r.x1 + 3: inside = k; break
            if inside is not None:
                if inside not in done_tab:
                    done_tab.add(inside); close(); cap = next((c for c in reversed(captions) if c[0] == "T"), None)
                    emit("table", tabs[inside][1], lab, pp, title=cap[1] if cap else st["title"]); ntables += 1; covered.add(pp)
                continue
            m = CAPT.match(t)
            if m and (headish or len(t) < 140) and re.search(r"\d", m.group(2)) and (m.group(3) == "" or m.group(3)[0].isupper() or headish):
                isT = m.group(1).lower().startswith("tab"); captions.append(("T" if isT else "F", t))
                if not isT or not tabs: close(); emit("figure_caption", t, lab, pp, title=t); covered.add(pp)
                continue
            if headish and len(t) < 160:
                m = CHAP.match(t) or ANNEX.match(t)
                if m:
                    num = m.group(1); big = L["size"] >= body + 1.5 or L["x"] > left + 40
                    if st.get("label_pre") and st["mode"] != "front" and re.search(r"-?\d", str(st["label_pre"])) and labels[i] and chap_from_label(labels[i])[1] == "body":
                        # pages numérotées « 3-12 » : le titre doit correspondre au préfixe et n'est pris qu'une fois
                        okh = (st["label_pre"] == num or st["label_pre"].startswith(num + "-") or (num and re.fullmatch(re.escape(num) + r"[A-Z]", st["label_pre"]) and re.match(r"^[A-Z] ", m.group(2))) or (m.re is ANNEX and re.search(r"(TO|to) (ANNEX|Annex) " + re.escape(st["label_pre"].split("-")[0]), t))) and not titles.get(st["label_pre"])
                    else:
                        okh = big and not titles.get(num) and st["mode"] != "toc"
                    if not okh: m = None
                if m:
                    close(); num = m.group(1)
                    key = st["label_pre"] if (st.get("label_pre") and labels[i] and chap_from_label(labels[i])[1] == "body") else num
                    ttl = norm(m.group(2))
                    if key != num and re.fullmatch(re.escape(num) + r"[A-Z]", str(key)) and ttl[:2] == str(key)[-1] + " ": ttl = ttl[2:]
                    st.update(chapter=key, ctitle=ttl, section="", article=None, title="", para=None, mode="body"); titles[key] = ttl; st["_ct_open"] = (pp, L["y"]); covered.add(pp)
                    st["lastj"] = {}
                    continue
                m = SECT.match(t) or PART.match(t)
                if m:
                    close(); st.update(section=norm(t), article=None if st.get("fam") != "A" else st["article"], title=""); covered.add(pp); st["_h"] = ("section", pp, L["y"], L["size"]); continue
                if GLOSS.match(t) and (L["size"] >= body + 1.5 or L["x"] > left + 40 or st["mode"] == "glossary"):
                    close(); st.update(mode="glossary", section=norm(t), article=None, title=norm(t))
                    if not (pre and lmode in ("glossary",)): st.update(chapter="LEX", ctitle=norm(t))
                    covered.add(pp); continue
                if TOCH.match(t) and st["mode"] == "front":
                    close(); st.update(title=norm(t)); continue
                # suite d'un titre de chapitre sur deux lignes
                o = st.get("_ct_open")
                if o and o[0] == pp and 0 < L["y"] - o[1] < 2.6 * L["size"] and L["size"] >= body + 1.5 and not ART_A.match(t):
                    st["ctitle"] = norm(st["ctitle"] + " " + t); titles[st["chapter"]] = st["ctitle"]; st["_ct_open"] = (pp, L["y"]); continue
            st["_ct_open"] = None
            if not (headish and L["bold"]): st["_h"] = None
            # articles
            if st["mode"] in ("body", "front"):
                mr = re.match(r"^(\d{4,5})\s*(?:[—–\-]|to|through)\s*(\d{4,5})\s+(\S.*)$", t)        # plage d'articles : « 0671—0684 Titre »
                if mr and headish and atleft:
                    family["A"] += 1; st.update(article=mr.group(1) + "-" + mr.group(2), title=norm(mr.group(3)), para=None, fam="A")
                    open_new(); covered.add(pp); continue
                m = ART_A.match(t)
                if m and headish and atleft and len(t) < 200 and not re.match(r"^(19|20)\d\d$", m.group(1)):
                    family["A"] += 1; st.update(article=m.group(1), title=norm(m.group(2)), para=None, fam="A")
                    open_new(); covered.add(pp); continue
                m = ART_J.match(t)
                if m and atleft and not re.search(r"\.{4,}", t):
                    num = m.group(1); parts = num.split("."); depth = len(parts); ok = False
                    if depth == 2 and (m.group(2) or True):
                        last = st["lastj"].get(parts[0], 0); n2 = int(parts[1])
                        chapnum = re.sub(r"^ANNEX ", "", str(st["chapter"]))
                        chap_ok = chapnum == parts[0] and family["A"] <= family["J"] + 5
                        ok = chap_ok and last < n2 <= last + 6 and not headish or (headish and chap_ok and last < n2 <= last + 6)
                        if ok: st["lastj"][parts[0]] = n2
                    elif depth >= 3: ok = headish and family["A"] <= family["J"] + 5
                    if ok:
                        family["J"] += 1; st["fam"] = "J"
                        if depth >= 3 or (headish and m.group(2) and len(t) < 110):
                            st.update(article=num, title=norm(m.group(2) or ""), para=None); open_new()
                        else:
                            st.update(article=num, para=None); open_new(m.group(2) or "", lab, pp)
                        covered.add(pp); continue
                # intertitre en gras non numéroté (AJP) : devient le titre des paragraphes qui suivent
                if headish and L["bold"] and len(t) < 110 and not SUB.match(t) and not PARA.match(t) and not t.endswith((".", ":", ";", ",")) and st.get("fam") != "A":
                    h = st.get("_h")
                    if h and h[1] == pp and 0 < L["y"] - h[2] < 1.75 * L["size"] and abs(h[3] - L["size"]) < 0.3:      # suite d'un titre sur deux lignes
                        st[h[0]] = norm(st[h[0]] + " " + t); st["_h"] = (h[0], pp, L["y"], L["size"]); continue
                    close(); st["title"] = t; st["_h"] = ("title", pp, L["y"], L["size"])
                    if st.get("fam") != "J": st["article"] = None
                    continue
                m = PARA.match(t)
                if m and L["b0"] and atleft and st.get("fam") != "J" and (st["article"] is None or str(st["article"]).startswith("§")):
                    st.update(article="§" + m.group(1), title=norm(re.split(r"(?<=[a-z)])\.\s", m.group(2))[0])[:120], para=m.group(1))
                    open_new(t, lab, pp); covered.add(pp); continue
            if cur is None: open_new()
            # nouvelle unité à chaque alinéa repéré, sinon on prolonge l'unité courante
            if cur["units"] and not SUB.match(t) and cur["units"][-1][2] == pp and not cur["units"][-1][0].endswith((".", ":")) or (cur["units"] and not SUB.match(t) and cur["units"][-1][2] != pp and not cur["units"][-1][0].rstrip().endswith((".", ":", ";"))):
                u = cur["units"][-1]; cur["units"][-1] = (u[0] + " " + t, u[1], u[2])
            elif cur["units"] and not SUB.match(t) and cur["units"][-1][2] == pp and len(t) > 0 and not (t[0].isupper() and L["x"] <= mode_x + 2 and False):
                u = cur["units"][-1]; cur["units"][-1] = (u[0] + " " + t, u[1], u[2])
            else: cur["units"].append((t, lab, pp))
            covered.add(pp)
    close()

    # nettoyage, identifiants stables
    # tableaux trop longs : recoupés par lignes, l'en-tête (1re ligne) répété
    split = []
    for p in passages:
        rows = p["text"].split("\n")
        if p["kind"] != "table" or len(p["text"].split()) <= MAXW + 50 or len(rows) < 3: split.append(p); continue
        head, cur, n = rows[0], [], 0
        for r in rows[1:]:
            k = len(r.split())
            if cur and n + k > MAXW: split.append(dict(p, text="\n".join([head] + cur))); cur, n = [], 0
            cur.append(" ".join(r.split()[:MAXW]) if k > MAXW else r); n += min(k, MAXW)
        if cur: split.append(dict(p, text="\n".join([head] + cur)))
    passages = split
    out, seen = [], collections.Counter()
    for p in passages:
        p["text"] = p["text"].strip()
        if not p["text"]: continue
        if p["kind"] == "toc" and not a.keep_toc: continue
        if p["chapter"] == "FRONT": p["chapter"] = "FRONT"
        base = p["article"] or ("ch" + str(p["chapter"]) + "-p" + str(p["pdf_page"]))
        key = f'{a.pub}:{p["chapter"]}:{base}' if p["article"] else f"{a.pub}:{base}"
        key = re.sub(r"\s+", "_", key); seen[key] += 1
        p["id"] = f"{key}:{seen[key]}"; p["pub"] = a.pub; p["edition"] = a.edition
        out.append({k: p[k] for k in ("id", "pub", "edition", "chapter", "chapter_title", "section", "article", "title", "page", "pdf_page", "kind", "text")})
    ids = collections.Counter(p["id"] for p in out)
    anomalies["ids_dupliques"] = sum(1 for v in ids.values() if v > 1)
    with open(a.out, "w", encoding="utf-8") as f:
        for p in out: f.write(json.dumps(p, ensure_ascii=False) + "\n")
    lens = [len(p["text"].split()) for p in out if p["kind"] == "text"] or [0]
    body_p = [p for p in out if p["kind"] in ("text", "table", "figure_caption") and p["chapter"] != "FRONT"]
    cov_pages = {p["pdf_page"] for p in out} | {pp for pp in covered}
    anomalies["pages_sans_numero_imprime"] = sum(1 for i, l in enumerate(labels) if not l and pages[i])
    anomalies["passages_tres_courts(<8 mots)"] = sum(1 for p in out if p["kind"] == "text" and len(p["text"].split()) < 8)
    anomalies["passages_longs(>450 mots)"] = sum(1 for p in out if len(p["text"].split()) > 450)
    rep = {"pub": a.pub, "edition": a.edition, "sha256": hashlib.sha256(open(a.pdf, "rb").read()).hexdigest(), "pages": len(doc), "pages_non_vides": nonblank, "pages_sommaire_index": toc_pages,
           "famille_detectee": "ATP/MTP (articles à 4-5 chiffres)" if family["A"] >= family["J"] else "AJP (paragraphes n.nn)", "taille_corps": body,
           "passages": len(out), "par_kind": dict(collections.Counter(p["kind"] for p in out)), "mots": sum(len(p["text"].split()) for p in out),
           "pages_couvertes_pct": round(100 * len(cov_pages) / max(1, nonblank), 1),
           "chapitres": len({p["chapter"] for p in out}), "articles_distincts": len({(p["chapter"], p["article"]) for p in out if p["article"]}),
           "sans_article": sum(1 for p in body_p if not p["article"]), "sans_article_pct": round(100 * sum(1 for p in body_p if not p["article"]) / max(1, len(body_p)), 1),
           "sans_chapitre": sum(1 for p in out if not p["chapter"]), "sans_titre_chapitre": sum(1 for p in body_p if not p["chapter_title"]),
           "longueur_mediane_mots": int(statistics.median(lens)), "longueur_max_mots": max(len(p["text"].split()) for p in out) if out else 0,
           "mentions_NOT_RELEASABLE": notrel, "lignes_notes_bas_de_page_retirees": nfoot[0], "anomalies": dict(anomalies)}
    json.dump(rep, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: rep[k] for k in ("pub", "pages", "passages", "par_kind", "mots", "pages_couvertes_pct", "sans_article_pct", "sans_titre_chapitre", "longueur_mediane_mots", "longueur_max_mots", "mentions_NOT_RELEASABLE", "anomalies")}, ensure_ascii=False))
    if a.debug:
        import random
        random.seed(1)
        for p in random.sample(out, min(12, len(out))): print("DEBUG", p["id"], "|", p["chapter"], "|", p["chapter_title"][:30], "|", p["article"], "|", p["title"][:30], "|", p["page"], p["pdf_page"], p["kind"], "|", p["text"][:70].replace("\n", " / "))


if __name__ == "__main__":
    main()
