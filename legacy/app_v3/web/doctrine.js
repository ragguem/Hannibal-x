// Panneau Doctrine et glossaire (v3) : interroge le service documentaire local via /api/doctrine et /api/glossary.
(function(){
  const $=id=>document.getElementById(id), esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  if(!$("dgo"))return;
  async function ask(){
    const q=$("dq").value.trim(); if(!q)return;
    $("dgo").disabled=true; $("dans").style.color="var(--mut)"; $("dans").textContent="Recherche dans les publications"; $("dans").classList.add("wait"); $("dsrc").innerHTML="";
    let r; try{ r=await (await fetch("/api/doctrine",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q,lang:$("dlang").value,pubs:$("dpub")&&$("dpub").value?[$("dpub").value]:[]})})).json(); }catch(e){ r={error:String(e)}; }
    $("dgo").disabled=false; $("dans").classList.remove("wait");
    if(r.error){ $("dans").textContent="Erreur : "+r.error; return; }
    if(r.status!=="ok"){ $("dans").innerHTML="<b>Pas de réponse.</b> "+esc(r.answer||"")+(r.reason?" <span style='opacity:.7'>("+esc(r.reason)+")</span>":""); }
    else { $("dans").style.color="";
      // si toutes les phrases citent les memes sources, on ne l'ecrit qu'une fois a la fin
      let ans=r.answer; const groups=ans.match(/(\[\d+\])+/g)||[]; if(groups.length>1&&new Set(groups).size===1){ans=ans.replace(/\s*(\[\d+\])+/g,"").trim()+" "+groups[0];}
      $("dans").innerHTML=esc(ans).replace(/\[(\d+)\]/g,"<sup style='color:#35c9b5'>[$1]</sup>").replace(/\n/g,"<br>"); }
    const src=(r.sources||[]).filter(s=>(r.cited||[]).includes(s.n));
    // terme inconnu des publications : on propose, l'opérateur choisit (jamais de correction silencieuse)
    const sg=(r.suggestions||[]).map(p=>"« <b>"+esc(p.inconnu)+"</b> » ne figure dans aucune publication chargée. Vouliez-vous dire "+p.propositions.map(x=>"<a href='#' class='dsg' data-old='"+esc(p.inconnu)+"' data-new='"+esc(x.terme)+"' title='"+esc(x.fr||x.en||"")+"' style='color:#ffc24a;font-weight:700'>"+esc(x.terme)+"</a>"+(x.en?" <span style='opacity:.7'>("+esc(x.en)+")</span>":"")).join(", ")+" ?").join("<br>");
    const sgHtml=sg?"<div style='border:1px solid #7a5a1c;border-radius:6px;padding:6px 9px;margin:6px 0;color:#ffd98a'>"+sg+"</div>":"";
    $("dsrc").innerHTML=sgHtml+src.map(s=>"<details style='margin:4px 0'><summary><b>["+s.n+"]</b> "+esc(s.pub)+(s.article?" · art. "+esc(s.article):"")+(s.page?" · p. "+esc(s.page):"")+(s.title?" — "+esc(s.title):"")+"</summary><div class='quote mono' style='white-space:pre-wrap;margin-top:4px'>"+esc(s.text)+"</div></details>").join("")
      +(r.seconds?"<div style='opacity:.6;margin-top:4px'>"+r.seconds+" s · modèle local "+esc(r.llm||"")+" · à vérifier sur la publication</div>":"");
    $("dsrc").querySelectorAll("a.dsg").forEach(a=>a.onclick=e=>{e.preventDefault(); const o=a.dataset.old.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"); $("dq").value=$("dq").value.replace(new RegExp(o,"g"),a.dataset.new); ask();});
  }
  async function gloss(){
    const q=$("gq").value.trim(); if(!q)return; $("gans").textContent="…";
    let r; try{ r=await (await fetch("/api/glossary?q="+encodeURIComponent(q))).json(); }catch(e){ r={error:String(e)}; }
    if(r.error){ $("gans").textContent="Erreur : "+r.error; return; }
    const E=r.entries||[]; if(!E.length){ $("gans").textContent="Terme absent du glossaire."; return; }
    $("gans").innerHTML=E.map(e=>"<div style='margin:6px 0'><b>"+esc(e.en)+"</b>"+(e.abbr?" ("+esc(e.abbr)+")":"")+" → "+(e.fr?"<b>"+esc(e.fr)+"</b>":"<i>pas d'équivalent français officiel</i>")+(e.sense?" · sens "+e.sense:"")+" <span style='opacity:.6'>· "+esc(e.source)+(e.page?" p. "+esc(e.page):"")+"</span>"+(e.def_fr||e.def_en?"<div style='opacity:.85'>"+esc(e.def_fr||e.def_en)+"</div>":"")+"</div>").join("");
  }
  $("dgo").onclick=ask; $("ggo").onclick=gloss; if($("dclr"))$("dclr").onclick=()=>{$("dans").style.color="var(--mut)";$("dans").textContent="Réponse rédigée à partir des publications chargées, avec la page citée. Sans source, le système refuse de répondre.";$("dsrc").innerHTML="";$("dq").value="";};
  $("dq").addEventListener("keydown",e=>{e.stopPropagation(); if(e.key==="Enter")ask();}); $("gq").addEventListener("keydown",e=>{e.stopPropagation(); if(e.key==="Enter")gloss();});
  ["dq","gq"].forEach(i=>$(i).addEventListener("keyup",e=>e.stopPropagation()));
})();
