#!/usr/bin/env python3
"""HANNIBAL X v2 — service documentaire (ne modifie rien de la v1).

Ecoute sur 127.0.0.1:8774. Lit le schema v2 de la base (passages, glossary), calcule les embeddings et
redige les reponses avec les modeles locaux du conteneur hannibal-ollama. Aucun appel en ligne.

  GET  /health
  GET  /glossary?q=terme            terme anglais, francais ou abreviation -> definitions officielles
  POST /search {q, k, pubs, classified}          passages les plus proches, avec reference
  POST /ask    {q, lang, pubs, classified}       reponse courte, chaque phrase citee [n], ou refus

Garde-fous :
  - les publications classifiees (HX2_CLASSIFIED) sont exclues sauf si la requete porte classified=true ;
  - pas de passage assez proche -> refus sans appeler le modele ;
  - le modele ne voit que les passages retrouves et doit citer leurs numeros ; une reponse sans citation
    valide est remplacee par un refus ; le texte des sources est renvoye a cote pour verification.
"""
import json, os, re, time, urllib.parse, http.server, psycopg, requests

PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
OLLAMA = os.environ.get("HX_OLLAMA", "http://127.0.0.1:11435")
EMBED = os.environ.get("HX_EMBED", "bge-m3")
LLM = os.environ.get("HX_LLM", "gemma3:12b")
PORT = int(os.environ.get("HX2_PORT", "8774"))
CLASSIFIED = set(x for x in os.environ.get("HX2_CLASSIFIED", "ATP-28").split(",") if x)
MIN_SCORE = float(os.environ.get("HX2_MIN_SCORE", "0.45"))
RERANK = os.environ.get("HX2_RERANK", "http://127.0.0.1:8775")
QIDX = os.environ.get("HX2_QIDX", "0") == "1"     # utiliser aussi les questions generees par passage (table v2.pquestions)
THINK = {"think": False} if os.environ.get("HX2_THINK") == "0" else {}     # modeles a raisonnement (qwen3...) : le couper
NONE = {"fr": "Aucune des publications chargées ne répond à cette question.", "en": "None of the loaded publications answers this question."}

def embed(text):
    r = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED, "input": [text]}, timeout=120); r.raise_for_status()
    return "[" + ",".join(f"{x:.6f}" for x in r.json()["embeddings"][0]) + "]"

def search(q, k=8, pubs=None, classified=False):
    v = embed(q); where, args = ["kind <> 'toc'"], [v]
    if pubs: where.append("pub = ANY(%s)"); args.append(list(pubs))
    if not classified and CLASSIFIED: where.append("NOT (pub = ANY(%s))"); args.append(list(CLASSIFIED))
    sql = ("SELECT id, pub, edition, chapter, article, title, page, pdf_page, kind, text, 1 - (embedding <=> %s::vector) AS score FROM v2.passages WHERE "
           + " AND ".join(where) + " ORDER BY embedding <=> %s::vector LIMIT %s")
    with psycopg.connect(PG) as con:
        con.execute("SET hnsw.ef_search = 200")
        rows = con.execute(sql, args + [v, k]).fetchall()
    keys = ["id", "pub", "edition", "chapter", "article", "title", "page", "pdf_page", "kind", "text", "score"]
    out = [dict(zip(keys, r)) for r in rows]
    for o in out: o["score"] = round(float(o["score"]), 4); o["classified"] = o["pub"] in CLASSIFIED
    return out

STOP = set("the a an of to in on for and or is are be by with at from as that this which what who how when where does do did can may shall should must it its their there than then into during between within without not no if any all each per about over under after before while been being has have had will would could was were".split())

