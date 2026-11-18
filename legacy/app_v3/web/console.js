"use strict";
(()=>{const d=Object.getOwnPropertyDescriptor(Element.prototype,"innerHTML");Object.defineProperty(Element.prototype,"innerHTML",{get:d.get,set(v){if(this.__h!==v){this.__h=v;d.set.call(this,v)}},configurable:true})})();
const $=id=>document.getElementById(id), NM=1852;
const fnm=v=>(v==null?"—":v.toFixed(1).replace(".",","));
const p2=n=>String(Math.floor(n)).padStart(2,"0"), mmss=t=>p2(t/60)+":"+p2(t%60);
const esc=s=>String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const seenC=new Set();function selC(id){sel=id}
let S=null, view=null, sel=null, range=4, ghosts=null, recs=[], ri=0, recSig="", trails={}, lastRec=0, sid=null;
const COLS={hannibal:"#4aa3ff",alfa:"#4aa3ff",charlie:"#4aa3ff",delta:"#4aa3ff"}, CLS={inconnu:"#f5b73b",ami:"#4aa3ff",neutre:"#2dd4bf",hostile:"#ff5d5d"};
const GCOL=["#f5b73b","#3ddc84","#ff7ad9","#7ad7ff"];

// flux direct : SSE, et repli automatique sur des requêtes répétées si le flux ne passe pas (certains tunnels le bloquent)
function liveFeed(on, down) {
  let last = 0, poll = false; const es = new EventSource("/events");
  es.onmessage = m => { last = Date.now(); let d; try { d = JSON.parse(m.data); } catch (_) { return; } on(d); };
  es.onerror = () => { if (!poll && down) down(); };
  async function loop() { for (;;) { try { const r = await fetch("/api/state", { cache: "no-store" }); on(await r.json()); } catch (_) { if (down) down(); } await new Promise(r => setTimeout(r, 300)); } }
  setTimeout(function chk() { if (Date.now() - last > 3000) { poll = true; es.close(); loop(); } else setTimeout(chk, 2000); }, 3000);
}
function es(){liveFeed(d=>{S=d;render()})}
function render(){
 if(!S||S.phase!=="running"&&S.phase!=="starting"){if(S&&S.phase==="idle"){location.href="/"}return}
 if(!S.ships)return;
 if(!view)view=S.player;
 $("hsc").textContent="Scénario : "+S.titre;$("hclk").textContent=mmss(S.t)+" / "+mmss(S.duree);
 S.ships.forEach(s=>{const a=trails[s.name]=trails[s.name]||[];const l=a[a.length-1];if(!l||Math.hypot(l[0]-s.x,l[1]-s.y)>25)a.push([s.x,s.y]);if(a.length>160)a.shift()});
 S.contacts.forEach(c=>{if(!seenC.has(c.id)){seenC.add(c.id);if(c.cls==="inconnu")sel=c.id}});          // une nouvelle piste non classée prend la main
 if(!sel||!S.contacts.find(c=>c.id===sel))sel=S.contacts.length?S.contacts[S.contacts.length-1].id:null;
 renderObj();$("bauto").textContent=S.auto?"Capitaines : autonomes":"Capitaines : aux ordres";$("bauto").style.borderColor=S.auto?"var(--green)":"";renderContact();renderShips();renderMsgs();renderBar();renderPlan();renderDebrief();
 $("halert").style.display=!S.ended&&S.contacts.some(c=>c.cls==="inconnu")?"":"none";
 if(S.ended){$("rec").textContent="—";$("recwhy").textContent="Scénario terminé."}else if(Date.now()-lastRec>10000){lastRec=Date.now();loadRec(false)}
 draw()}
function renderObj(){$("obj").innerHTML=(S.attendu||[]).map(a=>{const late=!a.ok&&S.t>a.avant_t+90,soon=!a.ok&&!late&&S.t>a.avant_t-30;return `<div style="display:flex;gap:8px;padding:4px 0;border-top:1px solid var(--line)"><span style="color:${a.ok?"var(--green)":late?"var(--red)":soon?"var(--amber)":"var(--mut)"}">${a.ok?"✓":late?"✗":"○"}</span><div>${esc(a.texte)}<br><small style="color:var(--mut)">avant ${mmss(a.avant_t)}${a.ok?"":" (tolérance 1 min 30)"}</small></div></div>`}).join("")}
function renderContact(){const c=S.contacts.find(x=>x.id===sel),b=$("cbody");
 if(!c){b.innerHTML="Aucun contact détecté pour l'instant.";b.style.color="var(--mut)";return}
 b.style.color="";const mode=c.tcpa_min!=null&&c.tcpa_min>0?"dans ~"+Math.round(c.tcpa_min)+" min":"maintenant";
 b.innerHTML=(S.contacts.length>1?`<div class="dest" style="margin-bottom:8px">${S.contacts.map(x=>`<button class="btn${x.id===sel?" on":""}" onclick="selC('${esc(x.id)}')">${esc(x.id)} · ${esc(x.cls)}</button>`).join("")}</div>`:"")+`<div class="mono" style="color:var(--mut);font-size:12px">${esc(c.id)}</div><div class="big">${esc(c.type)} · ${esc(c.cls)}</div>
 <dl><dt>Relèvement</dt><dd class="mono">${p2(Math.round(c.brg)%360).padStart(3,"0")}°</dd><dt>Distance</dt><dd class="mono">${fnm(c.range_nm)} NM</dd>
 <dt>Cap / vitesse</dt><dd class="mono">${String(c.cap).padStart(3,"0")}° · ${c.vit} kn</dd><dt>CPA estimé</dt><dd class="mono">${fnm(c.cpa_nm)} NM ${mode}</dd></dl>
 <p class="lbl" style="margin:12px 0 0">Classer le contact</p><div class="cls">
 ${[["ami","a","Ami"],["neutre","n","Neutre"],["hostile","h","Hostile"],["inconnu","i","Inconnu"]].map(k=>`<button class="btn ${k[1]} ${c.cls===k[0]?"on":""}" data-c="${k[0]}">${k[2]}</button>`).join("")}</div>`;
 b.querySelectorAll("[data-c]").forEach(x=>x.onclick=()=>post("/api/classify",{id:c.id,cls:x.dataset.c}))}
