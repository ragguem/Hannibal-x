#!/usr/bin/env python3
"""RAG HANNIBAL X : index pgvector + explication anglais/francais par LLM local.

Tout est local : PostgreSQL + pgvector pour la recherche, Ollama pour les
embeddings et le LLM. Aucun appel a un service en ligne.

Commandes :
    python rag.py index   kb                 # (re)construit l'index
    python rag.py search  "question" [-n 5]  # recherche semantique seule
    python rag.py explain kb "CHARLIE THIS IS HANNIBAL TURN STARBOARD NINER OVER"
    python rag.py batch   kb tests/testset.jsonl sortie.jsonl [--ids fichier] [--limit 40]

Variables d'environnement (valeurs par defaut = conteneurs hannibal-pg et hannibal-ollama) :
    HX_PG      postgresql://postgres:hannibal@127.0.0.1:5433/hannibal
    HX_OLLAMA  http://127.0.0.1:11435
    HX_EMBED   bge-m3
    HX_LLM     gemma3:12b

Garde-fous :
  - le signal, son sens et sa reference viennent de la table (interpret.py), jamais du LLM ;
  - le LLM ne recoit que le texte de la publication et doit citer les identifiants fournis ;
  - toute reference citee qui n'etait pas fournie est retiree et signalee ;
  - si le signal est inconnu, non attribue ou non diffusable, le LLM n'est pas appele.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import psycopg
import requests

from interpret import KB, interpret

PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
OLLAMA = os.environ.get("HX_OLLAMA", "http://127.0.0.1:11435")
EMBED = os.environ.get("HX_EMBED", "bge-m3")
LLM = os.environ.get("HX_LLM", "gemma3:12b")
KB_VERSION = "MTP 1(D) Vol. II, March 2003, Change 1 — extraction 2026-11-12"


# ------------------------------------------------------------------ outils
def embed(texts):
    out = []
    for i in range(0, len(texts), 16):
        r = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED, "input": texts[i:i + 16]},
                          timeout=600)
        r.raise_for_status()
        out += r.json()["embeddings"]
    return out


def vec(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def chunk(text, size=1400, overlap=200):
    """Decoupe un article en morceaux, en coupant de preference sur une ligne vide."""
    text = text.strip()
    if len(text) <= size:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        cut = text.rfind("\n\n", start + size // 2, end)
        if cut == -1:
            cut = text.rfind("\n", start + size // 2, end)
        if cut == -1 or end == len(text):
            cut = end
        parts.append(text[start:cut].strip())
        if cut >= len(text):
            break
        start = max(cut - overlap, start + 1)
    return [p for p in parts if p]


# ------------------------------------------------------------------ index
def build_index(kb_dir):
    kb = Path(kb_dir)
    docs = []
    for line in (kb / "passages.jsonl").read_text("utf-8").splitlines():
        p = json.loads(line)
        for n, part in enumerate(chunk(p["text"])):
            docs.append((f"{p['id']}.{n}", "passage", p["chapter"], p["reference"], part))
    for s in json.loads((kb / "signals.json").read_text("utf-8")):
        if s["status"] == "assigned":
            docs.append((s["id"], "signal", s["chapter"], s["reference"],
                         s["signal"] + " . . . " + s["full_text"]))
    t0 = time.time()
    vectors = embed([f"{d[3]}\n{d[4]}"[:6000] for d in docs])
    dim = len(vectors[0])
    with psycopg.connect(PG) as con:
        con.execute("CREATE EXTENSION IF NOT EXISTS vector")
        con.execute("DROP TABLE IF EXISTS hx_chunks")
        con.execute(f"""CREATE TABLE hx_chunks (
            id text PRIMARY KEY, kind text, chapter int, reference text, body text,
            kb_version text, embedding vector({dim}))""")
        with con.cursor() as cur:
            cur.executemany(
                "INSERT INTO hx_chunks VALUES (%s,%s,%s,%s,%s,%s,%s::vector)",
                [(d[0], d[1], d[2], d[3], d[4], KB_VERSION, vec(v)) for d, v in zip(docs, vectors)])
        con.execute("CREATE INDEX ON hx_chunks USING hnsw (embedding vector_cosine_ops)")
    print(f"{len(docs)} morceaux indexes (dimension {dim}) en {time.time() - t0:.0f} s")


def search(query, n=5, kind=None, chapter=None):
    q = vec(embed([query])[0])
    where, args = [], [q]
    if kind:
        where.append("kind = %s"); args.append(kind)
    if chapter is not None:
        where.append("chapter = %s"); args.append(chapter)
    sql = ("SELECT id, kind, reference, body, 1 - (embedding <=> %s::vector) AS score FROM hx_chunks "
           + ("WHERE " + " AND ".join(where) + " " if where else "")
           + "ORDER BY embedding <=> %s::vector LIMIT %s")
    with psycopg.connect(PG) as con:
        rows = con.execute(sql, args + [q, n]).fetchall()
    return [{"id": r[0], "kind": r[1], "reference": r[2], "text": r[3], "score": round(r[4], 3)}
            for r in rows]


# ------------------------------------------------------------------ explication
SYSTEM = """You assist naval personnel in understanding NATO maritime tactical signals.
You are given: the radio message, the EXACT entry from the signal book (authoritative), the
parameters already decoded by a deterministic parser, and context passages from the same book.
Rules:
- Use ONLY the provided entry and passages. Never invent or complete a signal meaning.
- The signal entry and the decoded parameters are authoritative. Do not contradict them.
- If the entry contains blanks (____) that the message does not fill, say so in "ambiguities".
- Keep NATO terms (CORPEN, TURN, PORT, STBD, Guide, OTC...) in both languages.
- "references_used" must list only the IDs given to you, and only those you actually relied on.
- French must be natural French naval language. PORT / port = "bâbord". STBD / starboard = "tribord".
  Never swap them. Use the French wording given in DECODED PARAMETERS (FRENCH).
