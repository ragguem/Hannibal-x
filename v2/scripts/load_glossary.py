"""Charge glossary/glossary_v2.json dans v2.glossary (remplace tout). Usage : v2run.sh load_glossary.py [fichier.json]"""
import json, os, sys, psycopg
PG = os.environ.get("HX_PG", "postgresql://postgres:hannibal@127.0.0.1:5433/hannibal")
L = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "glossary/glossary_v2.json", encoding="utf-8"))
with psycopg.connect(PG) as con:
    con.execute("ALTER TABLE v2.glossary ADD COLUMN IF NOT EXISTS statut text")
    con.execute("ALTER TABLE v2.glossary ADD COLUMN IF NOT EXISTS abbr text")
    con.execute("ALTER TABLE v2.glossary ALTER COLUMN fr DROP NOT NULL")
    con.execute("TRUNCATE v2.glossary")
    with con.cursor() as cur:
        cur.executemany("INSERT INTO v2.glossary (en, fr, sense, extra, def_en, def_fr, source, page, statut, abbr) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(e.get("en"), e.get("fr") or None, int(e["sens"]) if str(e.get("sens") or "").isdigit() else None, "; ".join(x for x in [", ".join(e.get("synonymes_en") or []) if isinstance(e.get("synonymes_en"), list) else (e.get("synonymes_en") or ""), ", ".join(e.get("synonymes_fr") or []) if isinstance(e.get("synonymes_fr"), list) else (e.get("synonymes_fr") or "")] if x) or None,
              e.get("def_en") or None, e.get("def_fr") or None, e.get("source"), str(e["page"]) if e.get("page") not in (None, "") else None, e.get("statut"), e.get("abbr") or None) for e in L])
    for r in con.execute("SELECT source, statut, count(*) FROM v2.glossary GROUP BY 1,2 ORDER BY 1,2"): print(*r)
    print("total", con.execute("SELECT count(*) FROM v2.glossary").fetchone()[0])