def expand(q):
    """Reformule la question en anglais doctrinal + mots-cles (le corpus est en anglais). En cas d'echec : rien."""
    try:
        r = requests.post(f"{OLLAMA}/api/chat", timeout=120, json={**THINK, "model": LLM, "stream": False, "format": "json", "options": {"temperature": 0, "num_ctx": 8192},
            "messages": [{"role": "system", "content": "You prepare search queries over NATO naval publications written in English (tactics, replenishment at sea, exercises, joint doctrine). "
                "Given a question in any language, return JSON {\"query\": one concise English reformulation using NATO naval vocabulary, \"keywords\": up to 8 English terms or short phrases likely to appear in the passage that answers it}. Do not answer the question."},
                {"role": "user", "content": q}]})
        d = json.loads(r.json()["message"]["content"]); kw = [str(k) for k in (d.get("keywords") or [])][:8]
        return str(d.get("query") or "").strip(), kw
    except Exception: return "", []

def _filters(pubs, classified):
    where, args = ["kind <> 'toc'"], []
    if pubs: where.append("pub = ANY(%s)"); args.append(list(pubs))
    if not classified and CLASSIFIED: where.append("NOT (pub = ANY(%s))"); args.append(list(CLASSIFIED))
    return " AND ".join(where), args

def search2(q, k=10, pubs=None, classified=False, n=40, qidx=None):
    """Recherche : vecteurs sur la question d'origine et sur sa reformulation en anglais ; on garde la meilleure similarite."""
    enq, kw = expand(q); w, wa = _filters(pubs, classified); lists = []; info = {"query_en": enq, "keywords": kw}
    with psycopg.connect(PG) as con:
        con.execute("SET hnsw.ef_search = 200"); cos = {}
        for text, weight in [(q, 1.0)] + ([(enq, 1.0)] if enq else []):
            v = embed(text)
            rows = con.execute(f"SELECT id, 1 - (embedding <=> %s::vector) FROM v2.passages WHERE {w} ORDER BY embedding <=> %s::vector LIMIT %s", [v] + wa + [v, n]).fetchall()
            lists.append((weight, [r[0] for r in rows]))
            for r in rows: cos[r[0]] = max(cos.get(r[0], 0), float(r[1]))
        # essais du 12/11 : la fusion avec les mots-cles degrade (top 5 : 73 %) ; le meilleur est le max des deux similarites (top 5 : 92 %, top 10 : 95 %)
        fused = dict(cos); pool = sorted(fused, key=lambda x: -fused[x])[:30]; top = pool[:k]; info["rerank"] = False
        if QIDX if qidx is None else qidx:
            # passages retrouves par ressemblance entre la question posee et les questions generees pour chaque passage
            qw, qa = ["TRUE"], []
            if pubs: qw.append("pub = ANY(%s)"); qa.append(list(pubs))
            if not classified and CLASSIFIED: qw.append("NOT (pub = ANY(%s))"); qa.append(list(CLASSIFIED))
            qs = {}
            for text in [q] + ([enq] if enq else []):
                v = embed(text)
                for pid, sim in con.execute(f"SELECT passage_id, 1 - (embedding <=> %s::vector) FROM v2.pquestions WHERE {' AND '.join(qw)} ORDER BY embedding <=> %s::vector LIMIT 60", [v] + qa + [v]).fetchall():
                    qs[pid] = max(qs.get(pid, 0), float(sim))
            byq = sorted(qs, key=lambda x: -qs[x])[:25]; info["qidx"] = len(byq)
            merged = []
            for a, b in zip(pool + [None] * 30, byq + [None] * 30):          # entrelace les deux listes
                for x in (a, b):
                    if x and x not in merged: merged.append(x)
            pool = merged[:45]; top = pool[:k]
            for pid in pool: fused.setdefault(pid, qs.get(pid, 0)); cos.setdefault(pid, 0.0)
        # mode demo : si le service de reclassement tourne (GPU libere), il relit les 30 meilleurs passages en entier et les reordonne
        try:
            tx = {r[0]: ((r[1] or "") + ". " + r[2]) for r in con.execute("SELECT id, title, text FROM v2.passages WHERE id = ANY(%s)", (pool,)).fetchall()}
            rr = requests.post(RERANK + "/rerank", json={"queries": [q, enq], "passages": [tx[i] for i in pool]}, timeout=6).json()["scores"]
            order = [i for _, i in sorted(zip(rr, pool), key=lambda x: -x[0])]; top = order[:k]; info["rerank"] = True
            for i, sc in zip(pool, rr): fused[i] = sc
        except Exception: pass
        if not top: return [], info
        rows = con.execute("SELECT id, pub, edition, chapter, article, title, page, pdf_page, kind, text FROM v2.passages WHERE id = ANY(%s)", (top,)).fetchall()
    keys = ["id", "pub", "edition", "chapter", "article", "title", "page", "pdf_page", "kind", "text"]; by = {r[0]: dict(zip(keys, r)) for r in rows}
    out = []
    for pid in top:
        o = by[pid]; o["score"] = round(cos.get(pid, 0.0), 4); o["fused"] = round(fused[pid], 5); o["classified"] = o["pub"] in CLASSIFIED; out.append(o)
    return out, info