function renderShips(){$("tships").innerHTML=S.ships.map(s=>`<tr class="row" data-n="${s.name}"><td><span class="sdot" style="background:${s.name===S.player?"#3ddc84":"#4aa3ff"}"></span>${s.name.toUpperCase()}${s.name===S.guide?" ★":""}</td><td class="mono">${String(Math.round(s.hdg)%360).padStart(3,"0")}°</td><td class="mono">${Math.round(s.sog/0.514444)} kn</td><td>${s.etat}</td></tr>`).join("");
 $("tships").querySelectorAll("tr").forEach(r=>r.onclick=()=>{view=r.dataset.n})}
function renderMsgs(){const ms=S.msgs||[];
 $("log").innerHTML=ms.slice().reverse().slice(0,12).map(m=>`<div class="${m.kind}"><span class="t mono">${mmss(m.t)}</span> <b>${esc(m.from)}</b> → ${esc(m.to)} · ${esc(m.fr||m.en)}</div>`).join("");
 const rx=ms.filter(m=>["ordre","urgence","rapport"].includes(m.kind)).slice(-1)[0];
 if(rx){const w=$("rx");w.style.color="";w.innerHTML=`<div style="color:var(--mut);font-size:11.5px;margin-bottom:5px">${mmss(rx.t)} · ${esc(rx.from)} → ${esc(rx.to)} · VHF</div>« ${esc(rx.en)} »`;
  $("tr").style.color="";$("tr").textContent=rx.fr;
  const u=rx.kind==="urgence";$("trkv").innerHTML=`<span>Niveau</span><span>${u?"Alerte, non classifié":rx.kind==="rapport"?"Compte rendu d'une escorte":rx.pending?"Ordre à exécuter":"Ordre routine"}</span><span>Source</span><span>Règles MTP 1(D), sans IA</span><span>Statut</span><span>${rx.pending?"En attente de ton exécution":"Pris en compte"}</span>`}}
function renderBar(){const el=$("bar");
 el.innerHTML=S.ships.map(s=>`<button class="pill ${s.name===view?"on":""} ${s.name===S.player?"me":""}" data-n="${s.name}"><b>${s.name.toUpperCase()}${s.name===S.guide?" ★":""}</b><small class="mono">${String(Math.round(s.hdg)%360).padStart(3,"0")}° · ${Math.round(s.sog/0.514444)} kn · ${s.name===S.player?"Vous":s.role==="guide"?"Guide":"Escorte"}</small></button>`).join("")
  +`<div class="prog"><i style="width:${Math.min(100,100*S.t/S.duree)}%"></i></div><button class="btn sm" id="bstop">Arrêter</button>`;
 el.querySelectorAll(".pill").forEach(b=>b.onclick=()=>{view=b.dataset.n});$("bstop").onclick=async()=>{await post("/api/stop",{});location.href="/"}}
function renderPlan(){const c=$("cplan"),isG=S.player===S.guide;let h="";
 if(isG&&S.plan.length){$("cplant").textContent="Ordres prévus par le scénario (à donner)";h=S.plan.map(p=>`<div style="padding:4px 0;border-top:1px solid var(--line)"><span class="mono" style="color:var(--mut)">${mmss(p.t)}</span> ${esc(p.fr)}<br><span class="mono" style="color:var(--mut);font-size:12px">${esc(p.en)}</span></div>`).join("")}
 else if(!isG&&S.pending.length){$("cplant").textContent="Ordres reçus à exécuter";h=S.pending.map(p=>`<div style="padding:4px 0;border-top:1px solid var(--line);color:var(--amber)">${esc(p.fr)}</div>`).join("")}
 c.style.display=h?"":"none";$("plan").innerHTML=h}