- explanation_en and explanation_fr: one or two plain sentences saying what the addressee must do or
  is being told. Do not quote the message, do not mention IDs, do not describe how you decoded it.
- TURN means the ships turn together (each ship turns at the same time); CORPEN with PORT/STBD
  means altering course by wheeling. In French: TURN = "virer ensemble" (never "demi-tour"),
  wheeling = "évoluer par conversion".
- "ambiguities": only real problems with THIS message (a blank not filled, an element not decoded,
  two possible readings). Empty list if there is none. Do not comment on other signals.
- "clarification_questions": only if an ambiguity exists. Otherwise empty list.
Answer in JSON only."""

SIDE_FR = {"PORT": "bâbord", "STBD": "tribord"}
SIDE_EN = {"PORT": "port", "STBD": "starboard"}


def params_en(p):
    """Sens des parametres, en anglais, impose au LLM."""
    out = []
    if "side" in p:
        out.append(f"side: {SIDE_EN[p['side']]}")
    if "relative_degrees" in p:
        out.append(f"amount: {p['relative_degrees']} degrees relative to the present course "
                   "(one or two numerals = tens of degrees)")
    if "true_course" in p:
        out.append(f"three numerals = the TRUE COURSE to end on: {p['true_course']:03d}. "
                   f"It is NOT a change of {p['true_course']} degrees")
    if "true_bearing" in p:
        out.append(f"true bearing {p['true_bearing']:03d}")
    if "relative_bearing_degrees" in p:
        out.append(f"relative bearing {p['relative_bearing_degrees']} degrees")
    if "speed_knots" in p:
        out.append(f"speed {p['speed_knots']} knots")
    if "formation_number" in p:
        out.append(f"formation number {p['formation_number']}")
    return "; ".join(out) or "none"


def params_fr(p):
    """Parametres decodes, dits en francais (repris tels quels par le LLM)."""
    out = []
    if "side" in p:
        out.append(f"bord : {SIDE_FR[p['side']]} ({p['side']})")
    if "relative_degrees" in p:
        out.append(f"{p['relative_degrees']} degrés par rapport au cap actuel")
    if "true_course" in p:
        out.append(f"trois chiffres = le CAP VRAI à atteindre : {p['true_course']:03d} "
                   f"(ce n'est PAS un changement de {p['true_course']} degrés)")
    if "true_bearing" in p:
        out.append(f"relèvement vrai {p['true_bearing']:03d}")
    if "relative_bearing_degrees" in p:
        out.append(f"relèvement relatif {p['relative_bearing_degrees']} degrés")
    if "speed_knots" in p:
        out.append(f"vitesse {p['speed_knots']} nœuds")
    if "formation_number" in p:
        out.append(f"formation numéro {p['formation_number']}")
    return " ; ".join(out) or "aucun"


def validate(ans, params):
    """Controle deterministe de la reponse du LLM. -> liste d'erreurs (vide si conforme)."""
    errs = []
    en = (ans.get("explanation_en") or "").lower()
    fr = (ans.get("explanation_fr") or "").lower()
    if not en or not fr:
        errs.append("explication manquante")
    side = params.get("side")
    if side:
        other = "PORT" if side == "STBD" else "STBD"
        if SIDE_FR[side] not in fr:
            errs.append(f"le français doit contenir « {SIDE_FR[side]} »")
        if SIDE_FR[other] in fr:
            errs.append(f"le français contient « {SIDE_FR[other]} » alors que le bord est {side}")
        if SIDE_EN[side] not in en:
            errs.append(f"l'anglais doit contenir « {SIDE_EN[side]} »")
        if re.search(rf"\b{SIDE_EN[other]}\b", en):
            errs.append(f"l'anglais contient « {SIDE_EN[other]} » alors que le bord est {side}")
    if "true_course" in params:
        v = params["true_course"]
        if re.search(rf"\bby 0*{v} degrees", en) or \
                re.search(rf"(modifi|chang|alt[ée]r)\w* (votre |le |son |leur )?cap de 0*{v}\b", fr):
            errs.append(f"{v:03d} est un cap vrai à atteindre, pas un changement de {v} degrés")
        if not (re.search(rf"course (of |to )?0*{v}\b", en) or "true course" in en):
            errs.append("l'anglais doit nommer le cap à atteindre (course)")
        if not re.search(rf"cap (vrai )?(de |au )?0*{v}\b", fr):
            errs.append("le français doit nommer le cap à atteindre (cap vrai …)")
    for key in ("relative_degrees", "true_course", "true_bearing", "relative_bearing_degrees",
                "speed_knots", "formation_number"):
        if key in params:
            v = params[key]
            forms = {str(v), f"{v:03d}"}
            for name, text in (("anglais", en), ("français", fr)):
                if not any(re.search(rf"(?<!\d){re.escape(x)}(?!\d)", text) for x in forms):
                    errs.append(f"la valeur {v} ({key}) est absente du {name}")
    return errs