def glossary(q):
    q = (q or "").strip().lower()
    if not q: return []
    with psycopg.connect(PG) as con:
        rows = con.execute("SELECT en, fr, sense, abbr, def_en, def_fr, source, page, statut FROM v2.glossary WHERE lower(en) = %s OR lower(fr) = %s OR lower(abbr) = %s ORDER BY source, sense NULLS FIRST LIMIT 20", (q, q, q)).fetchall()
        if not rows:
            rows = con.execute("SELECT en, fr, sense, abbr, def_en, def_fr, source, page, statut FROM v2.glossary WHERE lower(en) LIKE %s OR lower(fr) LIKE %s ORDER BY length(en), source LIMIT 12", (q + "%", q + "%")).fetchall()
    return [dict(zip(["en", "fr", "sense", "abbr", "def_en", "def_fr", "source", "page", "statut"], r)) for r in rows]

SYS = {"fr": "Tu es un assistant de doctrine navale OTAN. Réponds en français, en 2 à 5 phrases, UNIQUEMENT à partir des extraits numérotés fournis. "
             "Après chaque phrase, cite le ou les extraits utilisés sous la forme [1] ou [2][3]. N'ajoute aucune connaissance extérieure, aucun chiffre absent des extraits. "
             "Garde en anglais les termes techniques sans traduction officielle. Si les extraits ne répondent pas à la question, réponds exactement : AUCUNE_SOURCE",
       "en": "You are a NATO naval doctrine assistant. Answer in English, in 2 to 5 sentences, ONLY from the numbered extracts provided. "
             "After each sentence cite the extract(s) used as [1] or [2][3]. Add no outside knowledge and no figure absent from the extracts. "
             "If the extracts do not answer the question, reply exactly: AUCUNE_SOURCE"}

def _llm(lang, ctx, q, extra=""):
    r = requests.post(f"{OLLAMA}/api/chat", timeout=600, json={**THINK, "model": LLM, "stream": False, "options": {"temperature": 0, "num_ctx": 8192},
        "messages": [{"role": "system", "content": SYS[lang] + extra}, {"role": "user", "content": f"Extraits :\n\n{ctx}\n\nQuestion : {q}"}]})
    r.raise_for_status(); return (r.json().get("message", {}).get("content") or "").strip()

DEFAULT_K = int(os.environ.get("HX2_K", "10")); DEFAULT_STYLE = os.environ.get("HX2_STYLE", "verify")

