// Hannibal · Vue 3D — rendu WebGL (three.js embarqué, aucune dépendance Internet)
import * as THREE from "three";
import { OrbitControls } from "/static/vendor/OrbitControls.js";
import { GLTFLoader } from "/static/vendor/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "/static/vendor/meshopt_decoder.module.js";

const $ = id => document.getElementById(id), KN = 0.514444, NM = 1852, D2R = Math.PI / 180;
const p3 = n => String(Math.round(n) % 360).padStart(3, "0"), p2 = n => String(Math.floor(n)).padStart(2, "0"), mmss = t => p2(t / 60) + ":" + p2(t % 60);
const DEMO = new URLSearchParams(location.search).has("demo");

// ---------------------------------------------------------------- rendu
let renderer;
try { renderer = new THREE.WebGLRenderer({ canvas: $("gl"), antialias: true, powerPreference: "high-performance" }); }
catch (e) { $("err").style.display = "flex"; $("errt").textContent = "WebGL n'est pas disponible dans ce navigateur (" + e.message + ")."; throw e; }
const QP = new URLSearchParams(location.search), QLOW = QP.get("q") === "low", QHIGH = QP.get("q") === "high", QSTATS = QP.get("stats") === "1";
let PR = Math.min(window.devicePixelRatio || 1, QLOW ? 1 : QHIGH ? 2 : 1.5);
renderer.setPixelRatio(PR); renderer.shadowMap.enabled = !QLOW; renderer.shadowMap.type = QHIGH ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.9;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, 1, 3, 60000);
camera.position.set(-260, 90, 330);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.minDistance = 90; controls.maxDistance = 9000; controls.maxPolarAngle = Math.PI / 2 - 0.02; controls.enablePan = false;
function resize() { renderer.setSize(innerWidth, innerHeight, false); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); }
addEventListener("resize", resize); resize();

// ---------------------------------------------------------------- ambiances
const AMB = {
  "Bleu marine": { el: 40, az: 205, hor: [0.56, 0.61, 0.70], zen: [0.045, 0.125, 0.40], sun: [1.0, 0.96, 0.90], deep: [0.003, 0.012, 0.036], scat: [0.010, 0.040, 0.085], light: 2.7, hemi: 1.6, exp: 0.92, calm: 0.38, cov: 0.63, fog: 0.00003 },
  Jour: { el: 34, az: 140, hor: [0.60, 0.74, 0.88], zen: [0.10, 0.27, 0.58], sun: [1.0, 0.95, 0.86], deep: [0.008, 0.055, 0.11], scat: [0.02, 0.19, 0.25], light: 2.7, hemi: 1.7, exp: 0.9 },
  "Crépuscule": { el: 6, az: 250, hor: [0.98, 0.56, 0.30], zen: [0.09, 0.13, 0.33], sun: [1.0, 0.55, 0.25], deep: [0.008, 0.025, 0.06], scat: [0.07, 0.09, 0.12], light: 2.0, hemi: 1.0, exp: 0.95 },
  "Temps gris": { el: 40, az: 160, hor: [0.52, 0.56, 0.60], zen: [0.30, 0.34, 0.39], sun: [0.75, 0.77, 0.8], deep: [0.012, 0.04, 0.06], scat: [0.05, 0.11, 0.13], light: 1.2, hemi: 2.0, exp: 0.9 },
};
const U = { uTime: { value: 0 }, uSun: { value: new THREE.Vector3() }, uSunCol: { value: new THREE.Color() }, uHor: { value: new THREE.Color() }, uZen: { value: new THREE.Color() },
  uDeep: { value: new THREE.Color() }, uScat: { value: new THREE.Color() }, uFog: { value: 0.000085 }, uGrey: { value: 0 }, uCalm: { value: 1 }, uCov: { value: 0.52 } };
const sunLight = new THREE.DirectionalLight(0xffffff, 2.5), hemi = new THREE.HemisphereLight(0xbfd6ff, 0x1a2a38, 1);
sunLight.castShadow = true; sunLight.shadow.mapSize.set(QHIGH ? 2048 : 1024, QHIGH ? 2048 : 1024); sunLight.shadow.bias = -0.0015; sunLight.shadow.normalBias = 1.2;
{ const c = sunLight.shadow.camera; c.left = -110; c.right = 110; c.top = 110; c.bottom = -110; c.near = 10; c.far = 900; c.updateProjectionMatrix(); }
scene.add(sunLight, sunLight.target, hemi);
scene.fog = new THREE.FogExp2(0x9bbbe0, 0.000085);
let ambName = "Bleu marine";
function setAmb(name) {
  const a = AMB[name]; ambName = name; const e = a.el * D2R, z = a.az * D2R;
  U.uSun.value.set(Math.sin(z) * Math.cos(e), Math.sin(e), -Math.cos(z) * Math.cos(e));
  U.uSunCol.value.setRGB(...a.sun); U.uHor.value.setRGB(...a.hor); U.uZen.value.setRGB(...a.zen); U.uDeep.value.setRGB(...a.deep); U.uScat.value.setRGB(...a.scat);
  U.uGrey.value = name === "Temps gris" ? 1 : 0; U.uCalm.value = a.calm || 1; U.uCov.value = a.cov || 0.52;
  sunLight.color.setRGB(...a.sun); sunLight.intensity = a.light; hemi.intensity = a.hemi; hemi.color.setRGB(...a.zen).lerp(new THREE.Color(1, 1, 1), 0.55); hemi.groundColor.setRGB(...a.deep).multiplyScalar(3);
  scene.fog.color.setRGB(...a.hor); renderer.toneMappingExposure = a.exp; $("amb").textContent = name;
}

// ---------------------------------------------------------------- houle (Gerstner)
const WIND = 205 * D2R;
const WV = [[0, 170, 0.62], [22, 104, 0.40], [-28, 66, 0.27], [41, 41, 0.17], [-47, 25, 0.10]].map(([da, L, A]) => { const a = WIND + da * D2R, k = 2 * Math.PI / L; return { dx: Math.sin(a), dz: -Math.cos(a), k, A, w: Math.sqrt(9.81 * k) }; });
const DT = [[12, 15], [-63, 10.5], [75, 7.2], [-22, 4.9], [118, 3.3], [-97, 2.2], [37, 1.5]].map(([da, L]) => { const a = WIND + da * D2R, k = 2 * Math.PI / L; return { dx: Math.sin(a), dz: -Math.cos(a), k, A: L / 150, w: Math.sqrt(9.81 * k) }; });
U.uW = { value: WV.map(w => new THREE.Vector4(w.dx, w.dz, w.k, w.A)) }; U.uD = { value: DT.map(w => new THREE.Vector4(w.dx, w.dz, w.k, w.A)) };
function waveH(x, z, t) { let h = 0; for (const w of WV) h += w.A * Math.sin(w.k * (w.dx * x + w.dz * z) - w.w * t); return h * U.uCalm.value; }

