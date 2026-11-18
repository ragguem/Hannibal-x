#!/usr/bin/env python3
"""Construit le classeur de relecture a envoyer a l'expert.

Usage :
    python build_expert_pack.py kb/signals.json kb/extraction_report.json \
           tests/testset.jsonl expert/relecture_expert.xlsx [--seed 11]

Necessite : pip install openpyxl
Les colonnes jaunes sont celles que l'expert remplit. Rien n'est calcule dans
le classeur : c'est une grille de relecture.
"""
import argparse
import json
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3A5F")
EXPERT_FILL = PatternFill("solid", fgColor="FFF2CC")
EXAMPLE_FILL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet(wb, title, headers, widths, expert_cols, rows, example=None, yesno_cols=()):
    ws = wb.create_sheet(title)
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BORDER
        ws.column_dimensions[c.column_letter].width = widths[j - 1]
    ws.row_dimensions[1].height = 42
    all_rows = ([example] if example else []) + rows
    for i, row in enumerate(all_rows, start=2):
        is_example = example is not None and i == 2
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = Font(name=FONT, size=10, italic=is_example)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = BORDER
            if is_example:
                c.fill = EXAMPLE_FILL
            elif j in expert_cols:
                c.fill = EXPERT_FILL
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    for col in yesno_cols:
        dv = DataValidation(type="list", formula1='"oui,non,a discuter"', allow_blank=True)
        ws.add_data_validation(dv)
        letter = ws.cell(row=1, column=col).column_letter
        dv.add(f"{letter}2:{letter}{len(all_rows) + 1}")
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("signals"); ap.add_argument("report"); ap.add_argument("testset")
    ap.add_argument("out"); ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--llm", help="sortie de 'rag.py batch' : ajoute la proposition du systeme")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    signals = json.loads(Path(a.signals).read_text("utf-8"))
    report = json.loads(Path(a.report).read_text("utf-8"))
    cases = [json.loads(l) for l in Path(a.testset).read_text("utf-8").splitlines() if l.strip()]

    wb = Workbook()
    ws = wb.active
    ws.title = "Lisez-moi"
    intro = [
        ("HANNIBAL X — Grille de relecture expert", True),
        ("", False),
        ("Objet", True),
        ("Ce classeur sert a valider (1) les messages de test du systeme et (2) l'extraction "
         "automatique de la publication MTP 1(D) Vol. II. Les messages ont ete fabriques par un "
         "script a partir de la publication ; ils doivent etre controles par une personne qui "
         "connait la procedure avant de servir de reference.", False),
        ("", False),
        ("Comment remplir", True),
        ("• Seules les colonnes a fond JAUNE sont a remplir. Ne modifiez pas les autres.", False),
        ("• La premiere ligne de chaque onglet (fond VERT, en italique) est un exemple de remplissage.", False),
        ("• Colonnes oui/non : choisir « oui », « non » ou « a discuter » dans la liste.", False),
        ("• En cas de « non », donner la version correcte dans la colonne voisine.", False),
        ("", False),
        ("Onglets", True),
        ("1. Messages — messages radio de test : la trame est-elle realiste ? le sens est-il le bon ? "
         "La colonne « Proposition du systeme » montre l'explication produite par l'IA locale : "
         "la corriger dans la colonne voisine, ou y ecrire l'explication qu'un operateur devrait recevoir.", False),
        ("2. Extraction — echantillon de signaux extraits : le texte correspond-il a la page de la publication ?", False),
        ("3. Anomalies — points releves automatiquement dans la publication (codes en double, numeros absents).", False),
        ("4. Questions — points de procedure que la publication ne tranche pas.", False),
        ("", False),
        ("Source", True),
        ("MTP 1(D), Vol. II, Multinational Maritime Tactical Signal and Maneuvering Book, mars 2003, "
         "Change 1 (NATO-UNCLASSIFIED). Document a diffusion restreinte : ne pas publier ce classeur "
         "sur un support librement accessible.", False),
    ]
    ws.column_dimensions["A"].width = 120
    for i, (text, bold) in enumerate(intro, start=1):
        c = ws.cell(row=i, column=1, value=text)
        c.font = Font(name=FONT, bold=bold, size=14 if i == 1 else 10)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---- 1. Messages
    by_cat = {}
    for c in cases:
        by_cat.setdefault(c["category"], []).append(c)
    core_chapters = ("Chapter 3 ", "Chapter 4 ", "Chapter 5 ", "Chapter 6 ", "Chapter 7 ",
                     "Chapter 8 ", "Chapter 9 ")

    def pick(cat, n, core_first=True):
        pool = by_cat.get(cat, [])
        core = [c for c in pool if any(k in c["expected"].get("reference", "") for k in core_chapters)]
        rest = [c for c in pool if c not in core]
        rng.shuffle(core); rng.shuffle(rest)
        chosen = (core[: int(n * 0.7)] + rest)[:n] if core_first else (rest + core)[:n]
        return chosen

    selected = (pick("clean_param", 20) + pick("clean_fixed", 20) + pick("needs_params", 30)
                + by_cat.get("err_missing_side", []) + pick("err_out_of_range", 4)
                + pick("err_spare", 3) + pick("err_not_releasable", 2))
    llm = {}
    if a.llm:
        for line in Path(a.llm).read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                llm[r["case_id"]] = r
    rows = []
    for c in selected:
        e = c["expected"]
        r = llm.get(c["id"], {})
        prop = r.get("explanation_fr") or ""
        if r.get("explanation_source") == "repli_deterministe":
            prop = "[repli sans IA] " + prop
        if r.get("ambiguities"):
            prop += "\nPoints signalés : " + " | ".join(r["ambiguities"])
        rows.append([c["id"], c["category"], c["written_text"], c["spoken_text"],
                     e.get("signal") or e.get("base_signal", ""), e.get("status", ""),
                     e.get("source_text", e.get("reason", "")), e.get("reference", ""),
                     "", "", "", prop, "", "", c["note"]])
    example = ["EXEMPLE", "clean_param", "CHARLIE THIS IS HANNIBAL TURN STBD 9 OVER",
               "CHARLIE THIS IS HANNIBAL TURN STARBOARD NINER OVER",
               "TURN [PORT or STBD] [1 to 36] or [000 to 359]", "ok",
               "TURN TOGETHER in the direction indicated, the number of tens of degrees indicated, "
               "or to the course indicated.",
               "MTP 1(D), Vol. II, Chapter 6 (TURN), art. 601, p. 6-2",
               "non", "(ecrire ici la trame telle qu'elle serait reellement prononcee)", "oui",
               "Les navires doivent virer ensemble à tribord de 90 degrés par rapport à leur cap actuel.",
               "Charlie : virez ensemble de 90 degres sur tribord.",
               "", "exemple de remplissage"]
    sheet(wb, "Messages",
          ["ID", "Categorie", "Message ecrit", "Message parle (pour l'audio)", "Signal attendu",
           "Resultat attendu", "Texte de la publication", "Reference",
           "EXPERT : trame radio realiste ?", "EXPERT : message corrige (si non)",
           "EXPERT : signal et sens corrects ?", "Proposition du systeme en francais (IA locale)",
           "EXPERT : explication correcte en francais", "EXPERT : commentaire", "Note du generateur"],
          [9, 15, 38, 46, 24, 14, 50, 34, 14, 40, 14, 48, 44, 30, 34],
          {9, 10, 11, 13, 14}, rows, example, yesno_cols=(9, 11))

    # ---- 2. Extraction
    assigned = [s for s in signals if s["status"] == "assigned"]
    sample = rng.sample(assigned, 50)
    longest = sorted(assigned, key=lambda s: -len(s["full_text"]))[:5]
    flagged = [s for s in signals if s["signal"] in report.get("duplicate_codes", {})]
    seen, rows = set(), []
    for s in sample + longest + flagged:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        rows.append([s["id"], s["signal"], s["status"], s["raw"], s["page"], s["pdf_page"],
                     s["change"], "", "", ""])
    example = ["EXEMPLE", "SPEED D", "assigned", "SPEED D. . . . DECREASE speed by ____ knots.",
               "8-1", 141, "CHANGE 1", "oui", "", "exemple de remplissage"]
    sheet(wb, "Extraction",
          ["ID", "Signal", "Statut", "Texte extrait (mise en page d'origine)", "Page", "Page du PDF",
           "Amendement", "EXPERT : conforme a la publication ?", "EXPERT : correction",
           "EXPERT : commentaire"],
          [22, 26, 12, 90, 8, 9, 12, 14, 44, 30], {8, 9, 10}, rows, example, yesno_cols=(8,))

    # ---- 3. Anomalies
    rows = []
    for code, pages in report.get("duplicate_codes", {}).items():
        rows.append(["Code present plusieurs fois", code, "pages " + ", ".join(pages),
                     "Meme signal repete dans plusieurs articles, ou erreur d'impression ?", "", ""])
    for group, gaps in report.get("numbering_gaps", {}).items():
        rows.append(["Numeros absents", group, ", ".join(f"{group}{n}" for n in gaps),
                     "Ces numeros n'apparaissent pas dans le PDF. Absents de l'edition, ou page manquante ?",
                     "", ""])
    for code in report.get("contains_not_releasable", []):
        rows.append(["Contenu NOT RELEASABLE", code, "", "Sens complet ou partiel non diffuse dans "
                     "cette edition. Le systeme repondra « non disponible ».", "", ""])
    example = ["EXEMPLE", "1L", "pages 13-20, 13-20", "Le premier 1L est-il en realite 1I ?",
               "Oui, erreur d'impression : lire 1I.", "exemple de remplissage"]
    sheet(wb, "Anomalies",
          ["Type", "Code", "Detail", "Question", "EXPERT : reponse", "EXPERT : commentaire"],
          [28, 14, 34, 60, 50, 30], {5, 6}, rows, example)

    # ---- 4. Questions
    questions = [
        "Quelle est la trame radio reelle pour un signal tactique (appel, methode d'execution, fin) ? "
        "Le generateur utilise trois gabarits : simple (THIS IS … OVER), EXECUTE TO FOLLOW, et "
        "IMMEDIATE EXECUTE … I SAY AGAIN … STANDBY EXECUTE OVER (repris des exemples p. 7-7 et 8-3).",
        "Comment sont transmis a la voix les blancs « ____ » d'un signal (chiffres a la suite, "
        "DESIG, TACK) ? Exemple : SPEED D « DECREASE speed by ____ knots ».",
        "Comment sont transmis les choix de liste (List A / List B) ? Exemple : AD4.",
        "Prononciation des chiffres en usage : NINER / FIFE / TREE / FOWER, ou formes courantes ?",
        "Les indicatifs du simulateur sont ALFA, HANNIBAL, CHARLIE, DELTA. ALFA, CHARLIE et DELTA "
        "sont aussi des lettres phonetiques : faut-il d'autres indicatifs pour eviter l'ambiguite ?",
        "Un TURN ou CORPEN sans PORT ni STBD est-il toujours a rejeter (art. 601) ?",
        "Cette edition (mars 2003, Change 1) est-elle celle en vigueur ? Sinon, quels amendements manquent ?",
        "Quels sont les 20 a 30 signaux les plus frequents en exercice ? Ils serviront a prioriser les tests.",
    ]
    rows = [[i, q, "", ""] for i, q in enumerate(questions, start=1)]
    example = ["EXEMPLE", "L'interface doit-elle afficher le texte anglais d'origine a cote du francais ?",
               "Oui, toujours les deux.", "exemple de remplissage"]
    sheet(wb, "Questions", ["N°", "Question", "EXPERT : reponse", "EXPERT : commentaire"],
          [9, 90, 70, 30], {3, 4}, rows, example)

    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    (out.parent / "message_ids.txt").write_text("\n".join(c["id"] for c in selected) + "\n", "utf-8")
    print(f"{out} : {len(selected)} messages, {len(seen)} signaux a controler, "
          f"{len(report.get('duplicate_codes', {}))} doublons, {len(questions)} questions")


if __name__ == "__main__":
    main()