function renderDebrief(){if(!S.ended||!S.debrief)return;const d=S.debrief;$("deb").classList.add("on");$("dt").textContent=`Objectifs atteints : ${d.score} / ${d.total}`;
 $("db").innerHTML=d.checks.map(c=>`<div class="chk"><span class="${c.ok?"ok":"ko"}">${c.ok?"✓":"✗"}</span><div>${esc(c.texte)}<br><small style="color:var(--mut)">avant ${mmss(c.avant_t)}${c.t!=null?" · fait à "+mmss(c.t):""}</small></div></div>`).join("")
 +`<div class="chk"><span>•</span><div>Distance minimale entre navires : <b>${d.min_ship_m==null?"—":d.min_ship_m+" m"}</b></div></div>`
 +Object.entries(d.min_cpa).map(([k,v])=>`<div class="chk"><span>•</span><div>Plus courte distance à ${esc(k)} : <b>${fnm(v)} NM</b></div></div>`).join("")
 +Object.entries(d.classes).map(([k,v])=>`<div class="chk"><span class="${v.choisie===v.reelle?"ok":"ko"}">${v.choisie===v.reelle?"✓":"✗"}</span><div>${esc(k)} classé « ${v.choisie} » (réel : ${v.reelle})</div></div>`).join("")}
$("dhome").onclick=async()=>{await post("/api/stop",{});location.href="/"};
$("dre").onclick=async()=>{const sc=S.titre;const list=await (await fetch("/api/scenarios")).json();const s=list.find(x=>x.titre===sc);const me=S.player;await post("/api/stop",{});await post("/api/start",{scenario:s.id,player:me,unity:false});location.href="/"};
// ---------- actions
async function post(u,b){return (await fetch(u,{method:"POST",body:JSON.stringify(b)})).json()}
function fb(html,cls){const f=$("fb");f.className="fb "+(cls||"");f.innerHTML=html}
async function doExec(text,direct){if(!text.trim())return fb("Tape un ordre, par exemple TURN STBD 9.","err");
 if(!direct){const r=await post("/api/interpret",{text,target:dest});if(!r.ok)return fb(esc(r.error),"err");showCmd(r.cmd);$("cmd").value="";fb("Message interprété : à approuver dans le cadre « Ordre à la voix ».","ok");return}
 const r=await post("/api/order",{text});
 if(r.ok){fb("✓ Envoyé : "+esc(r.fr)+`<small class="mono">${esc(r.en)}</small>`,"ok");ghosts=null;$("bghost").style.display="none";$("cmd").value="";lastRec=0}
 else fb(esc(r.error)+(r.hint?`<small>${esc(r.hint)}</small>`:""),"err")}
async function doSim(text){if(!text.trim())return fb("Tape un ordre à simuler.","err");const r=await post("/api/simulate",{text});
 if(!r.ok)return fb(esc(r.error)+(r.hint?`<small>${esc(r.hint)}</small>`:""),"err");
 ghosts={paths:r.paths,until:Date.now()+60000};$("bghost").style.display="";
 const mine=r.cpa.filter(c=>c.ship.toLowerCase()===S.player);const w=mine.map(c=>`CPA ${esc(c.contact)} : ${fnm(c.cpa_nm)} NM (sans ordre : ${fnm(c.cpa_nm_sans_ordre)})${c.risque?" ⚠":""}`).join("<br>");
 const col=r.ships_min.filter(x=>x.risque).map(x=>`⚠ ${x.a.toUpperCase()}/${x.b.toUpperCase()} à ${x.dist_m} m`).join("<br>");
 fb("Simulation : "+esc(r.fr)+(w?"<br>"+w:"")+(col?"<br>"+col:"")+"<small>Trajectoires fantômes affichées 60 s sur le radar.</small>",mine.some(c=>c.risque)||col?"err":"ok")}
async function loadRec(show){const r=await post("/api/recommend",{});recs=r.items||[];const sig=recs.map(x=>x.text).join("|");if(sig!==recSig){recSig=sig;ri=0}drawRec();if(show&&recs.length){$("cmd").value=recs[ri].text;fb(esc(recs[ri].reason),"ok")}}
function drawRec(){const r=recs[ri];if(!r){$("rec").textContent="—";$("recwhy").textContent="";return}
 $("rec").style.color="";$("rec").textContent="« "+r.text+" »";$("recwhy").textContent="Basé sur : "+r.reason}