const SKYFN = `
uniform vec3 uSun,uSunCol,uHor,uZen; uniform float uGrey,uTime,uCov;
float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y); }
float fbm(vec2 p){ float a=0.5,s=0.0; for(int i=0;i<5;i++){ s+=a*noise(p); p=p*2.03+17.0; a*=0.5; } return s; }
vec3 skyCol(vec3 d){ float y=max(d.y,0.0); vec3 c=mix(uHor,uZen,pow(y,0.42)); float s=max(dot(d,uSun),0.0);
  c+=uSunCol*(pow(s,10.0)*0.22+pow(s,90.0)*0.5)*(1.0-uGrey*0.85); return c; }
vec3 skyFull(vec3 d){ vec3 c=skyCol(d); if(d.y>0.0){ float sd=max(dot(d,uSun),0.0); vec2 uv=d.xz/(d.y+0.10)*1.15+vec2(uTime*0.004,0.0);
    float cl=fbm(uv)*0.78+fbm(uv*0.31+7.0)*0.34; float cov=mix(uCov,0.30,uGrey);
    float m=smoothstep(cov,cov+0.26,cl)*smoothstep(0.0,0.10,d.y); float core=smoothstep(cov+0.10,cov+0.42,cl);
    vec3 lit=mix(uHor*1.05,vec3(1.0),0.62)*(0.80+0.20*sd)+uSunCol*pow(sd,6.0)*0.2; vec3 shade=mix(uHor,vec3(0.40,0.37,0.36),0.62);
    vec3 cc=mix(lit,shade,core*0.7); cc=mix(cc,vec3(0.50,0.53,0.57),uGrey*0.7);
    c=mix(c,cc,m*mix(0.88,0.92,uGrey)); }
  return c; }`;
const waterMat = new THREE.ShaderMaterial({
  uniforms: U,
  vertexShader: `
uniform float uTime,uCalm; uniform vec4 uW[5]; varying vec3 vP; varying vec2 vB; varying float vH;
void main(){ vec4 wp=modelMatrix*vec4(position,1.0); vB=wp.xz; float dc=distance(wp.xz,cameraPosition.xz); float fade=1.0-smoothstep(780.0,1150.0,dc); float h=0.0;
  for(int i=0;i<5;i++){ vec4 w=uW[i]; float f=w.z*dot(w.xy,vB)-sqrt(9.81*w.z)*uTime; float a=w.w*fade*uCalm; wp.xz+=w.xy*a*0.55*cos(f); h+=a*sin(f);} wp.y+=h; vH=h; vP=wp.xyz;
  gl_Position=projectionMatrix*viewMatrix*wp; }`,
  fragmentShader: `
uniform float uFog,uCalm; uniform vec4 uW[5]; uniform vec4 uD[7]; uniform vec3 uDeep,uScat; varying vec3 vP; varying vec2 vB; varying float vH;
${SKYFN}
void main(){ vec3 V=cameraPosition-vP; float dist=length(V); V/=dist; vec2 g=vec2(0.0);
  for(int i=0;i<5;i++){ vec4 w=uW[i]; float f=w.z*dot(w.xy,vB)-sqrt(9.81*w.z)*uTime; float lw=6.2832/w.z; g+=w.xy*(w.w*w.z*cos(f))*clamp(1.7-dist/(lw*30.0),0.07,1.0); }
  vec2 gd=vec2(0.0);
  for(int i=0;i<7;i++){ vec4 w=uD[i]; float f=w.z*dot(w.xy,vB)-sqrt(9.81*w.z)*uTime*1.15; float lw=6.2832/w.z; gd+=w.xy*(w.w*w.z*cos(f))*clamp(1.6-dist/(lw*55.0),0.0,1.0); }
  g+=gd; g*=mix(0.55,1.0,uCalm);
  vec3 n=normalize(vec3(-g.x,1.0,-g.y));
  float F=0.02+0.98*pow(1.0-max(dot(n,V),0.0),5.0); F=clamp(F,0.0,1.0)*mix(0.70,0.92,uCalm);
  vec3 R=reflect(-V,n); R.y=abs(R.y);
  vec3 sky=skyFull(normalize(R));
  float s=max(dot(R,uSun),0.0); vec3 spec=uSunCol*(pow(s,700.0)*9.0+pow(s,70.0)*0.35)*(1.0-uGrey*0.9);
  float lit=0.35+0.65*max(dot(n,uSun),0.0);
  vec3 body=mix(uDeep,uScat,clamp(0.22+vH*0.28+g.x*0.4,0.0,1.0)*0.75)*lit;
  vec3 col=mix(body,sky,F)+spec;
  col=mix(col,uHor,1.0-exp(-dist*uFog*1.25));
  gl_FragColor=vec4(col,1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`,
});
const gNear = new THREE.PlaneGeometry(2400, 2400, QHIGH ? 240 : 150, QHIGH ? 240 : 150); gNear.rotateX(-Math.PI / 2);
const seaNear = new THREE.Mesh(gNear, waterMat); seaNear.frustumCulled = false;
const gFar = new THREE.PlaneGeometry(120000, 120000, 1, 1); gFar.rotateX(-Math.PI / 2);
const seaFar = new THREE.Mesh(gFar, waterMat); seaFar.frustumCulled = false; seaFar.position.y = -1.6;
scene.add(seaFar, seaNear);

const sky = new THREE.Mesh(new THREE.SphereGeometry(50000, 32, 16), new THREE.ShaderMaterial({
  uniforms: U, side: THREE.BackSide, depthWrite: false, fog: false,
  vertexShader: `varying vec3 vD; void main(){ vD=position; vec4 p=projectionMatrix*viewMatrix*vec4(position+cameraPosition,1.0); gl_Position=p.xyww; }`,
  fragmentShader: `
varying vec3 vD;
${SKYFN}
void main(){ vec3 d=normalize(vD); vec3 c=skyFull(d); float sd=max(dot(d,uSun),0.0);
  c+=uSunCol*smoothstep(0.99955,0.99985,sd)*14.0*(1.0-uGrey);
  gl_FragColor=vec4(c,1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`,
}));
sky.frustumCulled = false; sky.renderOrder = -10; scene.add(sky);

