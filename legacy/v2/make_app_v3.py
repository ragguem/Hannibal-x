"""Cree ~/hannibal/app_v3 a partir de app_v2 (copie) et y ajoute le panneau Doctrine + glossaire (service hx2). Ne modifie ni app ni app_v2."""
import os, shutil, re
H = os.environ.get("HANNIBAL_HOME", os.path.expanduser("~/hannibal")); src, dst = H + "/app_v2", H + "/app_v3"
if not os.path.exists(dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("audit", "public_password.txt", "*.bak*", "__pycache__"))
    os.makedirs(dst + "/audit", exist_ok=True)
p = dst + "/server.py"; s = open(p, encoding="utf-8").read()
if "HX2_URL" not in s:
    s = s.replace('PORT = int(os.environ.get("PORT", "8771"))', 'PORT = int(os.environ.get("PORT", "8773"))\nHX2_URL = os.environ.get("HX2_URL", "http://127.0.0.1:8774")')
    s = s.replace('PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "8781"))', 'PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "0"))')
    s = s.replace('"hannibal_server_v2"', '"hannibal_server_v3"')
    helper = '''
def hx2(path, body=None, timeout=120):
    """Appel du service documentaire v2 (glossaire, doctrine). Les publications classifiees ne sont jamais demandees d'ici."""
    import urllib.request
    try:
        req = urllib.request.Request(HX2_URL + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception as e: return {"error": "service documentaire indisponible : " + str(e)[:160]}

class Handler(http.server.BaseHTTPRequestHandler):'''
    assert s.count("\nclass Handler(http.server.BaseHTTPRequestHandler):") == 1
    s = s.replace("\nclass Handler(http.server.BaseHTTPRequestHandler):", helper, 1)
    g = '        if p == "/api/scenarios": return self._json(H.scenarios())'
    assert s.count(g) == 1
    s = s.replace(g, '''        if p == "/api/glossary":
            q = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q") or [""])[0]
            return self._json(hx2("/glossary?q=" + urllib.parse.quote(q), timeout=10))
        if p == "/api/hx2": return self._json(hx2("/health", timeout=5))
''' + g)
    a = '        if p == "/api/interpret":'
    assert s.count(a) == 1
    s = s.replace(a, '''        if p == "/api/doctrine":
            q = str(body.get("q", "")).strip()[:600]
            if not q: return self._json({"error": "question vide"})
            r = hx2("/ask", {"q": q, "lang": "en" if body.get("lang") == "en" else "fr", "classified": False}, timeout=180)
            try:
                cid = H.audit.new_id()
                H.audit.log(cid, "doctrine", "console", question=q, status=r.get("status"), reason=r.get("reason"), answer=r.get("answer"),
                            cited=[{"pub": x["pub"], "article": x["article"], "page": x["page"]} for x in r.get("sources", []) if x["n"] in r.get("cited", [])], seconds=r.get("seconds"))
            except Exception: pass
            return self._json(r)
''' + a)
    open(p, "w", encoding="utf-8").write(s)
p = dst + "/web/console.html"; h = open(p, encoding="utf-8").read()
if 'id="cdoc"' not in h:
    card = '''  <div class="card teal" id="cdoc"><p class="lbl teal">Doctrine · publications OTAN</p>
    <div class="cmd"><input id="dq" placeholder="Ex. : Qui exerce le commandement tactique si personne n'est désigné ?" autocomplete="off"><select id="dlang" style="margin-left:6px"><option value="fr">FR</option><option value="en">EN</option></select><button id="dgo" style="margin-left:6px">Demander</button></div>
    <div id="dans" style="margin-top:10px;font-size:13px;color:var(--mut)">Réponse rédigée à partir des publications chargées, avec la page citée. Sans source, le système refuse de répondre.</div>
    <div id="dsrc" style="margin-top:8px;font-size:12px"></div>
    <div class="cmd" style="margin-top:12px"><input id="gq" placeholder="Glossaire : terme anglais, français ou abréviation (ex. screen, OTC)" autocomplete="off"><button id="ggo" style="margin-left:6px">Définir</button></div>
    <div id="gans" style="margin-top:8px;font-size:12px"></div></div>
'''
    k = '  <div class="card"><p class="lbl">Ordre au clavier</p>'
    assert h.count(k) == 1
    h = h.replace(k, card + k); h = h.replace('<script src="/static/console.js"></script>', '<script src="/static/console.js"></script><script src="/static/doctrine.js"></script>')
    open(p, "w", encoding="utf-8").write(h)