SCHEMA = {
    "type": "object",
    "properties": {
        "explanation_en": {"type": "string"},
        "explanation_fr": {"type": "string"},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
        "clarification_questions": {"type": "array", "items": {"type": "string"}},
        "references_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["explanation_en", "explanation_fr", "ambiguities", "clarification_questions",
                 "references_used"],
}

REFUSALS = {
    "unknown_signal": ("This group is not in the signal book loaded in the system. No interpretation is given.",
                       "Ce groupe ne figure pas dans la publication chargée. Aucune interprétation n'est proposée."),
    "spare": ("This code exists in the signal book but has no meaning assigned.",
              "Ce code existe dans la publication mais aucun sens ne lui est attribué."),
    "not_releasable": ("The meaning of this signal is marked NOT RELEASABLE in this edition. It is not available.",
                       "Le sens de ce signal est marqué NOT RELEASABLE dans cette édition. Il n'est pas disponible."),
    "invalid_parameter": ("A parameter is outside the limits allowed for this signal.",
                          "Un paramètre est hors des limites admises pour ce signal."),
    "missing_parameter": ("A mandatory element of this signal is missing.",
                          "Un élément obligatoire de ce signal est absent."),
    "empty": ("No signal group was found in the message.",
              "Aucun groupe de signal n'a été trouvé dans le message."),
}