// ---------------------------------------------------------------- modèles
function loftHull(L, B, draft, deckFn, beamFn, stations) {
  const pos = [], col = []; const H = L / 2; const cGrey = [0.56, 0.59, 0.62], cBoot = [0.07, 0.07, 0.08], cDeck = [0.30, 0.32, 0.345];
  const sec = u => { const z = -H + u * L, b = Math.max(beamFn(u) * B / 2, 0.02), d = deckFn(u), dr = draft * (u < 0.08 ? u / 0.08 * 0.8 + 0.2 : 1);
    return [[0, -dr, z], [b * 0.55, -dr * 0.9, z], [b * 0.9, -0.4, z], [b * 0.93, 0.8, z], [b, d, z]]; };
  const tri = (a, b, c, k) => { pos.push(...a, ...b, ...c); col.push(...k, ...k, ...k); };
  for (let i = 0; i < stations; i++) {
    const s0 = sec(i / stations), s1 = sec((i + 1) / stations);
    for (const sg of [1, -1]) {
      for (let j = 0; j < 4; j++) { const k = j < 3 ? cBoot : cGrey;
        const a = [s0[j][0] * sg, s0[j][1], s0[j][2]], b = [s0[j + 1][0] * sg, s0[j + 1][1], s0[j + 1][2]], c = [s1[j][0] * sg, s1[j][1], s1[j][2]], d = [s1[j + 1][0] * sg, s1[j + 1][1], s1[j + 1][2]];
        if (sg > 0) { tri(a, c, b, k); tri(b, c, d, k); } else { tri(a, b, c, k); tri(b, d, c, k); } }
    }
    const a = [-s0[4][0], s0[4][1], s0[4][2]], b = [s0[4][0], s0[4][1], s0[4][2]], c = [-s1[4][0], s1[4][1], s1[4][2]], d = [s1[4][0], s1[4][1], s1[4][2]];
    tri(a, c, b, cDeck); tri(b, c, d, cDeck);
  }
  const s = sec(1); for (let j = 0; j < 4; j++) { const k = j < 2 ? cBoot : cGrey;   // tableau arrière
    tri([s[j][0], s[j][1], H], [s[j + 1][0], s[j + 1][1], H], [-s[j][0], s[j][1], H], k); tri([s[j + 1][0], s[j + 1][1], H], [-s[j + 1][0], s[j + 1][1], H], [-s[j][0], s[j][1], H], k); }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3)); g.computeVertexNormals(); return g;
}
// bloc à flancs inclinés (superstructure furtive) : base (w0,l0), sommet (w1,l1), hauteur h, décalage du sommet dz
function block(w0, l0, w1, l1, h, dz = 0) {
  const g = new THREE.BoxGeometry(1, 1, 1), p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const top = p.getY(i) > 0; p.setXYZ(i, p.getX(i) * (top ? w1 : w0), top ? h : 0, p.getZ(i) * (top ? l1 : l0) + (top ? dz : 0)); }
  g.computeVertexNormals(); return g;
}
const M = {
  hull: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.78, metalness: 0.08, side: THREE.DoubleSide, shadowSide: THREE.DoubleSide }),
  sup: new THREE.MeshStandardMaterial({ color: 0x9da6ad, roughness: 0.74, metalness: 0.08 }),
  dark: new THREE.MeshStandardMaterial({ color: 0x23272c, roughness: 0.6, metalness: 0.2 }),
  glass: new THREE.MeshStandardMaterial({ color: 0x0b1420, roughness: 0.25, metalness: 0.6 }),
  mark: new THREE.MeshStandardMaterial({ color: 0xd9dde0, roughness: 0.9 }),
  radome: new THREE.MeshStandardMaterial({ color: 0xc9ced2, roughness: 0.6 }),
  cHull: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, metalness: 0.05, side: THREE.DoubleSide }),
  cSup: new THREE.MeshStandardMaterial({ color: 0x55595d, roughness: 0.85 }),
};
function add(g, geo, mat, x, y, z) { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; g.add(m); return m; }
function buildFrigate() {            // frégate type FREMM, 142 m, étrave vers -Z
  const g = new THREE.Group(), deck = u => 6.4 + 3.2 * Math.pow(Math.max(0, 1 - u / 0.3), 2);
  const beam = u => Math.min(1, Math.pow(u / 0.42, 0.62)) * (u > 0.82 ? 1 - 0.16 * (u - 0.82) / 0.18 : 1);
  { const hm = new THREE.Mesh(loftHull(142, 19.6, 5.2, deck, beam, 48), M.hull); hm.castShadow = hm.receiveShadow = true; g.add(hm); }
  const tur = add(g, block(5.4, 6.4, 3.6, 4.2, 3.2), M.sup, 0, 7.2, -45); add(g, new THREE.CylinderGeometry(0.28, 0.34, 9, 10).rotateX(Math.PI / 2), M.dark, 0, 9.2, -51);
  add(g, block(9.5, 11, 9.0, 10.4, 1.5), M.sup, 0, 6.9, -33);                                   // lanceurs verticaux
  add(g, block(17.4, 30, 13.4, 25, 8.2, 1.5), M.sup, 0, 6.4, -12);                              // bloc passerelle
  add(g, block(13.7, 0.4, 12.6, 0.4, 1.5), M.glass, 0, 12.2, -24.4);                            // vitres passerelle
  add(g, block(11.6, 9, 9.4, 7, 3.4, 0.6), M.sup, 0, 14.6, -13.5);
  add(g, block(5.2, 5.2, 1.5, 1.5, 14.5), M.sup, 0, 18.0, -12);                                 // mât principal
  add(g, new THREE.SphereGeometry(2.0, 18, 12), M.radome, 0, 33.6, -12);
  const radar = add(g, new THREE.BoxGeometry(5.6, 2.0, 0.35), M.dark, 0, 29.4, -12); radar.userData.spin = 1;
  add(g, block(12.4, 13, 9.4, 9.5, 7.4, 0.8), M.sup, 0, 6.4, 13);                               // bloc cheminée
  add(g, block(5.6, 6.2, 4.4, 4.8, 4.8, 1.0), M.dark, 0, 13.8, 14.5);
  add(g, block(2.6, 2.6, 0.9, 0.9, 9.5), M.sup, 0, 13.8, 6.5);                                  // mât arrière
  add(g, new THREE.SphereGeometry(1.5, 14, 10), M.radome, 0, 23.4, 6.5);
  add(g, block(16.6, 20, 14.2, 18.4, 7.0, -0.4), M.sup, 0, 6.4, 34);                            // hangar
  add(g, block(9.6, 0.3, 9.2, 0.3, 5.2), M.dark, 0, 6.6, 44.1);                                 // porte de hangar
  const ring = add(g, new THREE.RingGeometry(5.3, 5.9, 40).rotateX(-Math.PI / 2), M.mark, 0, 6.47, 56);
  add(g, new THREE.BoxGeometry(0.6, 0.02, 5.2), M.mark, -1.7, 6.47, 56); add(g, new THREE.BoxGeometry(0.6, 0.02, 5.2), M.mark, 1.7, 6.47, 56); add(g, new THREE.BoxGeometry(3.4, 0.02, 0.6), M.mark, 0, 6.47, 56);
  for (const sx of [-1, 1]) add(g, block(1.6, 4.6, 1.2, 3.6, 1.6), M.sup, sx * 6.2, 14.6, 1);   // lance-leurres
  g.userData.radar = radar; g.userData.len = 142; g.userData.B = 19.6; g.userData.beam = beam; g.userData.top = 40; g.userData.bridge = [21, 21.5]; return g;
}
function buildContact() {            // bâtiment de surface générique, 96 m
  const g = new THREE.Group(), deck = u => 5.0 + 2.6 * Math.pow(Math.max(0, 1 - u / 0.25), 2), beam = u => Math.min(1, Math.pow(u / 0.35, 0.6)) * (u > 0.85 ? 1 - 0.2 * (u - 0.85) / 0.15 : 1);
  const hg = loftHull(96, 14.5, 4.4, deck, beam, 36), c = hg.attributes.color; for (let i = 0; i < c.count; i++) if (c.getX(i) > 0.4) c.setXYZ(i, 0.2, 0.21, 0.22);
  g.add(new THREE.Mesh(hg, M.cHull));
  add(g, block(11.5, 22, 9.2, 18, 7, 1), M.cSup, 0, 5.0, -4); add(g, block(9.4, 0.4, 8.8, 0.4, 1.3), M.glass, 0, 9.9, -13.6);
  add(g, block(3.6, 3.6, 1, 1, 11), M.cSup, 0, 12, -3); add(g, block(4.4, 5, 3.4, 4, 4), M.dark, 0, 12, 6);
  add(g, block(4, 4.6, 2.8, 3.2, 2.4), M.cSup, 0, 5.6, -28); add(g, new THREE.CylinderGeometry(0.2, 0.24, 6, 8).rotateX(Math.PI / 2), M.dark, 0, 7.2, -32);
  g.userData.len = 96; g.userData.B = 14.5; g.userData.beam = beam; g.userData.top = 30; g.userData.bridge = [8, 13]; return g;
}
// modèles 3D détaillés (glb allégés) ; le modèle géométrique sert de secours tant qu'ils ne sont pas chargés
const MODELS = { ship: { url: "/static/models/lowell_" + (QHIGH ? "lite" : "lod") + ".glb", len: 172, flip: false, tint: 1, wl: 0.22 }, contact: { url: "/static/models/hawaii_" + (QHIGH ? "lite" : "lod") + ".glb", len: 165, flip: true, tint: 0.8, wl: 0.22 } }, TPL = {};
const genBeam = u => Math.min(1, Math.pow(u / 0.4, 0.6)) * (u > 0.85 ? 1 - 0.15 * (u - 0.85) / 0.15 : 1);
function loadModel(kind) {
  const c = MODELS[kind];
  new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(c.url, gltf => {
    const root = gltf.scene; root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root, true), size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3()), alongX = size.x > size.z, long = Math.max(size.x, size.z), short = Math.min(size.x, size.z);
    const mats = new Set(), wl = box.min.y + size.y * c.wl;      // ligne de flottaison : fraction de la hauteur, réglée par modèle
    root.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; mats.add(o.material); } });
    for (const m of mats) { m.metalness = Math.min(m.metalness, 0.15); m.roughness = Math.max(m.roughness, 0.62); { const hsl = {}; m.color.getHSL(hsl); if (hsl.l < 0.16) m.color.setHSL(hsl.h, hsl.s, 0.16); } m.color.multiplyScalar(c.tint); m.side = THREE.DoubleSide; }
    root.position.x -= ctr.x; root.position.y -= wl; root.position.z -= ctr.z;
    const k = c.len / long, w = new THREE.Group(); w.add(root); w.scale.setScalar(k); w.rotation.y = (alongX ? Math.PI / 2 : 0) + (c.flip ? Math.PI : 0);
    TPL[kind] = { obj: w, len: c.len, B: short * k, top: (box.max.y - wl) * k + 8 };
    for (const e of ENT.values()) if (e.kind === kind) swapModel(e);
  }, undefined, err => console.warn("Modèle 3D indisponible, modèle simplifié conservé :", c.url, err));
}
function fromTpl(kind) { const t = TPL[kind], g = new THREE.Group(); g.add(t.obj.clone()); g.userData = { len: t.len, B: t.B, beam: genBeam, top: t.top, bridge: [t.len * 0.17, t.top * 0.62] }; return g; }
function swapModel(e) { const g = fromTpl(e.kind); g.position.copy(e.g.position); g.rotation.copy(e.g.rotation); scene.remove(e.g); scene.remove(e.foam); e.g = g; scene.add(g); e.foam = makeFoam(g.userData.len, g.userData.B, g.userData.beam); }
// sillage : ruban de particules d'écume
const wakeMat = new THREE.ShaderMaterial({ uniforms: U, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  vertexShader: `attribute vec4 aCol; varying vec4 vC; varying vec3 vP; void main(){ vC=aCol; vec4 wp=modelMatrix*vec4(position,1.0); vP=wp.xyz; gl_Position=projectionMatrix*viewMatrix*wp; }`,
  fragmentShader: `
uniform float uTime,uFog; uniform vec3 uHor,uSunCol,uZen; varying vec4 vC; varying vec3 vP;
float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y); }
void main(){ float dist=distance(cameraPosition,vP); vec2 q=vP.xz; float n=noise(q*0.09+uTime*0.05)*0.55+noise(q*0.31-uTime*0.11)*0.3+noise(q*0.9)*0.15;
  float near=1.0-smoothstep(300.0,1500.0,dist); float a=vC.a*mix(0.75,smoothstep(0.30,0.72,n+vC.a*0.35),near);
  vec3 c=mix(uZen*0.6+uHor*0.5,vec3(1.0),0.78)*(0.55+0.45*uSunCol); c=mix(c,uHor,1.0-exp(-dist*uFog*1.25));
  gl_FragColor=vec4(c,a);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}` });