def ask(q, lang="fr", pubs=None, classified=False, k=10, mode="hybrid", style="verify", qidx=None):
    t0 = time.time(); lang = "en" if lang == "en" else "fr"; info = {}
    if mode == "dense": hits = search(q, k, pubs, classified)
    else: hits, info = search2(q, k, pubs, classified, qidx=qidx)
    src = [{"n": i + 1, "id": h["id"], "pub": h["pub"], "edition": h["edition"], "chapter": h["chapter"], "article": h["article"], "title": h["title"], "page": h["page"],
            "pdf_page": h["pdf_page"], "score": h["score"], "classified": h["classified"], "text": h["text"]} for i, h in enumerate(hits)]
    base = {"question": q, "lang": lang, "sources": src, "llm": LLM, "mode": mode, "search": info}
    best = max([h["score"] for h in hits] or [0])
    if not hits or best < MIN_SCORE:
        return dict(base, status="refus", reason="aucun passage assez proche", answer=NONE[lang], cited=[], seconds=round(time.time() - t0, 1))
    ctx = "\n\n".join(f"[{s['n']}] {s['pub']}, art. {s['article'] or '-'}, p. {s['page'] or '-'} — {s['title'] or ''}\n{s['text'][:1800]}" for s in src)
    if style == "quotes": return ask_quotes(q, lang, src, ctx, base, t0)
    r1 = _answer(q, lang, src, ctx, base, t0, info, classified)
    if r1["status"] == "ok" or RETRY <= 0: return r1
    # second essai avant de refuser : contexte court (les meilleurs extraits seulement), memes controles
    sub = src[:RETRY]; ctx2 = "\n\n".join(f"[{s['n']}] {s['pub']}, art. {s['article'] or '-'}, p. {s['page'] or '-'} — {s['title'] or ''}\n{s['text'][:2600]}" for s in sub)
    r2 = _answer(q, lang, sub, ctx2, base, t0, info, classified)
    if r2["status"] == "ok": return dict(r2, second_try=True, first_reason=r1.get("reason"))
    return dict(r1, second_try=True)

RETRY = int(os.environ.get("HX2_RETRY", "0"))

def _answer(q, lang, src, ctx, base, t0, info, classified):
    ans = _llm(lang, ctx, q)
    def check(a):
        nums = [int(x) for x in re.findall(r"\[(\d+)\]", a)]
        return sorted({x for x in nums if 1 <= x <= len(src)}), [x for x in nums if not 1 <= x <= len(src)]
    cited, bad = check(ans)
    if "AUCUNE_SOURCE" not in ans and (not cited or bad):          # une relance : le modele a repondu sans citer correctement
        ans = _llm(lang, ctx, q, " IMPORTANT : chaque phrase doit se terminer par un numero d'extrait entre crochets, entre [1] et [%d]." % len(src)); cited, bad = check(ans)
    dodge = re.search(r"(does|do|did) not (specify|mention|state|provide|indicate)|not specified|no information|ne (précise|mentionne|spécifie|indique|fourni\w*) pas|n'est pas (précisé|mentionné|spécifié|indiqué)|aucune information", ans, re.I)
    if "AUCUNE_SOURCE" in ans or not cited or bad or dodge:
        reason = "le modèle ne trouve pas la réponse dans les extraits" if ("AUCUNE_SOURCE" in ans or dodge) else "réponse sans citation valide"
        return dict(base, status="refus", reason=reason, answer=NONE[lang], cited=[], seconds=round(time.time() - t0, 1))
    if GROUND:
        okg, why = grounded(q, ans, [x for x in src if x["n"] in cited], info.get("query_en", ""), classified)
        if not okg: return dict(base, status="refus", reason="contrôle : " + why, answer=NONE[lang], draft=ans, cited=[], seconds=round(time.time() - t0, 1))
    v = verify(q, ans, [x for x in src if x["n"] in cited])
    if not v["ok"]:
        return dict(base, status="refus", reason="vérification : " + v["why"], answer=NONE[lang], draft=ans, cited=[], seconds=round(time.time() - t0, 1))
    return dict(base, status="ok", answer=ans, cited=cited, verify=v, seconds=round(time.time() - t0, 1))