def explain(message, kb, k=3):
    t0 = time.time()
    res = interpret(message, kb)
    out = {"message": message, "status": res["status"], "to": res["to"], "from": res["from"],
           "method": res["method"], "signal": res["signal"], "signal_id": res["signal_id"],
           "reference": res["reference"], "source_text": res["meaning"], "params": res["params"],
           "parser_warnings": res["warnings"], "kb_version": KB_VERSION, "llm": None,
           "explanation_en": None, "explanation_fr": None, "ambiguities": [],
           "clarification_questions": [], "references_used": [], "rejected_references": [],
           "context": []}
    if res["status"] != "ok":
        en, fr = REFUSALS.get(res["status"], REFUSALS["unknown_signal"])
        detail = " ".join(res["warnings"])
        out.update({"explanation_en": en, "explanation_fr": fr + (" " + detail if detail else ""),
                    "seconds": round(time.time() - t0, 2)})
        return out

    entry = kb.by_id[res["signal_id"]]
    ctx = [c for c in search(f"{entry['signal']} {entry['full_text']}"[:800], n=k + 3,
                             kind="passage", chapter=entry["chapter"])][:k]
    out["context"] = [{"id": c["id"], "reference": c["reference"], "score": c["score"]} for c in ctx]
    allowed = {entry["id"]} | {c["id"] for c in ctx}
    user = (f"RADIO MESSAGE:\n{message}\n\n"
            f"ADDRESSEE: {res['to']}   ORIGINATOR: {res['from']}   METHOD: {res['method']}\n\n"
            f"SIGNAL ENTRY [ID {entry['id']}] — {entry['reference']}\n{entry['raw']}\n\n"
            f"DECODED PARAMETERS: {json.dumps(res['params'])}\n"
            f"MEANING OF THE PARAMETERS: {params_en(res['params'])}\n"
            f"DECODED PARAMETERS (FRENCH): {params_fr(res['params'])}\n"
            f"ELEMENTS AFTER THE GROUP, NOT DECODED: {res['extra']}\n\n"
            + "\n\n".join(f"PASSAGE [ID {c['id']}] — {c['reference']}\n{c['text']}" for c in ctx))
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    ans, errors = None, ["pas de reponse"]
    for attempt in range(2):                      # une seconde chance si le controle echoue
        r = requests.post(f"{OLLAMA}/api/chat", timeout=600, json={
            "model": LLM, "stream": False, "format": SCHEMA,
            "options": {"temperature": 0, "num_ctx": 8192}, "messages": messages})
        r.raise_for_status()
        try:
            ans = json.loads(r.json()["message"]["content"])
        except (json.JSONDecodeError, KeyError):
            ans, errors = None, ["reponse du LLM illisible"]
            continue
        errors = validate(ans, res["params"])
        out["llm_attempts"] = attempt + 1
        if not errors:
            break
        messages += [{"role": "assistant", "content": json.dumps(ans, ensure_ascii=False)},
                     {"role": "user", "content": "Your answer failed these checks: "
                      + "; ".join(errors) + ". Correct it and answer again in JSON."}]
    out["validation_errors"] = errors
    if ans is None or errors:
        # le texte du LLM n'est pas montre comme valide : on garde le texte de la publication
        # repli deterministe : sens exact de la publication + parametres decodes
        en = entry["meaning"]
        fr = "Sens d'après la publication (en anglais) : " + entry["meaning"]
        if res["params"]:
            en += " Parameters: " + params_en(res["params"]) + "."
            fr += " Paramètres : " + params_fr(res["params"]) + "."
        out.update({"llm": LLM, "explanation_en": en, "explanation_fr": fr,
                    "explanation_source": "repli_deterministe",
                    "rejected_explanation": ans, "seconds": round(time.time() - t0, 2)})
        return out
    out["explanation_source"] = "llm_valide"
    cited = [re.sub(r"^ID\s*", "", str(x)).strip("[] ") for x in ans.get("references_used", [])]
    out.update({
        "llm": LLM,
        "explanation_en": ans.get("explanation_en"), "explanation_fr": ans.get("explanation_fr"),
        "ambiguities": ans.get("ambiguities", []),
        "clarification_questions": ans.get("clarification_questions", []),
        "references_used": [c for c in cited if c in allowed],
        "rejected_references": [c for c in cited if c not in allowed],
        "seconds": round(time.time() - t0, 2),
    })
    if entry["id"] not in out["references_used"]:
        out["references_used"].insert(0, entry["id"])
    return out


def load_kb(kb_dir):
    kb = KB(Path(kb_dir) / "signals.json")
    kb.by_id = {s["id"]: s for s in kb.signals}
    return kb


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "index":
        build_index(a[1])
    elif a[0] == "search":
        n = int(a[a.index("-n") + 1]) if "-n" in a else 5
        for r in search(a[1], n):
            print(f"[{r['score']}] {r['kind']} — {r['reference']}\n    " + " ".join(r["text"].split())[:260])
    elif a[0] == "explain":
        print(json.dumps(explain(a[2], load_kb(a[1])), ensure_ascii=False, indent=1))
    elif a[0] == "batch":
        kb = load_kb(a[1])
        cases = [json.loads(l) for l in Path(a[2]).read_text("utf-8").splitlines() if l.strip()]
        if "--ids" in a:
            ids = set(Path(a[a.index("--ids") + 1]).read_text("utf-8").split())
            cases = [c for c in cases if c["id"] in ids]
        if "--limit" in a:
            cases = cases[: int(a[a.index("--limit") + 1])]
        with open(a[3], "w", encoding="utf-8") as f:
            for n, c in enumerate(cases, start=1):
                r = explain(c["spoken_text"], kb)
                r["case_id"], r["category"] = c["id"], c["category"]
                f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
                print(f"{n}/{len(cases)} {c['id']} {r['status']} {r.get('seconds')} s", flush=True)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