const NW = 150;
function makeFoam(len, B, beamFn) {
  const P = [], C = [], I = [], N = 28, H = len / 2;
  for (const sg of [1, -1]) { const base = P.length / 3;
    for (let i = 0; i <= N; i++) { const u = i / N, z = -H - 3 + u * (len + 4), b = Math.max(beamFn(Math.min(1, u * 1.02)) * B / 2 * 0.86, 0.3), o = b + 2.5 + 7 * u, a = (0.35 + 0.5 * Math.sin(Math.min(1, u * 3) * Math.PI / 2)) * (i === 0 ? 0.5 : 1);
      P.push(sg * b, 0, z, sg * o, 0, z); C.push(1, 1, 1, a, 1, 1, 1, 0); if (i < N) { const k = base + i * 2; I.push(k, k + 2, k + 1, k + 1, k + 2, k + 3); } } }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3)); g.setAttribute("aCol", new THREE.Float32BufferAttribute(C, 4)); g.setIndex(I);
  const mt = wakeMat.clone(); mt.uniforms = U; mt.side = THREE.DoubleSide; const m = new THREE.Mesh(g, mt); m.frustumCulled = false; m.renderOrder = 2; scene.add(m); return m; }
function makeWake() { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(NW * 4 * 3), 3)); g.setAttribute("aCol", new THREE.BufferAttribute(new Float32Array(NW * 4 * 4), 4));
  const idx = []; for (let i = 0; i < NW - 1; i++) for (let r = 0; r < 3; r++) { const a = (i * 4) + r, b = a + 4; idx.push(a, b, a + 1, a + 1, b, b + 1); }
  g.setIndex(idx); const m = new THREE.Mesh(g, wakeMat); m.frustumCulled = false; m.renderOrder = 2; scene.add(m); return m; }

