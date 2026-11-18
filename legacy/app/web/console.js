"use strict";
(()=>{const d=Object.getOwnPropertyDescriptor(Element.prototype,"innerHTML");Object.defineProperty(Element.prototype,"innerHTML",{get:d.get,set(v){if(this.__h!==v){this.__h=v;d.set.call(this,v)}},configurable:true})})();
const $=id=>document.getElementById(id), NM=1852;
const fnm=v=>(v==null?"—":v.toFixed(1).replace(".",","));
const p2=n=>String(Math.floor(n)).padStart(2,"0"), mmss=t=>p2(t/60)+":"+p2(t%60);
const esc=s=>String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
let S=null, view=null, sel=null, range=4, ghosts=null, recs=[], ri=0, recSig="", trails={}, lastRec=0, sid=null;
const COLS={hannibal:"#4aa3ff",alfa:"#4aa3ff",charlie:"#4aa3ff",delta:"#4aa3ff"}, CLS={inconnu:"#f5b73b",ami:"#4aa3ff",neutre:"#2dd4bf",hostile:"#ff5d5d"};
const GCOL=["#f5b73b","#3ddc84","#ff7ad9","#7ad7ff"];

function es(){const e=new EventSource("/events");e.onmessage=m=>{S=JSON.parse(m.data);render()};e.onerror=()=>{}}
function render(){
 if(!S||S.phase!=="running"&&S.phase!=="starting"){if(S&&S.phase==="idle"){location.href="/"}return}
 if(!S.ships)return;
 if(!view)view=S.player;
 $("hsc").textContent="Scénario : "+S.titre;$("hclk").textContent=mmss(S.t)+" / "+mmss(S.duree);
 S.ships.forEach(s=>{const a=trails[s.name]=trails[s.name]||[];const l=a[a.length-1];if(!l||Math.hypot(l[0]-s.x,l[1]-s.y)>25)a.push([s.x,s.y]);if(a.length>160)a.shift()});
 if(!sel||!S.contacts.find(c=>c.id===sel))sel=S.contacts.length?S.contacts[S.contacts.length-1].id:null;
 renderObj();$("bauto").textContent=S.auto?"Mode : Auto capitaine":"Mode : Normal";$("bauto").style.borderColor=S.auto?"var(--green)":"";renderContact();renderShips();renderMsgs();renderBar();renderPlan();renderDebrief();
 $("halert").style.display=S.contacts.some(c=>c.cls==="inconnu")?"":"none";
 if(Date.now()-lastRec>3000){lastRec=Date.now();loadRec(false)}
 draw()}
function renderObj(){$("obj").innerHTML=(S.attendu||[]).map(a=>{const late=!a.ok&&S.t>a.avant_t+90,soon=!a.ok&&!late&&S.t>a.avant_t-30;return `<div style="display:flex;gap:8px;padding:4px 0;border-top:1px solid var(--line)"><span style="color:${a.ok?"var(--green)":late?"var(--red)":soon?"var(--amber)":"var(--mut)"}">${a.ok?"✓":late?"✗":"○"}</span><div>${esc(a.texte)}<br><small style="color:var(--mut)">avant ${mmss(a.avant_t)}${a.ok?"":" (+1 min 30)"}</small></div></div>`}).join("")}
function renderContact(){const c=S.contacts.find(x=>x.id===sel),b=$("cbody");
 if(!c){b.innerHTML="Aucun contact dans ce scénario (ou pas encore détecté). Pour une piste ennemie, lance « Menace ennemie ».";b.style.color="var(--mut)";return}
 b.style.color="";const mode=c.tcpa_min!=null&&c.tcpa_min>0?"dans ~"+Math.round(c.tcpa_min)+" min":"maintenant";
 b.innerHTML=`<div class="mono" style="color:var(--mut);font-size:12px">${esc(c.id)}</div><div class="big">${esc(c.type)} · ${esc(c.cls)}</div>
 <dl><dt>Relèvement</dt><dd class="mono">${p2(Math.round(c.brg)%360).padStart(3,"0")}°</dd><dt>Distance</dt><dd class="mono">${fnm(c.range_nm)} NM</dd>
 <dt>Cap / vitesse</dt><dd class="mono">${String(c.cap).padStart(3,"0")}° · ${c.vit} kn</dd><dt>CPA estimé</dt><dd class="mono">${fnm(c.cpa_nm)} NM ${mode}</dd></dl>
 <p class="lbl" style="margin:12px 0 0">Classer le contact</p><div class="cls">
 ${[["ami","a","Ami"],["neutre","n","Neutre"],["hostile","h","Hostile"],["inconnu","i","Inconnu"]].map(k=>`<button class="btn ${k[1]} ${c.cls===k[0]?"on":""}" data-c="${k[0]}">${k[2]}</button>`).join("")}</div>`;
 b.querySelectorAll("[data-c]").forEach(x=>x.onclick=()=>post("/api/classify",{id:c.id,cls:x.dataset.c}))}