$("bex").onclick=()=>doExec($("cmd").value);$("bsim").onclick=()=>doSim($("cmd").value);$("brec").onclick=()=>loadRec(true);
$("cmd").addEventListener("keydown",e=>{if(e.key==="Enter")doExec($("cmd").value)});
$("rexec").onclick=()=>recs[ri]&&doExec(recs[ri].text,true);$("rsim").onclick=()=>recs[ri]&&doSim(recs[ri].text);
$("rnext").onclick=()=>{if(recs.length){ri=(ri+1)%recs.length;drawRec()}};
$("bghost").onclick=()=>{ghosts=null;$("bghost").style.display="none"};
document.querySelectorAll(".rtool [data-r]").forEach(b=>b.onclick=()=>{range=+b.dataset.r;document.querySelectorAll(".rtool [data-r]").forEach(x=>x.classList.toggle("on",x===b))});
// ---------- radar
const cv=$("cv"),cx=cv.getContext("2d");let W=0,H=0,DPR=1;
function fit(){const r=$("rad").getBoundingClientRect();DPR=window.devicePixelRatio||1;W=r.width;H=r.height;cv.width=W*DPR;cv.height=H*DPR;cx.setTransform(DPR,0,0,DPR,0,0)}
window.addEventListener("resize",fit);fit();
function arrow(x1,y1,x2,y2,col,w){cx.strokeStyle=col;cx.fillStyle=col;cx.lineWidth=w||1.5;cx.beginPath();cx.moveTo(x1,y1);cx.lineTo(x2,y2);cx.stroke();const a=Math.atan2(y2-y1,x2-x1),h=9;cx.beginPath();cx.moveTo(x2,y2);cx.lineTo(x2-h*Math.cos(a-0.4),y2-h*Math.sin(a-0.4));cx.lineTo(x2-h*Math.cos(a+0.4),y2-h*Math.sin(a+0.4));cx.closePath();cx.fill()}
function draw(){if(!S||!S.ships)return;const o=S.ships.find(s=>s.name===view)||S.ships[0];fit_if();cx.clearRect(0,0,W,H);
 const R=Math.min(W,H)/2-30,k=R/(range*NM),mx=W/2,my=H/2;const X=x=>mx+(x-o.x)*k,Y=y=>my-(y-o.y)*k;
 cx.lineWidth=1;cx.strokeStyle="#16253f";cx.fillStyle="#6f86ab";cx.font="11px Segoe UI";
 for(let i=1;i<=4;i++){cx.beginPath();cx.arc(mx,my,R*i/4,0,7);cx.stroke();cx.fillText(fnm(range*i/4)+" NM",mx+4,my-R*i/4+12)}
 for(let a=0;a<360;a+=30){const r=a*Math.PI/180;cx.beginPath();cx.moveTo(mx+Math.sin(r)*R*0.04,my-Math.cos(r)*R*0.04);cx.lineTo(mx+Math.sin(r)*R,my-Math.cos(r)*R);cx.strokeStyle=a%90===0?"#1d3156":"#101d33";cx.stroke();
  const t=String(a).padStart(3,"0");cx.fillStyle="#8196b8";cx.textAlign="center";cx.fillText(t,mx+Math.sin(r)*(R+15),my-Math.cos(r)*(R+15)+4)}cx.textAlign="start";
 // sillages
 S.ships.forEach(s=>{const a=trails[s.name]||[];cx.strokeStyle=s.name===S.player?"#3ddc8455":"#4aa3ff40";cx.lineWidth=1.5;cx.beginPath();a.forEach((p,i)=>i?cx.lineTo(X(p[0]),Y(p[1])):cx.moveTo(X(p[0]),Y(p[1])));cx.stroke()});
 // fantomes
 if(ghosts&&Date.now()<ghosts.until){let gi=0;Object.entries(ghosts.paths).forEach(([n,pts])=>{const c=n===S.player?"#f5b73b":"#7ad7ff";cx.strokeStyle=c;cx.setLineDash([7,6]);cx.lineWidth=2;cx.beginPath();pts.forEach((p,i)=>i?cx.lineTo(X(p[0]),Y(p[1])):cx.moveTo(X(p[0]),Y(p[1])));cx.stroke();cx.setLineDash([]);
   const l=pts[pts.length-1],q=pts[pts.length-3]||pts[0],ang=Math.atan2(X(l[0])-X(q[0]),Y(q[1])-Y(l[1]));cx.save();cx.translate(X(l[0]),Y(l[1]));cx.rotate(ang);cx.fillStyle=c;cx.beginPath();cx.moveTo(0,-8);cx.lineTo(6,7);cx.lineTo(-6,7);cx.closePath();cx.fill();cx.restore();
   pts.forEach(p=>{if(p[2]%120===0&&p[2]>0){cx.fillStyle=c;cx.beginPath();cx.arc(X(p[0]),Y(p[1]),2.5,0,7);cx.fill()}})})}
 else if(ghosts){ghosts=null;$("bghost").style.display="none"}
 // contacts
 S.contacts.forEach(c=>{const px=X(c.x),py=Y(c.y),col=CLS[c.cls]||"#f5b73b";const vx=Math.sin(c.cap*Math.PI/180)*c.vit*0.514444*600,vy=Math.cos(c.cap*Math.PI/180)*c.vit*0.514444*600;
  {const m=Math.hypot(vx*k,vy*k)||1,f=34/m;arrow(px+Math.sin(c.cap*Math.PI/180)*12,py-Math.cos(c.cap*Math.PI/180)*12,px+vx*k*f,py-vy*k*f,col,2)}
  cx.strokeStyle=col;cx.lineWidth=2;cx.strokeRect(px-8,py-8,16,16);if(c.id===sel){cx.beginPath();cx.arc(px,py,16,0,7);cx.stroke()}
  cx.fillStyle=col;cx.font="bold 11px Segoe UI";cx.textAlign="center";cx.fillText(c.cls==="inconnu"?"?":c.cls[0].toUpperCase(),px,py+4);cx.font="11px Segoe UI";cx.fillText(c.id,px,py-14);cx.textAlign="start"});
 // navires
 S.ships.forEach(s=>{const px=X(s.x),py=Y(s.y),me=s.name===S.player,r=s.hdg*Math.PI/180;
  {const L=24,col=me?"#3ddc84":"#7fb8f5";cx.globalAlpha=.9;arrow(px+Math.sin(r)*12,py-Math.cos(r)*12,px+Math.sin(r)*(12+L),py-Math.cos(r)*(12+L),col,1.6);cx.globalAlpha=1}cx.save();cx.translate(px,py);cx.rotate(r);cx.fillStyle=me?"#ffffff":"#4aa3ff";cx.strokeStyle=me?"#3ddc84":"#0b1830";cx.lineWidth=me?2:1;cx.beginPath();cx.moveTo(0,-11);cx.lineTo(6.5,8);cx.lineTo(0,4);cx.lineTo(-6.5,8);cx.closePath();cx.fill();cx.stroke();cx.restore();
  cx.fillStyle=me?"#fff":"#9cc9ff";cx.font=(me?"bold ":"")+"11px Segoe UI";const sd=(s.name.charCodeAt(0)+s.name.length)%2?1:-1;cx.textAlign=sd>0?"left":"right";cx.fillText(s.name.toUpperCase()+(s.name===S.guide?" ★":""),px+14*sd,py+1);cx.fillStyle="#8196b8";cx.font="10px Segoe UI";cx.fillText(String(Math.round(s.hdg)%360).padStart(3,"0")+"° · "+Math.round(s.sog/0.514444)+" kn",px+14*sd,py+13);cx.textAlign="start"});
 $("rfoot").textContent=`Radar centré sur ${o.name.toUpperCase()} · nord en haut · portée ${range} NM`}