// ---------------------------------------------------------------- entités
const ENT = new Map(); let S = null, focus = null, mode = "orbit", showTags = true, tRecv = 0;
function entity(id, kind) {
  let e = ENT.get(id); if (e) return e;
  const g = TPL[kind] ? fromTpl(kind) : kind === "ship" ? buildFrigate() : buildContact(); scene.add(g);
  const tag = document.createElement("div"); tag.className = "tag"; tag.innerHTML = "<span><b></b><small></small></span><i></i>"; tag.onclick = () => setFocus(id); $("tags").appendChild(tag);
  e = { id, kind, g, tag, foam: makeFoam(g.userData.len, g.userData.B, g.userData.beam), wake: makeWake(), trail: [], x: null, z: 0, hdg: 0, sog: 0, tx: 0, tz: 0, thdg: 0, d: {} }; ENT.set(id, e); return e;
}
function drop(id) { const e = ENT.get(id); if (!e) return; scene.remove(e.g); scene.remove(e.wake); scene.remove(e.foam); e.wake.geometry.dispose(); e.tag.remove(); ENT.delete(id); }
function ingest(s) {
  S = s; tRecv = performance.now() / 1000; if (!s.ships) return;
  const seen = new Set();
  for (const sh of s.ships) { seen.add(sh.name); const e = entity(sh.name, "ship"); e.d = sh; e.tx = sh.x; e.tz = -sh.y; e.thdg = sh.hdg; e.sog = sh.sog; if (e.x === null) { e.x = e.tx; e.z = e.tz; e.hdg = e.thdg; } }
  for (const c of s.contacts || []) { seen.add(c.id); const e = entity(c.id, "contact"); e.d = c; e.tx = c.x; e.tz = -c.y; e.thdg = c.cap; e.sog = c.vit * KN; if (e.x === null) { e.x = e.tx; e.z = e.tz; e.hdg = e.thdg; } }
  for (const id of [...ENT.keys()]) if (!seen.has(id)) drop(id);
  if (!focus || !ENT.has(focus)) setFocus(s.player && ENT.has(s.player) ? s.player : s.ships[0] && s.ships[0].name);
  hud();
}
function setFocus(id) { if (!id || !ENT.has(id)) return; focus = id; const e = ENT.get(id); if (e.x !== null && mode === "orbit") { /* la cible glisse dans la boucle */ } hud(); }

// ---------------------------------------------------------------- HUD
function hud() {
  if (!S || !S.ships) return;
  $("sc").textContent = (S.demo ? "Démonstration · " : "") + (S.titre || "Vue 3D"); if (S.ended) { if (window._tEnd == null) window._tEnd = S.t || 0; } else window._tEnd = null;
  $("clock").textContent = (S.ended ? "Terminé · " + mmss(window._tEnd) : mmss(S.t || 0) + (S.duree ? " / " + mmss(S.duree) : ""));
  const e = ENT.get(focus);
  if (e) { const d = e.d, ship = e.kind === "ship";
    $("in").textContent = e.id.toUpperCase() + (e.id === S.guide ? " ★" : ""); $("ir").textContent = ship ? (e.id === S.player ? "Votre navire · " : "") + (d.role === "guide" ? "Guide de la formation" : "Escorte") : d.type + " · " + d.cls;
    const rows = ship ? [["Cap", p3(d.hdg) + "°"], ["Vitesse", (d.sog / KN).toFixed(1).replace(".", ",") + " kn"], ["État", d.etat || "—"], ["Formation", { column: "Colonne", line_abreast: "Ligne de front", screen: "Écran" }[S.form] || "—"]]
      : [["Cap", p3(d.cap) + "°"], ["Vitesse", d.vit + " kn"], ["Distance", d.range_nm == null ? "—" : d.range_nm.toFixed(1).replace(".", ",") + " NM"], ["Relèvement", d.brg == null ? "—" : p3(d.brg) + "°"], ["CPA", d.cpa_nm == null ? "—" : d.cpa_nm.toFixed(1).replace(".", ",") + " NM"]];
    $("id").innerHTML = rows.map(r => `<dt>${r[0]}</dt><dd>${r[1]}</dd>`).join(""); }
  const pills = S.ships.map(s => `<button class="pill ${s.name === focus ? "on" : ""} ${s.name === S.player ? "me" : ""}" data-n="${s.name}"><b>${s.name.toUpperCase()}${s.name === S.guide ? " ★" : ""}</b><small>${p3(s.hdg)}° · ${Math.round(s.sog / KN)} kn</small></button>`)
    .concat((S.contacts || []).map(c => `<button class="pill ${c.cls} ${c.id === focus ? "on" : ""}" data-n="${c.id}"><b>${c.id}</b><small>${c.cls} · ${c.range_nm == null ? "—" : c.range_nm.toFixed(1).replace(".", ",") + " NM"}</small></button>`)).join("");
  const st = S.demo ? "Aucun scénario en cours · démonstration" : S.ended ? "Scénario terminé" : "En direct";
  const html = pills + `<div class="glass" id="state">${st}<br><span style="font-size:10.5px">Modèles 3D : Pippa (Sketchfab), CC BY 4.0</span></div>`; const bar = $("bar"); if (bar.__h !== html) { bar.__h = html; bar.innerHTML = html; bar.querySelectorAll(".pill").forEach(b => b.onclick = () => setFocus(b.dataset.n)); }
  const m = (S.msgs || []).filter(m => ["ordre", "urgence", "joueur"].includes(m.kind)).slice(-1)[0], r = $("radio");
  if (m && S.t - m.t < 45) { r.style.display = "block"; $("rh").textContent = `${mmss(m.t)} · ${m.from} → ${m.to} · VHF`; $("ren").textContent = "« " + m.en + " »"; $("rfr").textContent = m.fr || ""; r.style.borderColor = m.kind === "urgence" ? "#7a5a1c" : "#23344f"; }
  else r.style.display = "none";
}
const tp = $("tp").getContext("2d");
function tape(brg) {
  tp.clearRect(0, 0, 760, 60); tp.textAlign = "center"; tp.font = "600 20px Segoe UI, sans-serif";
  for (let a = Math.floor((brg - 50) / 5) * 5; a <= brg + 50; a += 5) { const x = 380 + (a - brg) * 7.2, aa = ((a % 360) + 360) % 360, big = aa % 30 === 0; tp.fillStyle = big ? "#dfe9f7" : "#5f7598";
    tp.fillRect(x - 1, 46, 2, big ? 14 : 8); if (big) tp.fillText({ 0: "N", 90: "E", 180: "S", 270: "O" }[aa] || String(aa).padStart(3, "0"), x, 38); }
  tp.fillStyle = "#4aa3ff"; tp.beginPath(); tp.moveTo(380, 44); tp.lineTo(373, 30); tp.lineTo(387, 30); tp.closePath(); tp.fill();
  tp.fillStyle = "#4aa3ff"; tp.font = "600 17px Consolas, monospace"; tp.fillText(p3(((brg % 360) + 360) % 360) + "°", 380, 17);
}