QSYS = {"fr": "Tu es un assistant de doctrine navale OTAN. On te donne des extraits numérotés (en anglais) et une question. Travaille en deux temps et rends du JSON : "
               "{\"quotes\": [{\"n\": numéro de l'extrait, \"text\": phrase ou ligne recopiée MOT POUR MOT de cet extrait, en anglais, qui répond à la question}], \"answer\": réponse en français, 1 à 4 phrases, fondée uniquement sur ces citations, chaque phrase suivie de [n]}. "
               "Une à trois citations. Si aucun extrait ne répond précisément à la question, rends {\"quotes\": [], \"answer\": \"AUCUNE_SOURCE\"}. N'ajoute aucune connaissance extérieure. Garde en anglais les termes techniques sans traduction officielle.",
        "en": "You are a NATO naval doctrine assistant. You receive numbered extracts and a question. Work in two steps and return JSON: "
               "{\"quotes\": [{\"n\": extract number, \"text\": sentence or line copied WORD FOR WORD from that extract which answers the question}], \"answer\": answer in English, 1 to 4 sentences, based only on those quotes, each sentence followed by [n]}. "
               "One to three quotes. If no extract answers the question precisely, return {\"quotes\": [], \"answer\": \"AUCUNE_SOURCE\"}. Add no outside knowledge."}
_norm = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

def ask_quotes(q, lang, src, ctx, base, t0):
    """Reponse appuyee sur des citations mot pour mot : le programme verifie que chaque citation figure bien dans l'extrait indique."""
    def refus(reason, draft=None): return dict(base, style="quotes", status="refus", reason=reason, answer=NONE[lang], draft=draft, cited=[], seconds=round(time.time() - t0, 1))
    try:
        r = requests.post(f"{OLLAMA}/api/chat", timeout=600, json={**THINK, "model": LLM, "stream": False, "format": "json", "options": {"temperature": 0, "num_ctx": 8192},
            "messages": [{"role": "system", "content": QSYS[lang]}, {"role": "user", "content": f"Extraits :\n\n{ctx}\n\nQuestion : {q}"}]})
        d = json.loads(r.json()["message"]["content"])
    except Exception: return refus("réponse du modèle illisible")
    ans = str(d.get("answer") or "").strip(); good = []
    for c in (d.get("quotes") or [])[:4]:
        try: n = int(c.get("n")); t = _norm(str(c.get("text") or ""))
        except Exception: continue
        if not (1 <= n <= len(src)) or len(t.split()) < 4: continue
        body = _norm(src[n - 1]["text"]); w = t.split()
        # citation acceptee si elle se retrouve dans l'extrait (au moins une suite de 6 mots identiques, ou toute la citation si elle est plus courte)
        if t in body or any(" ".join(w[i:i + 6]) in body for i in range(0, max(1, len(w) - 5))): good.append({"n": n, "text": str(c.get("text"))[:400]})
    if "AUCUNE_SOURCE" in ans or not ans: return refus("le modèle ne trouve pas la réponse dans les extraits")
    if not good: return refus("aucune citation exacte à l'appui", ans)
    nums = sorted({g["n"] for g in good}); cited = sorted({int(x) for x in re.findall(r"\[(\d+)\]", ans) if 1 <= int(x) <= len(src)})
    if not cited or not set(cited) <= set(nums): cited = nums; ans = re.sub(r"\s*\[\d+\]", "", ans).strip() + " " + "".join(f"[{n}]" for n in nums)
    if re.search(r"(does|do|did) not (specify|mention|state|provide|indicate)|not specified|ne (précise|mentionne|spécifie|indique) pas|aucune information", ans, re.I): return refus("le modèle ne trouve pas la réponse dans les extraits", ans)
    return dict(base, style="quotes", status="ok", answer=ans, cited=cited, quotes=good, seconds=round(time.time() - t0, 1))