function fit_if(){const r=$("rad").getBoundingClientRect();if(Math.abs(r.width-W)>1||Math.abs(r.height-H)>1)fit()}
cv.addEventListener("click",e=>{if(!S||!S.ships)return;const r=cv.getBoundingClientRect(),o=S.ships.find(s=>s.name===view)||S.ships[0],R=Math.min(W,H)/2-30,k=R/(range*NM);
 const px=e.clientX-r.left,py=e.clientY-r.top;let best=null,bd=22;S.contacts.forEach(c=>{const d=Math.hypot(W/2+(c.x-o.x)*k-px,H/2-(c.y-o.y)*k-py);if(d<bd){bd=d;best=c.id}});if(best)sel=best});
es();

$("bauto").onclick=()=>post("/api/auto",{on:!(S&&S.auto)});

// ---------- HANNIBAL X : voix -> signal -> approbation
let dest="TOUS", cur=null, rec=null, wantStop=false, sndOn=true, lastSpoken=0, firstMsgs=true;
function vst(html,cls){const f=$("vst");f.className="fb "+(cls||"");f.innerHTML=html}
function renderDest(){if(!S||!S.ships)return;const names=["TOUS"].concat(S.ships.filter(s=>s.name!==S.player).map(s=>s.name.toUpperCase()));
 $("dest").innerHTML=names.map(n=>`<button class="btn ${n===dest?"on":""}" data-d="${n}">${n==="TOUS"?"Tous les navires":n}</button>`).join("");
 $("dest").querySelectorAll("[data-d]").forEach(b=>b.onclick=()=>{dest=b.dataset.d;renderDest()})}
function words(c){if(!c.words||!c.words.length)return esc(c.transcript);
 return c.words.map(w=>`<span class="${w.p<0.3?"vlo":w.p<0.6?"lo":""}" title="confiance ${Math.round(w.p*100)} %">${esc(w.w)}</span>`).join(" ")}