function renderShips(){$("tships").innerHTML=S.ships.map(s=>`<tr class="row" data-n="${s.name}"><td><span class="sdot" style="background:${s.name===S.player?"#3ddc84":"#4aa3ff"}"></span>${s.name.toUpperCase()}${s.name===S.guide?" ★":""}</td><td class="mono">${String(Math.round(s.hdg)%360).padStart(3,"0")}°</td><td class="mono">${Math.round(s.sog/0.514444)} kn</td><td>${s.etat}</td></tr>`).join("");
 $("tships").querySelectorAll("tr").forEach(r=>r.onclick=()=>{view=r.dataset.n})}
function renderMsgs(){const ms=S.msgs||[];
 $("log").innerHTML=ms.slice().reverse().slice(0,12).map(m=>`<div class="${m.kind}"><span class="t mono">${mmss(m.t)}</span> <b>${esc(m.from)}</b> → ${esc(m.to)} · ${esc(m.fr||m.en)}</div>`).join("");
 const rx=ms.filter(m=>["ordre","urgence"].includes(m.kind)).slice(-1)[0];
 if(rx){const w=$("rx");w.style.color="";w.innerHTML=`<div style="color:var(--mut);font-size:11.5px;margin-bottom:5px">${mmss(rx.t)} · ${esc(rx.from)} → ${esc(rx.to)} · VHF</div>« ${esc(rx.en)} »`;
  $("tr").style.color="";$("tr").textContent=rx.fr;
  const u=rx.kind==="urgence";$("trkv").innerHTML=`<span>Niveau</span><span>${u?"Alerte, non classifié":rx.pending?"Ordre à exécuter":"Ordre routine"}</span><span>Source</span><span>Règles MTP 1(D), sans IA</span><span>Statut</span><span>${rx.pending?"En attente de ton exécution":"Pris en compte"}</span>`}}
function renderBar(){const el=$("bar");
 el.innerHTML=S.ships.map(s=>`<button class="pill ${s.name===view?"on":""} ${s.name===S.player?"me":""}" data-n="${s.name}"><b>${s.name.toUpperCase()}${s.name===S.guide?" ★":""}</b><small class="mono">${String(Math.round(s.hdg)%360).padStart(3,"0")}° · ${Math.round(s.sog/0.514444)} kn · ${s.name===S.player?"Vous":s.role==="guide"?"Guide":"Escorte"}</small></button>`).join("")
  +`<div class="prog"><i style="width:${Math.min(100,100*S.t/S.duree)}%"></i></div><button class="btn sm" id="bstop">Arrêter</button>`;
 el.querySelectorAll(".pill").forEach(b=>b.onclick=()=>{view=b.dataset.n});$("bstop").onclick=async()=>{await post("/api/stop",{});location.href="/"}}
function renderPlan(){const c=$("cplan"),isG=S.player===S.guide;let h="";
 if(isG&&S.plan.length){$("cplant").textContent="Ordres prévus par le scénario (à donner)";h=S.plan.map(p=>`<div style="padding:4px 0;border-top:1px solid var(--line)"><span class="mono" style="color:var(--mut)">${mmss(p.t)}</span> ${esc(p.fr)}<br><span class="mono" style="color:var(--mut);font-size:12px">${esc(p.en)}</span></div>`).join("")}
 else if(!isG&&S.pending.length){$("cplant").textContent="Ordres reçus à exécuter";h=S.pending.map(p=>`<div style="padding:4px 0;border-top:1px solid var(--line);color:var(--amber)">${esc(p.fr)}</div>`).join("")}
 c.style.display=h?"":"none";$("plan").innerHTML=h}