// ---------------------------------------------------------------- caméras
function setMode(m) {
  mode = m; document.querySelectorAll("[data-cam]").forEach(b => b.classList.toggle("on", b.dataset.cam === m)); controls.enabled = m === "orbit" || m === "fleet";
  camera.up.set(0, 1, 0); camera.fov = m === "bridge" ? 62 : 42; camera.updateProjectionMatrix();
  const off = camera.position.clone().sub(controls.target); if (off.y < 20) off.y = 60; off.setLength(m === "fleet" ? 1500 : 420); if (m === "fleet") off.y = Math.max(off.y, 420);
  if (controls.enabled) camera.position.copy(controls.target).add(off);
}
const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), v3 = new THREE.Vector3();
function fleetCenter(out) { let n = 0; out.set(0, 0, 0); for (const e of ENT.values()) if (e.kind === "ship" && e.x !== null) { out.x += e.x; out.z += e.z; n++; } if (n) out.multiplyScalar(1 / n); return n; }
function cam(dt) {
  const e = ENT.get(focus); if (!e || e.x === null) { controls.update(); return; }
  const h = e.hdg * D2R, fx = Math.sin(h), fz = -Math.cos(h), k = 1 - Math.exp(-dt * 3.5);
  if (mode === "orbit" || mode === "fleet") {
    if (mode === "fleet") fleetCenter(v1); else v1.set(e.x, 12, e.z);
    v2.copy(v1).sub(controls.target); const jump = v2.length() > 4000; if (!jump) v2.multiplyScalar(Math.min(1, dt * 4 + (v2.length() < 30 ? 1 : 0)));
    controls.target.add(v2); camera.position.add(v2); controls.update();
  } else if (mode === "chase") {
    v1.set(e.x - fx * 330, 78, e.z - fz * 330); camera.position.lerp(v1, k); v2.set(e.x + fx * 160, 14, e.z + fz * 160); controls.target.lerp(v2, k * 1.4); camera.lookAt(controls.target);
  } else if (mode === "bridge") {
    const br = e.g.userData.bridge, y = e.g.position.y + br[1]; camera.position.set(e.x + fx * br[0], y, e.z + fz * br[0]); v2.set(e.x + fx * 600, y - 22, e.z + fz * 600); controls.target.copy(v2); camera.lookAt(v2);
  } else if (mode === "top") {
    fleetCenter(v1); let r = 500; for (const o of ENT.values()) if (o.x !== null && o.kind === "ship") r = Math.max(r, Math.hypot(o.x - v1.x, o.z - v1.z)); const H = Math.min(9000, r * 2.7 + 1300);
    v2.set(v1.x, H, v1.z + 1); camera.position.lerp(v2, k); camera.up.set(0, 0, -1); controls.target.set(v1.x, 0, v1.z); camera.lookAt(camera.position.x, 0, camera.position.z - 1);
  }
}