function showCmd(c){cur=c;const ok=c.status==="ok",st=c.state;
 const pr=Object.entries(c.params||{}).map(([k,v])=>({side:"Bord",relative_degrees:"Degrés (relatif)",true_course:"Cap vrai",true_bearing:"Relèvement vrai",relative_bearing_degrees:"Relèvement relatif",speed_knots:"Vitesse (nœuds)",formation_number:"Formation n°"}[k]?`<span>${({side:"Bord",relative_degrees:"Degrés (relatif)",true_course:"Cap vrai",true_bearing:"Relèvement vrai",relative_bearing_degrees:"Relèvement relatif",speed_knots:"Vitesse (nœuds)",formation_number:"Formation n°"})[k]}</span><span class="mono">${esc(v==="STBD"?"Tribord (STBD)":v==="PORT"?"Bâbord (PORT)":v)}</span>`:"")).join("");
 const notes=(c.warnings||[]).concat(c.notes||[]);
 let h=`<div style="margin-top:10px"><div style="color:var(--mut);font-size:11.5px;margin-bottom:3px">${c.source==="voix"?"Entendu (Whisper "+esc(c.asr_model||"")+", "+(c.asr_seconds||0)+" s) · mots incertains soulignés":"Saisi au clavier"} · ${esc(c.id)}</div>
 <div class="tw">${words(c)}</div>
 <div class="cmd" style="margin-top:6px"><input id="vfix" value="${esc(c.transcript).replace(/"/g,"&quot;")}" spellcheck="false"><button class="btn sm" id="vre">Corriger</button></div>
 <div style="margin-top:10px"><span class="st ${ok?"ok":"ko"}">${esc(c.status_fr)}</span> ${c.to?`<span class="st wa">→ ${c.to[0]==="TOUS"?"Tous les navires":esc(c.to[0])}</span>`:""}</div>`;
 const PL={side:"Bord",relative_degrees:"Degrés (relatif)",true_course:"Cap vrai",true_bearing:"Relèvement vrai",relative_bearing_degrees:"Relèvement relatif (degrés)",speed_knots:"Vitesse (nœuds)",formation_number:"Formation n°"};
 const gs=(c.groups&&c.groups.length)?c.groups:[{signal:c.signal,meaning:c.meaning,reference:c.reference,params:c.params,status:c.status}];
 gs.forEach(g=>{if(!g.signal)return;const kv=Object.entries(g.params||{}).filter(([k])=>PL[k]).map(([k,v])=>`<span>${PL[k]}</span><span class="mono">${esc(v==="STBD"?"Tribord (STBD)":v==="PORT"?"Bâbord (PORT)":v)}</span>`).join("");
  h+=`<div class="pub"${g.status&&g.status!=="ok"?' style="border-left-color:var(--red)"':""}><b class="mono">${esc(g.signal)}</b>${g.status&&g.status!=="ok"?` <span class="st ko">${esc(g.status_fr||"")}</span>`:""}${g.meaning?"<br>"+esc(g.meaning):""}<small>${esc(g.reference||"")}</small>${kv?`<div class="kv">${kv}</div>`:""}</div>`});
 if(c.hint)h+=`<div style="font-size:12.5px;margin-top:8px;color:var(--ink)">${esc(c.hint)}</div>`;
 h+=`<div style="margin-top:8px;font-weight:600">${esc(c.fr)}</div>`;
 if(c.effect)h+=`<div style="font-size:12.5px;color:var(--mut);margin-top:3px">Dans le simulateur : ${esc(c.effect)}</div>`;
 if(notes.length)h+=notes.map(n=>`<div class="note">⚠ ${esc(n)}</div>`).join("");
 if(st==="awaiting_review")h+=`<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px"><button class="btn green" id="vok" ${c.can_execute?"":"disabled"}>Approuver et exécuter</button><button class="btn" id="vko">Rejeter</button></div>`;
 else h+=`<div style="margin-top:10px"><span class="st ${st==="approved"?"ok":"ko"}">${st==="approved"?"Approuvé, exécuté et consigné":"Rejeté et consigné"}</span></div>`;
 if(ok&&!c.legacy)h+=`<div class="ia" id="via">${c.llm?llmHtml(c.llm):`<button class="btn sm" id="vllm">Explication détaillée (IA locale)</button>`}</div>`;
 h+="</div>";$("vres").innerHTML=h;
 if($("vok"))$("vok").onclick=()=>decide("execute");if($("vko"))$("vko").onclick=()=>decide("reject");
 $("vre").onclick=async()=>{const t=$("vfix").value;if(st==="awaiting_review")await post("/api/confirm",{id:c.id,decision:"reject"});const r=await post("/api/interpret",{text:t,target:dest,parent:c.id});if(r.ok)showCmd(r.cmd);else vst(esc(r.error),"err")};
 $("vfix").addEventListener("keydown",e=>{e.stopPropagation();if(e.key==="Enter")$("vre").click()});
 if($("vllm"))$("vllm").onclick=async()=>{$("via").innerHTML="<small>Le modèle local rédige l'explication…</small>";const r=await post("/api/explain",{id:c.id});if(r.ok){c.llm=r.llm;$("via").innerHTML=llmHtml(r.llm)}else $("via").innerHTML=`<small>${esc(r.error)}</small>`}}
function llmHtml(l){return `<small>${l.explanation_source==="repli_deterministe"?"Texte de la publication (l'explication de l'IA n'a pas passé le contrôle)":"Explication de l'IA locale ("+esc(l.llm||"")+") — aide à la lecture, le texte de la publication fait foi"}</small><div style="margin-top:4px">${esc(l.explanation_fr||"")}</div>`
 +((l.ambiguities||[]).length?`<div class="note">${l.ambiguities.map(esc).join("<br>")}</div>`:"")}
