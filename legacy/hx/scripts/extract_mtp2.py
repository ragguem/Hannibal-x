#!/usr/bin/env python3
"""Extraction du MTP 1(D) Vol. II vers une base structuree.

Usage :
    python extract_mtp2.py chemin/vers/mtp_2.pdf dossier_sortie

Necessite l'outil `pdftotext` (poppler-utils) dans le PATH.

Sorties :
    signals.json    une entree par signal (code, sens exact, references)
    signals.csv     la meme table, pour relecture dans un tableur
    passages.jsonl  le texte integral decoupe par article, pour le RAG
    extraction_report.json  compteurs de controle

Principe : aucun texte n'est reformule. `raw` est le texte de la publication
tel qu'imprime (mise en page conservee) ; `meaning` est le meme texte remis sur
une ligne. En cas de doute, `raw` fait foi.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

CHAPTERS = {
    1: "GENERAL INSTRUCTIONS", 2: "SINGLE FLAGS AND PENNANTS", 3: "EMERGENCY",
    4: "FORM", 5: "STATION", 6: "TURN", 7: "CORPEN", 8: "SPEED", 9: "SCREEN",
    10: "ANTIAIR WARFARE", 11: "ADMINISTRATION", 12: "AMPHIBIOUS",
    13: "ANTISUBMARINE WARFARE", 14: "AIRCRAFT", 15: "GOVERNING GROUPS",
    16: "COMMUNICATIONS", 17: "COMMAND", 18: "ENTRY AND DEPARTURE", 19: "ENEMY",
    20: "ELECTRONIC WARFARE", 21: "EXERCISES", 22: "GUNNERY AND MISSILES",
    23: "HARASSMENT", 24: "INTERDICTION AND EMBARGO OPERATIONS",
    25: "METEOROLOGY", 26: "MINE WARFARE", 27: "NAVIGATION", 28: "N.B.C.",
    29: "RADAR", 30: "READINESS", 31: "REPLENISHMENT/TRANSFER",
    32: "ANTISURFACE WARFARE", 33: "TACTICAL", 34: "SUPPLEMENTARY TABLES",
    35: "STANDARD POSITION INDICATORS",
}
PUBLICATION = "MTP 1(D), Vol. II"

FOOTER = re.compile(r"^\s*((?:\d+|Index|LEP)-\d+|[IVXLC]+[ab]?)\s+(ORIGINAL|CHANGE \d+)\s*$")
NOISE = re.compile(r"^\s*(NATO-UNCLASSIFIED|MTP 1\(D\), Vol\. II|INTENTIONALLY BLANK)\s*$")
ARTICLE = re.compile(r"^\s*(\d{3,4})\s{1,3}([A-Z][A-Za-z0-9 ,/().&'’\-—]+?)\s*(?:\(See Chapter 1\.\))?\s*$")
# en-tete de signal : CODE suivi de points de conduite (deux au minimum)
HEADER = re.compile(r"^(\s*)(\S(?:.{0,78}?\S)?)\s*((?:\.\s?){2,}|\.\s{2,})\s*(.*)$")
HEADER_NODOTS = re.compile(r"^(\s{0,2})([A-Z0-9]\S*(?: \S+){0,2}?)\s{3,}(\S.*)$")
BRACKETS = re.compile(r"^[\[(][^\])]*[\])](?: [\[(][^\])]*[\])])*$")
MAINCODE = re.compile(r"^[A-Z]{2} ?\d{1,3}\*?$")
_SIDE = r"(?:PORT/STBD|PORT or STBD|PORT|STBD)"
_SUF = r"(?: (?:[A-Z]\d?|\d{1,2}|\d+ to \d+|or|" + _SIDE + r"|[\[(][^\])]*[\])]))*"
_KW = r"(?:FORM|STATION|TURN|CORPEN|SPEED|SCREEN|EMERG)"
STRICT = [
    ("main_vocabulary", re.compile(r"^[A-Z]{2} ?\d{1,3}\*?(?: " + _SIDE + r")?$")),
    ("maneuvering", re.compile(r"^(?:INT )?" + _KW + _SUF + r"$", re.I)),
    ("maneuvering_info", re.compile(r"^[A-Z] " + _KW + _SUF + r"$", re.I)),
    ("maneuvering", re.compile(r"^[\[(][^\])]*[\])](?: [\[(][^\])]*[\])])*$")),
    ("action_table", re.compile(r"^\d[A-Z]$")),
    ("designator", re.compile(r"^\d{1,2}[A-Z]{1,2}$")),
    ("two_letter", re.compile(r"^[A-Z]{2}$")),
]
STOP = {"IMI", "BT", "AR", "IX", "NOTE", "NOTES"}
TABLE_CHAPTERS = {1, 2, 34}      # instructions et tableaux : repris en passages seulement


def classify(head, chap):
    """Retourne le type de l'en-tete, ou None si ce n'est pas un groupe de signal."""
    if head.upper() in STOP or head.lower().startswith("example"):
        return None
    for kind, rx in STRICT:
        if rx.match(head):
            if kind == "two_letter":
                return {15: "governing_group", 35: "position_indicator"}.get(chap)
            if kind == "maneuvering" and chap == 3:
                return "emergency"
            return kind
    return None
EXAMPLE = re.compile(r"^(\s*)(Examples?:\s*)")
LISTSTART = re.compile(r"^\s*(List [A-Z]\b|Table [A-Z]\b|\d{1,2}\.\s|[A-Z]\.\s)")


def page_texts(pdf):
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                         check=True, capture_output=True).stdout.decode("utf-8", "replace")
    return out.split("\f")


def parse_header(ln, chap):
    """-> (indent, code, reste_de_ligne, type) ou None."""
    m = HEADER.match(ln)
    if m:
        head = re.sub(r"\s{2,}", " ", m.group(2).strip())
        kind = classify(head, chap)
        if kind:
            return len(m.group(1)), head, m.group(4), kind
    m = HEADER_NODOTS.match(ln)             # "ED37      CHANNEL. ..." (points absents)
    if m:
        head = m.group(2).strip()
        kind = classify(head, chap)
        if kind in ("main_vocabulary", "action_table"):
            return len(m.group(1)), head, m.group(3), kind
    st = ln.strip()                         # code seul sur sa ligne : "EMERG 7", "FORM G"
    indent = len(ln) - len(ln.lstrip())
    if st and indent <= 2 and " " in st and len(st) <= 12:
        kind = classify(st, chap)
        if kind in ("emergency", "maneuvering", "maneuvering_info"):
            return indent, st, "", kind
    return None


def clean_join(lines):
    """Remet des lignes de mise en page sur une seule ligne, sans reformuler."""
    text = ""
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if text.endswith("-") and s[:1].islower() and not text.endswith(" -"):
            text = text[:-1] + s          # cesure de fin de ligne
        else:
            text = (text + " " + s) if text else s
    return re.sub(r"\s{2,}", " ", text)


def extract(pdf):
    signals, passages = [], []
    cur = None            # signal en cours
    art = None            # article en cours (pour les passages)
    chap = None
    in_example_indent = None

    def close_signal():
        nonlocal cur
        if cur is None:
            return
        body = cur.pop("_lines")
        while body and not body[-1].strip():
            body.pop()
        cur["raw"] = "\n".join(body)
        cur.pop("_first_text", None); cur.pop("_open_name", None); cur.pop("_text_col", None)
        text = cur.pop("_text")
        main = []
        for i, ln in enumerate(text):
            if i > 0 and (LISTSTART.match(ln) or EXAMPLE.match(ln)):
                break
            main.append(ln)
        cur["meaning"] = clean_join(main)
        cur["full_text"] = clean_join(text)
        txt = cur["full_text"]
        if not txt:
            cur["status"] = "spare"
        elif txt.strip().upper().startswith("NOT RELEASABLE"):
            cur["status"] = "not_releasable"
        else:
            cur["status"] = "assigned"
        cur["contains_not_releasable"] = "NOT RELEASABLE" in txt
        cur["blanks"] = txt.count("____")
        cur["has_lists"] = any(LISTSTART.match(l) for l in body[1:])
        cur["examples"] = [clean_join([l]) for l in body if EXAMPLE.match(l)]
        signals.append(cur)
        cur = None

    def close_article():
        nonlocal art
        if art and any(l.strip() for l in art["_lines"]):
            art["text"] = "\n".join(art.pop("_lines")).strip("\n")
            passages.append(art)
        art = None

    for pdf_page, page in enumerate(page_texts(pdf), start=1):
        lines = page.split("\n")
        label, change = None, None
        for ln in lines:
            m = FOOTER.match(ln)
            if m:
                label, change = m.group(1), m.group(2)
        if label is None:
            continue
        mchap = re.match(r"^(\d+)-\d+$", label)
        if not mchap:                      # pages liminaires, index, LEP
            close_signal(); close_article()
            continue
        page_chap = int(mchap.group(1))
        if page_chap != chap:
            close_signal(); close_article()
            chap = page_chap
            art = {"publication": PUBLICATION, "chapter": chap,
                   "chapter_title": CHAPTERS.get(chap, ""), "article": None,
                   "article_title": "(chapter head)", "page_start": label,
                   "pdf_page_start": pdf_page, "change": change, "_lines": []}
        body = [l for l in lines if not FOOTER.match(l) and not NOISE.match(l)]

        blank_run = 0
        for ln in body:
            ma = ARTICLE.match(ln)
            if ma and ma.group(1).startswith(str(chap)) and len(ma.group(1)) == len(str(chap)) + 2 \
                    and ma.group(2).upper() == ma.group(2):
                close_signal(); close_article()
                art = {"publication": PUBLICATION, "chapter": chap,
                       "chapter_title": CHAPTERS.get(chap, ""), "article": ma.group(1),
                       "article_title": ma.group(2).strip(), "page_start": label,
                       "pdf_page_start": pdf_page, "change": change, "_lines": []}
                in_example_indent = None
                continue
            if art is not None:
                art["_lines"].append(ln)
                art["page_end"] = label

            if chap in TABLE_CHAPTERS:
                continue

            # fin d'un signal : grand blanc, ou retour de la prose en marge gauche
            if ln.strip():
                indent0 = len(ln) - len(ln.lstrip())
                if cur is not None and blank_run >= 1 and not parse_header(ln, chap) \
                        and (indent0 < min(cur["_text_col"] - 1, 8) or blank_run >= 4
                             or not any(t.strip() for t in cur["_text"])        # code libre
                             or (indent0 >= cur["_text_col"] + 12 and len(ln.strip()) < 60
                                 and ". ." not in ln and not LISTSTART.match(ln))):
                    close_signal()
                blank_run = 0
            else:
                blank_run += 1

            # bloc d'exemple : les lignes alignees sous "Example:" restent des exemples
            me = EXAMPLE.match(ln)
            if me:
                in_example_indent = len(me.group(1)) + len(me.group(2))
                if cur is not None:
                    cur["_lines"].append(ln); cur["_text"].append(ln)
                continue
            if in_example_indent is not None:
                indent = len(ln) - len(ln.lstrip())
                if ln.strip() and indent >= in_example_indent - 2:
                    if cur is not None:
                        cur["_lines"].append(ln); cur["_text"].append(ln)
                    continue
                if ln.strip():
                    in_example_indent = None

            ph = parse_header(ln, chap)
            # "FORM G" suivi de lignes entre crochets : elles completent le code
            if cur is not None and cur["_open_name"]:
                st = ln.strip()
                if BRACKETS.match(st):
                    cur["signal"] += " " + st
                    cur["_lines"].append(ln)
                    continue
                if ph and BRACKETS.match(ph[1]):
                    cur["signal"] += " " + ph[1]
                    cur["_lines"].append(ln)
                    cur["_text"] = [ph[2]]
                    cur["_text_col"] = len(ln) - len(ph[2])
                    cur["_open_name"] = False
                    continue
                if st:
                    cur["_open_name"] = False
            if ph:
                indent, head, rest, kind = ph
                if indent > 4 or kind == "designator":
                    # sous-entree (designateur d'une table) : rattachee au signal parent
                    if cur is not None and kind in ("designator", "action_table", "main_vocabulary"):
                        cur["sub_entries"].append({"code": head, "text": rest.strip(), "page": label})
                    if cur is not None:
                        cur["_lines"].append(ln); cur["_text"].append(ln)
                    continue
                close_signal()
                cur = {"signal": head, "publication": PUBLICATION, "chapter": chap,
                       "chapter_title": CHAPTERS.get(chap, ""),
                       "article": art["article"] if art else None,
                       "article_title": art["article_title"] if art else None,
                       "page": label, "pdf_page": pdf_page, "change": change,
                       "kind": kind, "sub_entries": [], "_indent": indent, "_lines": [ln],
                       "_text": [rest], "_text_col": (len(ln) - len(rest)) if rest else 4,
                       "_open_name": rest == ""}
                continue
            if cur is not None:
                cur["_lines"].append(ln); cur["_text"].append(ln)

    close_signal(); close_article()

    # finition : continuation des sous-entrees, identifiants, nettoyage
    seen = {}
    for s in signals:
        s.pop("_indent", None)
        base = re.sub(r"[^A-Z0-9]+", "_", s["signal"].upper()).strip("_")
        seen[base] = seen.get(base, 0) + 1
        s["id"] = f"MTP2:{base}" + (f"#{seen[base]}" if seen[base] > 1 else "")
        s["reference"] = (f"{PUBLICATION}, Chapter {s['chapter']} ({s['chapter_title']}), "
                          f"art. {s['article']}, p. {s['page']} [{s['change']}]")
    for i, p in enumerate(passages):
        p["id"] = f"MTP2:P{i:04d}"
        p.setdefault("page_end", p["page_start"])
        p["reference"] = (f"{PUBLICATION}, Chapter {p['chapter']} ({p['chapter_title']}), "
                          f"art. {p['article'] or '-'} {p['article_title']}, "
                          f"pp. {p['page_start']}–{p['page_end']}")
    return signals, passages


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    signals, passages = extract(pdf)

    (out / "signals.json").write_text(json.dumps(signals, ensure_ascii=False, indent=1), "utf-8")
    with open(out / "passages.jsonl", "w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    cols = ["id", "signal", "kind", "status", "chapter", "chapter_title", "article",
            "article_title", "page", "pdf_page", "change", "blanks", "has_lists", "meaning"]
    with open(out / "signals.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(signals)

    rep = {"signals_total": len(signals), "passages_total": len(passages),
           "by_status": {}, "by_kind": {}, "by_chapter": {}}
    for s in signals:
        for key, field in (("by_status", "status"), ("by_kind", "kind"), ("by_chapter", "chapter")):
            rep[key][str(s[field])] = rep[key].get(str(s[field]), 0) + 1
    counts = {}
    for s in signals:
        counts[s["signal"]] = counts.get(s["signal"], 0) + 1
    rep["duplicate_codes"] = {k: [x["page"] for x in signals if x["signal"] == k]
                              for k, v in counts.items() if v > 1}
    groups = {}
    for s in signals:
        m = re.match(r"^([A-Z]{2}) ?(\d+)", s["signal"])
        if m and s["kind"] == "main_vocabulary":
            groups.setdefault(m.group(1), []).append(int(m.group(2)))
    rep["numbering_gaps"] = {k: sorted(set(range(1, max(v) + 1)) - set(v))
                             for k, v in groups.items() if len(set(v)) != max(v)}
    rep["contains_not_releasable"] = [s["signal"] for s in signals if s["contains_not_releasable"]]
    (out / "extraction_report.json").write_text(json.dumps(rep, indent=1), "utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