function renderDebrief(){if(!S.ended||!S.debrief)return;const d=S.debrief;$("deb").classList.add("on");$("dt").textContent=`Score : ${d.score} / ${d.total}`;
 $("db").innerHTML=d.checks.map(c=>`<div class="chk"><span class="${c.ok?"ok":"ko"}">${c.ok?"✓":"✗"}</span><div>${esc(c.texte)}<br><small style="color:var(--mut)">avant ${mmss(c.avant_t)}${c.t!=null?" · fait à "+mmss(c.t):""}</small></div></div>`).join("")
 +`<div class="chk"><span>•</span><div>Distance minimale entre navires : <b>${d.min_ship_m==null?"—":d.min_ship_m+" m"}</b></div></div>`
 +Object.entries(d.min_cpa).map(([k,v])=>`<div class="chk"><span>•</span><div>Plus courte distance à ${esc(k)} : <b>${fnm(v)} NM</b></div></div>`).join("")
 +Object.entries(d.classes).map(([k,v])=>`<div class="chk"><span class="${v.choisie===v.reelle?"ok":"ko"}">${v.choisie===v.reelle?"✓":"✗"}</span><div>${esc(k)} classé « ${v.choisie} » (réel : ${v.reelle})</div></div>`).join("")}
$("dhome").onclick=async()=>{await post("/api/stop",{});location.href="/"};
$("dre").onclick=async()=>{const sc=S.titre;const list=await (await fetch("/api/scenarios")).json();const s=list.find(x=>x.titre===sc);const me=S.player;await post("/api/stop",{});await post("/api/start",{scenario:s.id,player:me,unity:false});location.href="/"};
// ---------- actions
async function post(u,b){return (await fetch(u,{method:"POST",body:JSON.stringify(b)})).json()}
function fb(html,cls){const f=$("fb");f.className="fb "+(cls||"");f.innerHTML=html}
async function doExec(text){if(!text.trim())return fb("Tape un ordre, par exemple CORPEN 090.","err");const r=await post("/api/order",{text});
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
$("rexec").onclick=()=>recs[ri]&&doExec(recs[ri].text);$("rsim").onclick=()=>recs[ri]&&doSim(recs[ri].text);
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
  cx.fillStyle=me?"#fff":"#9cc9ff";cx.font=(me?"bold ":"")+"11px Segoe UI";cx.textAlign="center";cx.textAlign="left";cx.fillText(s.name.toUpperCase()+(s.name===S.guide?" ★":""),px+14,py+4);cx.fillStyle="#8196b8";cx.font="10px Segoe UI";cx.fillText(String(Math.round(s.hdg)%360).padStart(3,"0")+"° · "+Math.round(s.sog/0.514444)+" kn",px+14,py+16);cx.textAlign="start"});
 $("rfoot").textContent=`Radar centré sur ${o.name.toUpperCase()} · nord en haut · portée ${range} NM`}
function fit_if(){const r=$("rad").getBoundingClientRect();if(Math.abs(r.width-W)>1||Math.abs(r.height-H)>1)fit()}
cv.addEventListener("click",e=>{if(!S||!S.ships)return;const r=cv.getBoundingClientRect(),o=S.ships.find(s=>s.name===view)||S.ships[0],R=Math.min(W,H)/2-30,k=R/(range*NM);
 const px=e.clientX-r.left,py=e.clientY-r.top;let best=null,bd=22;S.contacts.forEach(c=>{const d=Math.hypot(W/2+(c.x-o.x)*k-px,H/2-(c.y-o.y)*k-py);if(d<bd){bd=d;best=c.id}});if(best)sel=best});
es();

$("bauto").onclick=()=>post("/api/auto",{on:!(S&&S.auto)});