open(dst + "/web/doctrine.js", "w", encoding="utf-8").write(r'''// Panneau Doctrine et glossaire (v3) : interroge le service documentaire local via /api/doctrine et /api/glossary.
(function(){
  const $=id=>document.getElementById(id), esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  if(!$("dgo"))return;
  async function ask(){
    const q=$("dq").value.trim(); if(!q)return;
    $("dgo").disabled=true; $("dans").style.color="var(--mut)"; $("dans").textContent="Recherche dans les publications…"; $("dsrc").innerHTML="";
    let r; try{ r=await (await fetch("/api/doctrine",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q,lang:$("dlang").value})})).json(); }catch(e){ r={error:String(e)}; }
    $("dgo").disabled=false;
    if(r.error){ $("dans").textContent="Erreur : "+r.error; return; }
    if(r.status!=="ok"){ $("dans").innerHTML="<b>Pas de réponse.</b> "+esc(r.answer||"")+(r.reason?" <span style='opacity:.7'>("+esc(r.reason)+")</span>":""); }
    else { $("dans").style.color=""; $("dans").innerHTML=esc(r.answer).replace(/\[(\d+)\]/g,"<sup style='color:#35c9b5'>[$1]</sup>").replace(/\n/g,"<br>"); }
    const src=(r.sources||[]).filter(s=>(r.cited||[]).includes(s.n));
    $("dsrc").innerHTML=src.map(s=>"<details style='margin:4px 0'><summary><b>["+s.n+"]</b> "+esc(s.pub)+(s.article?" · art. "+esc(s.article):"")+(s.page?" · p. "+esc(s.page):"")+(s.title?" — "+esc(s.title):"")+"</summary><div class='quote mono' style='white-space:pre-wrap;margin-top:4px'>"+esc(s.text)+"</div></details>").join("")
      +(r.seconds?"<div style='opacity:.6;margin-top:4px'>"+r.seconds+" s · modèle local "+esc(r.llm||"")+" · à vérifier sur la publication</div>":"");
  }
  async function gloss(){
    const q=$("gq").value.trim(); if(!q)return; $("gans").textContent="…";
    let r; try{ r=await (await fetch("/api/glossary?q="+encodeURIComponent(q))).json(); }catch(e){ r={error:String(e)}; }
    if(r.error){ $("gans").textContent="Erreur : "+r.error; return; }
    const E=r.entries||[]; if(!E.length){ $("gans").textContent="Terme absent du glossaire."; return; }
    $("gans").innerHTML=E.map(e=>"<div style='margin:6px 0'><b>"+esc(e.en)+"</b>"+(e.abbr?" ("+esc(e.abbr)+")":"")+" → "+(e.fr?"<b>"+esc(e.fr)+"</b>":"<i>pas d'équivalent français officiel</i>")+(e.sense?" · sens "+e.sense:"")+" <span style='opacity:.6'>· "+esc(e.source)+(e.page?" p. "+esc(e.page):"")+"</span>"+(e.def_fr||e.def_en?"<div style='opacity:.85'>"+esc(e.def_fr||e.def_en)+"</div>":"")+"</div>").join("");
  }
  $("dgo").onclick=ask; $("ggo").onclick=gloss;
  $("dq").addEventListener("keydown",e=>{e.stopPropagation(); if(e.key==="Enter")ask();}); $("gq").addEventListener("keydown",e=>{e.stopPropagation(); if(e.key==="Enter")gloss();});
  ["dq","gq"].forEach(i=>$(i).addEventListener("keyup",e=>e.stopPropagation()));
})();
''')
print("app_v3 prete")