// ---------------------------------------------------------------- boucle
let last = performance.now() / 1000, T = 0, slow = 0, fN = 0, fT = 0, fL = performance.now() / 1000, FPS = 60, qStep = 0, statEl = null;
if (QSTATS) { statEl = document.createElement("div"); statEl.id = "perf"; statEl.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:50;font:12px ui-monospace,Consolas,monospace;color:#cfe3f5;background:rgba(6,14,24,.75);padding:4px 8px;border-radius:4px;pointer-events:none"; document.body.appendChild(statEl); }
function frame() {
  requestAnimationFrame(frame);
  const now = performance.now() / 1000, dt = Math.min(0.1, now - last); last = now; T += dt; U.uTime.value = T;
  // qualité adaptative : moyenne sur 1 s ; deux secondes de suite sous 32 images/s => un cran de moins
  fN++; fT += now - fL; fL = now;
  if (fT >= 1) { FPS = fN / fT; fN = 0; fT = 0;
    if (!QHIGH && document.visibilityState === "visible") { if (FPS < 32) { if (++slow >= 2) { slow = 0; qStep++;
        if (PR > 1) { PR = 1; renderer.setPixelRatio(1); resize(); }
        else if (renderer.shadowMap.enabled) { renderer.shadowMap.enabled = false; scene.traverse(o => { if (o.material) o.material.needsUpdate = true; }); }
        else if (PR > 0.75) { PR = 0.75; renderer.setPixelRatio(PR); resize(); } } } else slow = 0; }
    if (statEl) { const ri = renderer.info.render; statEl.textContent = FPS.toFixed(0) + " img/s · " + Math.round(ri.triangles / 1000) + " k tri · " + ri.calls + " appels · PR " + PR + " · ombres " + (renderer.shadowMap.enabled ? "oui" : "non"); }
    window._perf = { fps: FPS, tri: renderer.info.render.triangles, calls: renderer.info.render.calls, pr: PR, shadows: renderer.shadowMap.enabled, step: qStep }; }
  const live = S && !S.ended ? Math.min(1.5, now - tRecv) : 0, k = 1 - Math.exp(-dt * 3);
  for (const e of ENT.values()) {
    if (e.x === null) continue;
    const th = e.thdg * D2R, gx = e.tx + Math.sin(th) * e.sog * live, gz = e.tz - Math.cos(th) * e.sog * live;
    if (Math.hypot(gx - e.x, gz - e.z) > 400) { e.x = gx; e.z = gz; e.trail.length = 0; } else { e.x += (gx - e.x) * k; e.z += (gz - e.z) * k; }
    e.hdg += ((((e.thdg - e.hdg) % 360) + 540) % 360 - 180) * k;
    const h = e.hdg * D2R, fx = Math.sin(h), fz = -Math.cos(h), L = e.g.userData.len * 0.36, Bm = 7;
    const hb = waveH(e.x + fx * L, e.z + fz * L, T), hs = waveH(e.x - fx * L, e.z - fz * L, T), hp = waveH(e.x - fz * Bm, e.z + fx * Bm, T), hq = waveH(e.x + fz * Bm, e.z - fx * Bm, T);
    e.g.position.set(e.x, (hb + hs + hp + hq) / 4 * 0.45, e.z); e.g.rotation.order = "YXZ"; e.g.rotation.set(Math.atan2(hb - hs, 2 * L) * 0.55, -h, Math.atan2(hq - hp, 2 * Bm) * 0.3);
    if (e.g.userData.radar) e.g.userData.radar.rotation.y = T * 2.4;
    e.foam.position.set(e.x, e.g.position.y * 0.6 + 0.45, e.z); e.foam.rotation.y = -h; e.foam.visible = e.sog > 1.5;
    // sillage
    const sx = e.x - fx * e.g.userData.len * 0.47, sz = e.z - fz * e.g.userData.len * 0.47, t0 = e.trail[0];
    if (!t0 || Math.hypot(t0[0] - sx, t0[1] - sz) > 7) { e.trail.unshift([sx, sz, T]); if (e.trail.length > NW - 1) e.trail.pop(); }
    const P = e.wake.geometry.attributes.position.array, C = e.wake.geometry.attributes.aCol.array, pts = [[sx, sz, T], ...e.trail], n = pts.length, sp = Math.min(1, e.sog / 4);
    for (let i = 0; i < NW; i++) {
      const p = pts[Math.min(i, n - 1)], q = pts[Math.min(i + 1, n - 1)], r = pts[Math.max(Math.min(i, n - 1) - 1, 0)]; let dx = r[0] - q[0], dz = r[1] - q[1]; const m = Math.hypot(dx, dz) || 1; dx /= m; dz /= m;
      const a = i >= n ? 1 : i / (NW - 1), w1 = 4.5 + 9 * Math.pow(a, 0.6), w2 = 9 + 46 * Math.pow(a, 0.85), al = i >= n ? 0 : sp * Math.min(1, i / 2);
      const y = waveH(p[0], p[1], T) * (Math.hypot(p[0] - camera.position.x, p[1] - camera.position.z) < 1000 ? 1 : 0.3) + 0.35, o = i * 12, c = i * 16;
      const xs = [-w2, -w1, w1, w2], as = [0, 0.9 * Math.pow(1 - a, 2.2) * al, 0.9 * Math.pow(1 - a, 2.2) * al, 0];
      for (let j = 0; j < 4; j++) { P[o + j * 3] = p[0] - dz * xs[j]; P[o + j * 3 + 1] = y; P[o + j * 3 + 2] = p[1] + dx * xs[j]; C[c + j * 4] = 0.93; C[c + j * 4 + 1] = 0.97; C[c + j * 4 + 2] = 1; C[c + j * 4 + 3] = as[j]; }
    }
    e.wake.geometry.attributes.position.needsUpdate = true; e.wake.geometry.attributes.aCol.needsUpdate = true;
  }
  cam(dt);
  { const fd = mode === "top" ? 0.000018 : (AMB[ambName].fog || 0.000085); U.uFog.value += (fd - U.uFog.value) * Math.min(1, dt * 3); scene.fog.density = U.uFog.value; }
  seaNear.position.set(Math.round(camera.position.x / 10) * 10, 0, Math.round(camera.position.z / 10) * 10); seaFar.position.set(camera.position.x, -1.6, camera.position.z);
  { const f = ENT.get(focus); if (f && f.x !== null) v1.set(f.x, 8, f.z); else v1.copy(camera.position); sunLight.position.copy(v1).addScaledVector(U.uSun.value, 450); sunLight.target.position.copy(v1); }
  renderer.render(scene, camera);
  // étiquettes
  camera.getWorldDirection(v3); tape(Math.atan2(v3.x, -v3.z) / D2R);
  for (const e of ENT.values()) {
    if (e.x === null) continue; const t = e.tag; v1.set(e.x, e.g.position.y + e.g.userData.top, e.z); const dist = v1.distanceTo(camera.position); v1.project(camera);
    const vis = showTags && v1.z < 1 && Math.abs(v1.x) < 1.05 && Math.abs(v1.y) < 1.1 && !(mode === "bridge" && e.id === focus);
    if (!vis) { t.style.display = "none"; continue; }
    t.style.display = ""; t.style.left = ((v1.x + 1) / 2 * innerWidth).toFixed(1) + "px"; t.style.top = ((1 - v1.y) / 2 * innerHeight).toFixed(1) + "px";
    const d = e.d, cls = "tag " + (e.kind === "ship" ? (S && e.id === S.player ? "me" : "") : d.cls) + (e.id === focus ? " sel" : ""); if (t.className !== cls) t.className = cls;
    const a = e.kind === "ship" ? e.id.toUpperCase() + (S && e.id === S.guide ? " ★" : "") : e.id + " · " + d.cls, b = (e.kind === "ship" ? p3(d.hdg) + "° · " + Math.round(d.sog / KN) + " kn" : p3(d.cap) + "° · " + d.vit + " kn") + (e.kind !== "ship" && d.range_nm != null ? " · " + d.range_nm.toFixed(1).replace(".", ",") + " NM" : "");
    if (t.__a !== a) { t.__a = a; t.children[0].children[0].textContent = a; } if (t.__b !== b) { t.__b = b; t.children[0].children[1].textContent = b; }
  }
}

// ---------------------------------------------------------------- données
function demoState(t) {
  const cap = 20 + 25 * Math.sin(t / 45), h = cap * D2R, v = 12 * KN, gx = Math.sin(20 * D2R) * v * t + 180 * (1 - Math.cos(t / 45)), gy = Math.cos(20 * D2R) * v * t;
  const names = ["hannibal", "alfa", "charlie", "delta"], ships = names.map((n, i) => ({ name: n, x: gx - Math.sin(h) * 420 * i, y: gy - Math.cos(h) * 420 * i, hdg: cap, sog: v, role: i ? "escorte" : "guide", etat: i ? "En station" : "Guide" }));
  const c = { id: "TRK021", type: "Surface", cls: "hostile", cap: 235, vit: 16, x: 3900 - Math.sin(55 * D2R) * 16 * KN * t, y: 3300 - Math.cos(55 * D2R) * 16 * KN * t };
  const r = Math.hypot(c.x - ships[1].x, c.y - ships[1].y); c.range_nm = r / NM; c.brg = (Math.atan2(c.x - ships[1].x, c.y - ships[1].y) / D2R + 360) % 360; c.cpa_nm = 0.8;
  return { demo: true, phase: "running", titre: "Transit en colonne", t, player: "alfa", guide: "hannibal", form: "column", ships, contacts: [c],
    msgs: [{ t: Math.max(0, t - 8), from: "HANNIBAL", to: "TOUS", kind: "ordre", en: "ALL SHIPS THIS IS HANNIBAL CORPEN 020 SPEED 12 OVER", fr: "À tous les navires : faire route au 020°, vitesse 12 nœuds" }] };
}
let liveOK = false, demoT0 = performance.now() / 1000;
// flux direct : SSE, et repli automatique sur des requêtes répétées si le flux ne passe pas (certains tunnels le bloquent)
function liveFeed(on, down) {
  let last = 0, poll = false; const es = new EventSource("/events");
  es.onmessage = m => { last = Date.now(); let d; try { d = JSON.parse(m.data); } catch (_) { return; } on(d); };
  es.onerror = () => { if (!poll && down) down(); };
  async function loop() { for (;;) { try { const r = await fetch("/api/state", { cache: "no-store" }); on(await r.json()); } catch (_) { if (down) down(); } await new Promise(r => setTimeout(r, 300)); } }
  setTimeout(function chk() { if (Date.now() - last > 3000) { poll = true; es.close(); loop(); } else setTimeout(chk, 2000); }, 3000);
}
function connect() {
  if (DEMO) return;
  liveFeed(d => { liveOK = d.phase === "running" && !!d.ships && d.ships.length > 0; if (liveOK) ingest(d); }, () => { liveOK = false; });
}
setInterval(() => { if (!liveOK) ingest(demoState(performance.now() / 1000 - demoT0)); }, 250);

// ---------------------------------------------------------------- commandes
document.querySelectorAll("[data-cam]").forEach(b => b.onclick = () => setMode(b.dataset.cam));
$("amb").onclick = () => { const k = Object.keys(AMB); setAmb(k[(k.indexOf(ambName) + 1) % k.length]); };
$("lab").onclick = () => { showTags = !showTags; $("lab").classList.toggle("on", showTags); };
$("full").onclick = () => { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); };
$("cons").onclick = () => { location.href = "/console"; };
addEventListener("keydown", e => { const k = e.key.toLowerCase(), cams = ["orbit", "chase", "bridge", "fleet", "top"];
  if (k >= "1" && k <= "5") setMode(cams[+k - 1]); else if (k === "f") $("full").click(); else if (k === "l") $("lab").click(); else if (k === "h") document.body.classList.toggle("clean");
  else if (k === "tab") { e.preventDefault(); const ids = [...ENT.keys()]; setFocus(ids[(ids.indexOf(focus) + 1) % ids.length]); } });