GROUND = os.environ.get("HX2_GROUND", "1") == "1"
_FRSTOP = set("le la les un une des du de au aux en et ou qui que quoi quel quelle quels quelles comment combien pourquoi quand dans sur sous par pour avec sans est sont selon lors pendant entre vers chez ce cet cette ces son sa ses leur leurs si ne pas plus the a an of to in on for and or who what which how when where why is are does do can may should must by with at from as that this during between under after before it its".split())

_NUMW = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
         "fifteen": "15", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "hundred": "100", "thousand": "1000", "half": "0.5", "twice": "2", "double": "2", "single": "1", "both": "2", "first": "1", "second": "2", "third": "3"}
_CORPUS = {}

def in_corpus(term, classified=False):
    """Le terme apparait-il quelque part dans les publications chargees (non classifiees sauf demande) ? Resultat garde en memoire."""
    k = (term.lower(), classified)
    if k not in _CORPUS:
        with psycopg.connect(PG) as con:
            # tolere les variantes d'ecriture : SM-2, SM 2, SM2, tiret insecable...
            pat = "[^a-z0-9]{0,2}".join(re.escape(c) for c in re.sub(r"[^a-z0-9]", "", term.lower()))
            sql = "SELECT 1 FROM v2.passages WHERE text ~* %s" + ("" if classified or not CLASSIFIED else " AND NOT (pub = ANY(%s))") + " LIMIT 1"
            args = [pat] + ([] if classified or not CLASSIFIED else [list(CLASSIFIED)])
            _CORPUS[k] = con.execute(sql, args).fetchone() is not None
    return _CORPUS[k]

def key_terms(text):
    """Noms propres, sigles et codes d'un texte anglais (la reformulation de la question)."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/]*", text); keys = []
    for i, w in enumerate(words):
        if len(w) < 3 or w.lower() in _FRSTOP: continue
        code = any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
        sigle = w.isupper() and w.isalpha()
        propre = i > 0 and w[0].isupper() and w[1:].islower() and len(w) >= 4
        if code or sigle or propre: keys.append(w)
    return keys

def grounded(q, ans, cited_src, enq="", classified=False):
    """Controle par programme, sans modele. -> (ok, raison)
    (1) chaque nombre de la reponse figure dans les extraits cites (en chiffres ou en lettres) ;
    (2) un nom propre, sigle ou code de la question qui n'existe NULLE PART dans les publications chargees => les documents ne peuvent pas repondre."""
    body = " ".join(x["text"] + " " + (x.get("title") or "") for x in cited_src)
    low = body.lower(); flat = re.sub(r"[\s\u00a0\u202f,]", "", low)
    present = set(re.findall(r"\d+(?:\.\d+)?", low.replace(",", ""))) | {v for w, v in _NUMW.items() if re.search(r"\b" + w + r"\b", low)}
    present |= set(re.findall(r"\d+(?:\.\d+)?", (q + " " + (enq or "")).replace(",", ".")))          # nombres donnes dans la question elle-meme
    for a_, b_ in re.findall(r"\b(twenty|thirty|forty|fifty|sixty)[- ](one|two|three|four|five|six|seven|eight|nine)\b", low): present.add(str(int(_NUMW[a_]) + int(_NUMW[b_])))
    txt = re.sub(r"\[[\d,\s]+\]", " ", ans)
    for n in re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"(?<=\d)[\s\u00a0\u202f](?=\d{3}\b)", "", txt)):
        v = n.replace(",", ".")
        if len(v) == 1: continue          # chiffre isole (enumeration, « 2 conditions ») : non controle
        if v in present or n in low or v in low or v.replace(".", "") in flat or n.replace(",", "") in present or (v.endswith(".0") and v[:-2] in present): continue
        return False, "un chiffre de la réponse (%s) ne figure pas dans les extraits cités" % n
    ql = q.lower()
    for k in key_terms(enq or ""):
        if k.lower() not in ql: continue          # seulement les termes ecrits par l'utilisateur, pas ceux ajoutes par la reformulation
        if k.lower() in low or k.lower().rstrip("s") in low or re.sub(r"[^a-z0-9]", "", k.lower()) in re.sub(r"[^a-z0-9]", "", low): continue
        if not in_corpus(k, classified) and not in_corpus(k.rstrip("s"), classified):
            return False, "« %s » n'apparaît dans aucune publication chargée" % k
    return True, ""