async function decide(d){if(!cur)return;const r=await post("/api/confirm",{id:cur.id,decision:d});
 if(!r.ok)return vst(esc(r.error),"err");showCmd(r.cmd);vst(d==="execute"?"✓ Envoyé : "+esc(r.en||""):"Message rejeté.",d==="execute"?"ok":"");ghosts=null;lastRec=0}
async function sendAudio(blob){vst("Transcription et recherche du signal…");$("vres").innerHTML="";
 try{const r=await (await fetch("/api/voice?target="+encodeURIComponent(dest),{method:"POST",body:blob})).json();
  if(!r.ok)return vst(esc(r.error),"err");vst("");showCmd(r.cmd)}catch(e){vst("Envoi impossible : "+esc(e.message),"err")}}
function wav16k(a,sr){const ratio=sr/16000,m=Math.floor(a.length/ratio),buf=new ArrayBuffer(44+m*2),v=new DataView(buf);
 const W=(o,t)=>{for(let i=0;i<t.length;i++)v.setUint8(o+i,t.charCodeAt(i))};
 W(0,"RIFF");v.setUint32(4,36+m*2,true);W(8,"WAVEfmt ");v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);W(36,"data");v.setUint32(40,m*2,true);
 for(let i=0;i<m;i++){const s=Math.floor(i*ratio),e=Math.min(a.length,Math.max(s+1,Math.floor((i+1)*ratio)));let acc=0;for(let j=s;j<e;j++)acc+=a[j];v.setInt16(44+i*2,Math.max(-1,Math.min(1,acc/(e-s)))*32767,true)}
 return new Blob([buf],{type:"audio/wav"})}
async function micStart(){if(rec||micStart.busy)return;wantStop=false;
 if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)return vst("Micro bloqué par le navigateur sur cette adresse. Ouvrez la console par <b>http://localhost:8771</b> (tunnel SSH), ou importez un fichier audio.","err");
 micStart.busy=true;
 try{const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});
  const ctx=new (window.AudioContext||window.webkitAudioContext)(),src=ctx.createMediaStreamSource(stream),proc=ctx.createScriptProcessor(4096,1,1),chunks=[];
  proc.onaudioprocess=e=>chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));src.connect(proc);proc.connect(ctx.destination);
  rec={stream,ctx,src,proc,chunks};$("bmic").classList.add("rec");$("bmic").textContent="Écoute… relâchez pour envoyer";vst("");
  if(wantStop)micStop()}
 catch(e){vst("Accès au micro refusé : "+esc(e.message),"err")}
 micStart.busy=false}
async function micStop(){wantStop=true;if(!rec)return;const r=rec;rec=null;$("bmic").classList.remove("rec");$("bmic").textContent="Maintenir pour parler (ou barre d'espace)";
 r.proc.disconnect();r.src.disconnect();r.stream.getTracks().forEach(t=>t.stop());const sr=r.ctx.sampleRate;await r.ctx.close();
 const n=r.chunks.reduce((x,c)=>x+c.length,0),a=new Float32Array(n);let o=0;r.chunks.forEach(c=>{a.set(c,o);o+=c.length});
 if(n/sr<0.7)return vst("Enregistrement trop court : maintenez le bouton pendant que vous parlez.","err");
 sendAudio(wav16k(a,sr))}
$("bmic").addEventListener("mousedown",micStart);$("bmic").addEventListener("touchstart",e=>{e.preventDefault();micStart()});
window.addEventListener("mouseup",()=>{if(rec||micStart.busy)micStop()});$("bmic").addEventListener("touchend",micStop);
window.addEventListener("keydown",e=>{if(e.code==="Space"&&!e.repeat&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();micStart()}});
window.addEventListener("keyup",e=>{if(e.code==="Space"&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();micStop()}});
$("fwav").onchange=e=>{const f=e.target.files[0];if(f)sendAudio(f);e.target.value=""};
// accuses de reception lus a voix haute par le navigateur
function speakNew(){const ms=(S&&S.msgs)||[];if(firstMsgs){firstMsgs=false;lastSpoken=ms.length?ms[ms.length-1].id:0;return}
 ms.filter(m=>m.id>lastSpoken).forEach(m=>{lastSpoken=m.id;if(!sndOn||!window.speechSynthesis||!m.en||m.kind==="joueur"||m.kind==="info"||m.kind==="plan")return;
  const u=new SpeechSynthesisUtterance(m.en.replace(/\bSTBD\b/g,"starboard"));u.lang="en-GB";u.rate=1.05;speechSynthesis.speak(u)})}