$("lab").classList.add("on"); setAmb("Bleu marine"); ingest(demoState(0));
{ const e = ENT.get(focus); if (e) { controls.target.set(e.x, 12, e.z); camera.position.set(e.x - 300, 85, e.z + 290); } }
loadModel("ship"); loadModel("contact"); connect(); frame();
window.__h3d = { setMode, setAmb, setFocus, ENT, camera, controls, TPL };

// ---------------------------------------------------------------- barre manuelle (touches fleches)
{ const hk = { l: false, r: false }; let lastR = 0, camSet = false;
  const el = document.createElement("div"); el.className = "hud glass"; el.id = "helm3d";
  el.style.cssText = "position:fixed;left:50%;transform:translateX(-50%);top:84px;padding:8px 14px;font:600 14px Consolas,monospace;display:none;z-index:5;text-align:center;white-space:nowrap";
  document.body.appendChild(el);
  const send = b => fetch("/api/helm", { method: "POST", body: JSON.stringify(b) }).catch(() => {});
  const rud = () => { const r = hk.l && !hk.r ? -1 : hk.r && !hk.l ? 1 : 0; if (r !== lastR) { lastR = r; send({ rudder: r }); } };
  addEventListener("keydown", e => { if (!S || !S.manual) return;
    if (e.key === "ArrowLeft") { hk.l = true; rud(); e.preventDefault(); } else if (e.key === "ArrowRight") { hk.r = true; rud(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { send({ dkn: 1 }); e.preventDefault(); } else if (e.key === "ArrowDown") { send({ dkn: -1 }); e.preventDefault(); } });
  addEventListener("keyup", e => { if (e.key === "ArrowLeft") { hk.l = false; rud(); } else if (e.key === "ArrowRight") { hk.r = false; rud(); } });
  addEventListener("blur", () => { hk.l = hk.r = false; rud(); });
  setInterval(() => { if (!S || !S.manual || !S.ships || !S.helm) { el.style.display = "none"; return; }
    const me = S.ships.find(s => s.name === S.player); if (!me) return; el.style.display = "block";
    if (!camSet) { camSet = true; setFocus(S.player); setMode("chase"); }
    const f3 = n => String(Math.round(n) % 360).padStart(3, "0");
    el.innerHTML = `BARRE ${S.helm.rudder < 0 ? "◀ BÂBORD" : S.helm.rudder > 0 ? "TRIBORD ▶" : "au milieu"} · cap ${f3(me.hdg)}° (ordonné ${f3(S.helm.cap)}°) · ${Math.round(me.sog / 0.514444)} kn (ordonné ${Math.round(S.helm.kn)})`
      + (S.station ? ` · poste à ${S.station.err} m` : "") + `<div style="font:500 11px Segoe UI,sans-serif;color:#8196b8;margin-top:3px">← → barre (maintenir) · ↑ ↓ vitesse · 2 poursuite · 3 passerelle</div>`; }, 200);
}