def verify(q, ans, cited_src):
    """Second passage, independant : la reponse repond-elle a la question, et les extraits cites l'appuient-ils ? En cas de panne du controle : on laisse passer en le signalant."""
    try:
        ctx = "\n\n".join(f"[{x['n']}] {x['text'][:1800]}" for x in cited_src)
        r = requests.post(f"{OLLAMA}/api/chat", timeout=300, json={**THINK, "model": LLM, "stream": False, "format": "json", "options": {"temperature": 0, "num_ctx": 8192},
            "messages": [{"role": "system", "content": "You are a strict fact-checker. You receive a QUESTION, a proposed ANSWER and the EXTRACTS it cites. Return JSON "
                "{\"answers_question\": true/false, \"supported\": true/false, \"why\": short reason}. answers_question is true only if the ANSWER gives the specific information the QUESTION asks for "
                "(false if it says the information is not specified, or talks about something else). supported is true only if every factual statement of the ANSWER is explicitly stated in the EXTRACTS."},
                {"role": "user", "content": f"QUESTION: {q}\n\nANSWER: {ans}\n\nEXTRACTS:\n{ctx}"}]})
        d = json.loads(r.json()["message"]["content"]); a, b = bool(d.get("answers_question")), bool(d.get("supported"))
        return {"ok": a and b, "answers_question": a, "supported": b, "why": ("la réponse ne traite pas la question" if not a else "la réponse n'est pas appuyée par les extraits cités") if not (a and b) else ""}
    except Exception as e: return {"ok": True, "answers_question": None, "supported": None, "why": "contrôle indisponible"}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, o, code=200):
        b = json.dumps(o, ensure_ascii=False).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/health":
                with psycopg.connect(PG) as con:
                    n = con.execute("SELECT count(*) FROM v2.passages").fetchone()[0]; g = con.execute("SELECT count(*) FROM v2.glossary").fetchone()[0]
                try: rk = requests.get(RERANK + "/", timeout=1).json().get("ok", False)
                except Exception: rk = False
                return self._json({"ok": True, "rerank": rk, "passages": n, "glossary": g, "llm": LLM, "embed": EMBED, "classified_excluded_by_default": sorted(CLASSIFIED)})
            if u.path == "/glossary": return self._json({"q": (q.get("q") or [""])[0], "entries": glossary((q.get("q") or [""])[0])})
        except Exception as e: return self._json({"error": str(e)[:300]}, 500)
        self._json({"error": "inconnu"}, 404)
    def do_POST(self):
        try: b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}")
        except Exception: b = {}
        try:
            if self.path == "/search":
                if b.get("mode") == "dense": return self._json({"hits": search(b.get("q", ""), int(b.get("k", 10)), b.get("pubs"), bool(b.get("classified")))})
                hits, info = search2(b.get("q", ""), int(b.get("k", 10)), b.get("pubs"), bool(b.get("classified")), qidx=b.get("qidx")); return self._json({"hits": hits, "search": info})
            if self.path == "/ask": return self._json(ask(b.get("q", ""), b.get("lang", "fr"), b.get("pubs"), bool(b.get("classified")), k=int(b.get("k", DEFAULT_K)), mode=b.get("mode", "hybrid"), style=b.get("style", DEFAULT_STYLE), qidx=b.get("qidx")))
        except Exception as e: return self._json({"error": str(e)[:300]}, 500)
        self._json({"error": "inconnu"}, 404)

if __name__ == "__main__":
    print(f"hx2 sur 127.0.0.1:{PORT}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