$("bsnd").onclick=()=>{sndOn=!sndOn;$("bsnd").textContent="Son radio : "+(sndOn?"activé":"coupé");if(!sndOn&&window.speechSynthesis)speechSynthesis.cancel()};
function renderReq(){const rq=(S&&S.requests)||[];const sig=rq.map(r=>r.ship+r.cid).join("|");if(sig===renderReq.sig)return;renderReq.sig=sig;
 $("vreq").innerHTML=rq.map(r=>`<div class="req"><div>${esc(r.fr)}</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:7px"><button class="btn green" data-y="${esc(r.ship)}">Accorder</button><button class="btn" data-n="${esc(r.ship)}">Refuser</button></div><small>ou dites : « ${esc(r.ship.toUpperCase())}, this is ${esc(S.player.toUpperCase())}, affirmative » / « negative »</small></div>`).join("");
 $("vreq").querySelectorAll("[data-y]").forEach(b=>b.onclick=()=>post("/api/reply",{ship:b.dataset.y,yes:true}));
 $("vreq").querySelectorAll("[data-n]").forEach(b=>b.onclick=()=>post("/api/reply",{ship:b.dataset.n,yes:false}))}
const _render=render;render=function(){_render();if(S&&S.ships){if(!$("dest").children.length)renderDest();speakNew();renderReq()}};
fetch("/api/hx").then(r=>r.json()).then(d=>{const ok=d&&d.ok;$("hxdot").className="dot"+(ok?" ok":"");$("hxtxt").textContent=ok?"Voix : Whisper "+d.whisper+" local · "+d.signals+" signaux MTP":"Voix : service indisponible"}).catch(()=>{$("hxtxt").textContent="Voix : service indisponible"});

// ---------- barre manuelle : gouverner son navire au clavier ou aux boutons
const HK={l:false,r:false};let lastRud=0;
function sendRud(){const r=HK.l&&!HK.r?-1:HK.r&&!HK.l?1:0;if(r!==lastRud){lastRud=r;post("/api/helm",{rudder:r})}$("hl").classList.toggle("on",r<0);$("hr").classList.toggle("on",r>0)}
const typing=()=>/INPUT|TEXTAREA/.test(document.activeElement.tagName);
window.addEventListener("keydown",e=>{if(!S||!S.manual||typing())return;
 if(e.key==="ArrowLeft"){HK.l=true;sendRud();e.preventDefault()}else if(e.key==="ArrowRight"){HK.r=true;sendRud();e.preventDefault()}
 else if(e.key==="ArrowUp"){post("/api/helm",{dkn:1});e.preventDefault()}else if(e.key==="ArrowDown"){post("/api/helm",{dkn:-1});e.preventDefault()}});
window.addEventListener("keyup",e=>{if(e.key==="ArrowLeft"){HK.l=false;sendRud()}else if(e.key==="ArrowRight"){HK.r=false;sendRud()}});
window.addEventListener("blur",()=>{HK.l=HK.r=false;sendRud()});
[["hl","l"],["hr","r"]].forEach(([id,k])=>{const b=$(id);b.addEventListener("mousedown",()=>{HK[k]=true;sendRud()});["mouseup","mouseleave"].forEach(ev=>b.addEventListener(ev,()=>{if(HK[k]){HK[k]=false;sendRud()}}))});
$("hm").onclick=()=>post("/api/helm",{dkn:-1});$("hp").onclick=()=>post("/api/helm",{dkn:1});
function renderHelm(){const el=$("helm");if(!S||!S.manual){el.style.display="none";return}el.style.display="";
 const me=S.ships.find(x=>x.name===S.player);if(!me)return;const f3=n=>String(Math.round(n)%360).padStart(3,"0");
 $("hcap").textContent=f3(me.hdg)+"°";$("hcapo").textContent=S.helm.rudder?(S.helm.rudder<0?"barre à bâbord":"barre à tribord"):"ordonné "+f3(S.helm.cap)+"°";
 $("hkn").textContent=Math.round(me.sog/0.514444)+" kn";$("hkno").textContent="ordonné "+Math.round(S.helm.kn)+" kn";
 let info="Vous gouvernez "+S.player.toUpperCase()+" · ← → barre (maintenir) · ↑ ↓ vitesse";
 if(S.station)info+=" · <b>poste à "+S.station.err+" m</b>"+(S.station.err<200?" (en station)":"");
 if(S.pending&&S.pending.length)info+="<br>À exécuter à la barre : <b>"+S.pending.map(p=>esc(p.fr)).join(" ; ")+"</b>";
 $("hinfo").innerHTML=info}
const _draw2=draw;draw=function(){_draw2();if(!S||!S.ships||!S.station)return;const o=S.ships.find(x=>x.name===view)||S.ships[0],R=Math.min(W,H)/2-30,k=R/(range*NM);
 const px=W/2+(S.station.x-o.x)*k,py=H/2-(S.station.y-o.y)*k;cx.strokeStyle="#f5b73b";cx.lineWidth=1.5;cx.setLineDash([4,3]);cx.beginPath();cx.moveTo(px,py-9);cx.lineTo(px+9,py);cx.lineTo(px,py+9);cx.lineTo(px-9,py);cx.closePath();cx.stroke();cx.setLineDash([]);
 cx.fillStyle="#f5b73b";cx.font="10px Segoe UI";cx.fillText("votre poste",px+12,py-8)};
const _render3=render;render=function(){_render3();if(S&&S.ships)renderHelm()};
