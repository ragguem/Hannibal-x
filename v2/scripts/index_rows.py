"""Index des tableaux ligne par ligne (table v2.prows).
Chaque ligne d'un tableau devient un petit texte autonome : [publication | chapitre | section | article — titre] En-tete1 : valeur | En-tete2 : valeur ...
La recherche se fait sur la ligne ; le passage parent (le tableau) est donne au modele. Usage : index_rows.py [--dry]"""
import os, re, sys, json, requests, psycopg
PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal"); OLLAMA = os.environ.get("HX_OLLAMA", "http://127.0.0.1:11435"); EMBED = os.environ.get("HX_EMBED", "bge-m3")
DRY = "--dry" in sys.argv
def cells(l): return [c.strip() for c in l.split(" | ")]
def is_row(l): return l.count(" | ") >= 1 and len(l) > 8
def looks_header(c): 
    t = " ".join(c); letters = [ch for ch in t if ch.isalpha()]
    return bool(letters) and len(t) < 160 and sum(ch.isupper() for ch in letters) / len(letters) > 0.7 and not re.match(r"^\d", c[0])
def base(i): return i.rsplit(":", 1)[0] if ":" in i else i
with psycopg.connect(PG) as con:
    rows = con.execute("SELECT id, pub, chapter, section, article, title, text FROM v2.passages WHERE kind <> 'toc' ORDER BY id").fetchall()
    heads = {}; out = []; ntab = 0
    for pid, pub, chap, sec, art, title, text in rows:
        lines = [l for l in text.split("\n") if l.strip()]; tl = [l for l in lines if is_row(l)]
        if len(tl) < 3: continue
        ntab += 1; first = cells(tl[0]); n = len(first)
        if looks_header(first): head = first; heads[(base(pid), n)] = head; body = tl[1:]
        else: head = heads.get((base(pid), n)); body = tl
        crumb = " | ".join(x for x in [pub, ("Chap. " + chap) if chap else "", sec or "", (("art. " + art) if art else "") + ((" — " + title) if title else "")] if x)
        for l in body:
            c = cells(l)
            if sum(len(x) for x in c) < 12: continue
            if head and len(head) == len(c): body_txt = " | ".join(f"{h} : {v}" for h, v in zip(head, c) if v)
            else: body_txt = " | ".join(v for v in c if v)
            out.append((pid, pub, f"[{crumb}] {body_txt}"[:1200]))
    print(json.dumps({"passages_tableaux": ntab, "lignes": len(out), "avec_entete": sum(1 for o in out if " : " in o[2].split("] ", 1)[-1][:80])}))
    if DRY: sys.exit(0)
    con.execute("CREATE TABLE IF NOT EXISTS v2.prows (id bigserial PRIMARY KEY, passage_id text NOT NULL, pub text NOT NULL, row_text text NOT NULL, embedding vector(1024))")
    con.execute("TRUNCATE v2.prows"); done = 0
    for i in range(0, len(out), 32):
        b = out[i:i + 32]; r = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED, "input": [x[2] for x in b]}, timeout=600); r.raise_for_status()
        for (pid, pub, t), e in zip(b, r.json()["embeddings"]):
            con.execute("INSERT INTO v2.prows (passage_id, pub, row_text, embedding) VALUES (%s, %s, %s, %s::vector)", (pid, pub, t, "[" + ",".join(f"{x:.6f}" for x in e) + "]"))
        done += len(b); con.commit()
        if done % 640 == 0: print(done, flush=True)
    con.execute("CREATE INDEX IF NOT EXISTS prows_hnsw ON v2.prows USING hnsw (embedding vector_cosine_ops)"); con.commit(); print("FIN", done)
