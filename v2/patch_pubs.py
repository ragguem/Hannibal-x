"""app_v3 : choix de la publication dans le panneau Doctrine (ameliore nettement la precision)."""
import os
d = os.path.expanduser("~/hannibal/app_v3")
p = d + "/server.py"; s = open(p, encoding="utf-8").read()
if "DOC_PUBS" not in s:
    s = s.replace('HX2_URL = os.environ.get("HX2_URL", "http://127.0.0.1:8774")', 'HX2_URL = os.environ.get("HX2_URL", "http://127.0.0.1:8774")\nDOC_PUBS = {"MTP-01-VOL1", "ATP-16", "ATP-16.1", "MXP-02", "AJP-3", "AJP-3.1", "AJP-3.3", "AJP-3.3.3", "AJP-3.20", "AJP-6"}   # jamais de publication classifiee')
    old = 'r = hx2("/ask", {"q": q, "lang": "en" if body.get("lang") == "en" else "fr", "classified": False}, timeout=180)'
    assert s.count(old) == 1
    s = s.replace(old, 'pubs = [x for x in (body.get("pubs") or []) if x in DOC_PUBS]\n            r = hx2("/ask", {"q": q, "lang": "en" if body.get("lang") == "en" else "fr", "classified": False, "pubs": pubs or None}, timeout=180)')
    s = s.replace('H.audit.log(cid, "doctrine", "console", question=q,', 'H.audit.log(cid, "doctrine", "console", question=q, pubs=pubs,')
    open(p, "w", encoding="utf-8").write(s)
p = d + "/web/console.html"; h = open(p, encoding="utf-8").read()
if 'id="dpub"' not in h:
    old = '<select id="dlang" style="margin-left:6px">'
    assert h.count(old) == 1
    h = h.replace(old, '<select id="dpub" style="margin-left:6px" title="Limiter la recherche à une publication : nettement plus précis"><option value="">Toutes les publications</option><option value="MTP-01-VOL1">MTP-01 Vol. I — tactique</option><option value="ATP-16">ATP-16 — ravitaillement à la mer</option><option value="ATP-16.1">ATP-16.1 — ravitaillement, par nation</option><option value="MXP-02">MXP-02 — exercices</option><option value="AJP-3.1">AJP-3.1 — opérations maritimes</option><option value="AJP-3.3.3">AJP-3.3.3 — coordination air-mer</option><option value="AJP-3">AJP-3 — conduite des opérations</option><option value="AJP-6">AJP-6 — transmissions</option><option value="AJP-3.3">AJP-3.3 — air et espace</option><option value="AJP-3.20">AJP-3.20 — cyber</option></select>' + old)
    open(p, "w", encoding="utf-8").write(h)
p = d + "/web/doctrine.js"; j = open(p, encoding="utf-8").read()
if "dpub" not in j:
    old = 'body:JSON.stringify({q,lang:$("dlang").value})'
    assert j.count(old) == 1
    j = j.replace(old, 'body:JSON.stringify({q,lang:$("dlang").value,pubs:$("dpub")&&$("dpub").value?[$("dpub").value]:[]})'); open(p, "w", encoding="utf-8").write(j)
print("ok")
