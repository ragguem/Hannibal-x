#!/usr/bin/env python3
"""Hannibal : serveur de simulation (controleur de flotte + moteur de scenario + API web)."""
import os, sys, json, math, time, threading, glob, socket, http.client, http.server, urllib.parse, signal, traceback
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from geographic_msgs.msg import GeoPoint
from geometry_msgs.msg import Pose
from lotusim_msgs.msg import VesselPositionArray, MASCmd as MASCmdMsg
from lotusim_msgs.action import MASCmdArray
from lotusim_msgs.srv import SetWaypoints
import mtp, sim, reco, hxbridge

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.environ.get("WORLD", "defenseScenario")
PORT = int(os.environ.get("PORT", "8771"))
ENGINE = os.environ.get("ENGINE_CONTAINER", "lotusim")
RELAY = os.environ.get("RELAY_CONTAINER", "hannibal-relay")
RELAY_IMAGE = os.environ.get("RELAY_IMAGE", "hannibal-jazzy")
YAW_OFFSET = os.environ.get("YAW_OFFSET_DEG", "90")
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "8781"))
try: PUBLIC_PASSWORD = open(os.path.join(HERE, "public_password.txt"), encoding="utf-8").read().strip()
except OSError: PUBLIC_PASSWORD = ""
M, KN, NM = 111320.0, 0.514444, 1852.0
START = (0.0, -300.0)           # position du guide au depart (repere local du monde)
VMAX_GUIDE, VMAX = 10.3, 15.0      # 20 et 29 noeuds
FORMS = {
    "column":       {"hannibal": (0, 0), "alfa": (-400, 0), "charlie": (-800, 0), "delta": (-1200, 0)},
    "line_abreast": {"hannibal": (0, 0), "alfa": (0, -400), "charlie": (0, 400), "delta": (0, 800)},
    "screen":       {"hannibal": (0, 0), "alfa": (600, -500), "charlie": (600, 500), "delta": (-500, 0)},
    "line_abreast_stbd": {"hannibal": (0, 0), "alfa": (0, 300), "charlie": (0, 600), "delta": (0, 900)},
    "line_abreast_port": {"hannibal": (0, 0), "alfa": (0, -300), "charlie": (0, -600), "delta": (0, -900)},
}
SPACING = 300.0                 # distance entre navires sur une ligne de relevement (m)
TURN_CONTACT = 3.0              # vitesse de giration d'une piste qui manoeuvre (deg/s)
SDF = ("<lotus_param><render_interface><publish_render>true</publish_render><renderer_type_name>fremm</renderer_type_name>"
       "</render_interface><waypoint_follower><follower><loop>false</loop><range_tolerance>1</range_tolerance>"
       "<line><direction>0</direction><length>5000</length></line>"
       "<linear_velocities_limits>0.5 16</linear_velocities_limits><linear_accel_limit>0.8</linear_accel_limit>"
       "<angular_velocities_limits>0.07</angular_velocities_limits><angular_accel_limit>0.03</angular_accel_limit>"
       "</follower></waypoint_follower></lotus_param>")


def clamp(x, a, b): return max(a, min(b, x))
def angdiff(a, b): return ((a - b + 540.0) % 360.0) - 180.0


# ---------------------------------------------------------------- Docker (API via socket)
class _Unix(http.client.HTTPConnection):
    def __init__(self): super().__init__("localhost"); 
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); self.sock.connect("/var/run/docker.sock")


def docker(method, path, body=None):
    try:
        c = _Unix(); c.request(method, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"})
        r = c.getresponse(); data = r.read(); c.close()
        return r.status, (json.loads(data) if data[:1] in (b"{", b"[") else data.decode(errors="replace"))
    except Exception as e:
        return 0, str(e)


def ensure_relay():
    st, info = docker("GET", f"/containers/{RELAY}/json")
    if st == 200:
        if not info["State"]["Running"]: docker("POST", f"/containers/{RELAY}/start")
        return True, "relais déjà présent"
    cmd = "source /opt/ros/jazzy/setup.bash; source /build/install/setup.bash; ros2 run ros_tcp_endpoint default_server_endpoint --ros-args -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000"
    st, r = docker("POST", f"/containers/create?name={RELAY}", {"Image": RELAY_IMAGE, "Cmd": ["bash", "-c", cmd],
                   "Env": [f"YAW_OFFSET_DEG={YAW_OFFSET}"], "HostConfig": {"NetworkMode": "host", "IpcMode": "host", "RestartPolicy": {"Name": "unless-stopped"}}})
    if st not in (200, 201): return False, f"création impossible ({st}) {r}"
    st, r = docker("POST", f"/containers/{RELAY}/start")
    return st in (200, 204), "relais créé"


# ---------------------------------------------------------------- noeud ROS
TOL = 90   # tolérance (s) après l'échéance

class Ros(Node):
    def __init__(self):
        super().__init__("hannibal_server_v2", namespace="/lotusim")
        self.create_subscription(VesselPositionArray, f"/{WORLD}/poses", self.on_poses, 10)
        self.arr = ActionClient(self, MASCmdArray, f"/{WORLD}/mas_cmd_array")
        self.st, self.cli, self.lock = {}, {}, threading.RLock()

    def on_poses(self, msg):
        with self.lock:
            for v in msg.vessels:
                q = v.pose.orientation
                yaw = math.degrees(math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)))
                self.st[v.vessel_name] = dict(x=v.pose.position.x, y=v.pose.position.y, lat=v.geo_point.latitude,
                                              lon=v.geo_point.longitude, sog=v.speed_over_ground, hdg=(90 - yaw) % 360, t=time.time())

    def send(self, cmds, timeout=20.0):
        g = MASCmdArray.Goal()
        for c in cmds: g.cmd.append(c)
        if not self.arr.wait_for_server(timeout_sec=timeout): return False
        ev = threading.Event(); box = {}
        f = self.arr.send_goal_async(g)
        f.add_done_callback(lambda ff: (box.__setitem__("h", ff.result()), ev.set()))
        if not ev.wait(timeout): return False
        h = box.get("h")
        if h and h.accepted:
            ev2 = threading.Event(); h.get_result_async().add_done_callback(lambda ff: ev2.set()); ev2.wait(timeout)
            return True
        return False

    def spawn(self, ships, cap):
        cmds = []
        yaw = math.radians(90 - cap)
        for name, (x, y) in ships.items():
            m = MASCmdMsg(); m.cmd_type = MASCmdMsg.CREATE_CMD; m.model_name = "fremm"; m.vessel_name = name
            m.vessel_position = Pose(); m.vessel_position.position.x = float(x); m.vessel_position.position.y = float(y)
            m.vessel_position.orientation.z = math.sin(yaw / 2); m.vessel_position.orientation.w = math.cos(yaw / 2)
            m.sdf_string = SDF; cmds.append(m)
        return self.send(cmds)

    def delete(self, names):
        cmds = []
        for n in names:
            m = MASCmdMsg(); m.cmd_type = MASCmdMsg.DELETE_CMD; m.vessel_name = n; cmds.append(m)
        return self.send(cmds, 8.0)

    def carrot(self, name, course, v_cmd, dI):
        """Place un waypoint devant le navire : sa distance regle la vitesse (loi mesuree)."""
        s = self.st.get(name)
        if not s: return dI
        if name not in self.cli:
            for sn, _ in self.get_service_names_and_types():
                if sn == f"/{WORLD}/{name}/waypoints": self.cli[name] = self.create_client(SetWaypoints, sn)
            if name not in self.cli: return dI
        if abs(v_cmd - s["sog"]) < 1.5: dI = clamp(dI + 0.15 * (v_cmd - s["sog"]) * 0.5, -6, 8)
        D = clamp((v_cmd - 1.6) / 0.414 + dI, 4.0, 80.0)
        diff = angdiff(course, s["hdg"])
        r = math.radians(s["hdg"] + clamp(diff, -25.0, 25.0))
        req = SetWaypoints.Request(); req.loop = False
        req.path = [GeoPoint(latitude=s["lat"] + D * math.cos(r) / M,
                             longitude=s["lon"] + D * math.sin(r) / (M * math.cos(math.radians(s["lat"]))), altitude=0.0)]
        self.cli[name].call_async(req)
        return dI


# ---------------------------------------------------------------- simulation
class Hannibal:
    def __init__(self):
        self.ros = Ros()
        self.lock = threading.RLock()
        self.scen = None; self.run = None
        self.steps = []; self.phase = "idle"; self.unity_ok = threading.Event()
        self.msg_id = 0
        self.audit = hxbridge.Audit(); self.cmds = {}
        self.ros.create_timer(0.5, self.tick)

    # --- scenarios
    def scenarios(self):
        out = []
        for f in sorted(glob.glob(os.path.join(HERE, "scenarios", "*.yaml"))):
            d = yaml.safe_load(open(f, encoding="utf-8"))
            o = {k: d.get(k) for k in ("id", "titre", "niveau", "duree_s", "resume", "briefing", "formation_depart", "cap_initial", "vitesse_initiale_kn", "flotte")}
            o["slots"] = FORMS[d.get("formation_depart", "column")]; out.append(o)
        return out

    def load(self, sid):
        for f in glob.glob(os.path.join(HERE, "scenarios", "*.yaml")):
            d = yaml.safe_load(open(f, encoding="utf-8"))
            if d["id"] == sid: return d
        return None

    # --- demarrage
    def step(self, sid, label, state, detail=""):
        with self.lock:
            for s in self.steps:
                if s["id"] == sid: s.update(label=label, state=state, detail=detail); return
            self.steps.append({"id": sid, "label": label, "state": state, "detail": detail})

    def start(self, sid, player, with_unity, auto=False, manual=False):
        self.auto_req = bool(auto); self.manual_req = bool(manual)
        threading.Thread(target=self._start, args=(sid, player, with_unity), daemon=True).start()

    def _start(self, sid, player, with_unity):
        try:
            sc = self.load(sid)
            if not sc: self.phase = "error"; self.step("erreur", "Scénario introuvable", "err", sid); return
            with self.lock: self.steps = []; self.run = None; self.phase = "starting"; self.unity_ok.clear()
            names = [f["nom"] for f in sc["flotte"]]
            self.step("moteur", "Moteur LOTUSim", "run", "redémarrage propre…")
            self.step("navires", "Navires", "wait")
            self.ros.delete(names)
            st, r = docker("POST", f"/containers/{ENGINE}/restart?t=3")
            if st not in (204, 200): self.step("moteur", "Moteur LOTUSim", "err", f"docker {st} {r}"); self.phase = "error"; return
            time.sleep(14)
            if not self.ros.arr.wait_for_server(timeout_sec=30): self.step("moteur", "Moteur LOTUSim", "err", "le moteur ne répond pas"); self.phase = "error"; return
            self.ros.cli.clear(); self.ros.st.clear()
            self.step("moteur", "Moteur LOTUSim", "ok", "prêt")
            self.step("navires", "Navires", "run")
            cap = float(sc.get("cap_initial", 0)); f0 = sc.get("formation_depart", "column")
            gx, gy = START; r = math.radians(cap); u = (math.sin(r), math.cos(r)); sd = (math.cos(r), -math.sin(r))
            pos = {}
            for n in names:
                a, c = FORMS[f0][n]; pos[n] = (gx + a * u[0] + c * sd[0], gy + a * u[1] + c * sd[1])
            if not self.ros.spawn(pos, cap): self.step("navires", "Navires", "err", "création refusée"); self.phase = "error"; return
            t0 = time.time()
            while time.time() - t0 < 25 and not all(n in self.ros.st for n in names): time.sleep(0.3)
            if not all(n in self.ros.st for n in names): self.step("navires", "Navires", "err", "positions non reçues"); self.phase = "error"; return
            self.step("navires", "Navires", "ok", f"{len(names)} frégates")
            guide = next(f["nom"] for f in sc["flotte"] if f["role"] == "guide")
            ships = {f["nom"]: {"role": f["role"], "mode": "formation", "cap": cap, "v": 0.0, "dI": 0.0} for f in sc["flotte"]}
            run = {"sc": sc, "player": player, "guide": guide, "t0": time.time(), "ships": ships, "gcap": cap,
                   "gspeed": clamp(sc.get("vitesse_initiale_kn", 12) * KN, 1.5, VMAX_GUIDE), "form": f0,
                   "events": sorted([e for e in sc.get("evenements", []) if "t" in e], key=lambda e: e["t"]),
                   "cond": [e for e in sc.get("evenements", []) if "t" not in e], "drill": self._drill_init(sc), "dyn": [],
                   "contacts": {}, "msgs": [], "pending": [],
                   "reported": set(), "plog": [], "ended": False, "debrief": None, "min_ship": 1e9, "min_cpa": {}, "plan": [], "auto": getattr(self, "auto_req", False),
                   "manual": getattr(self, "manual_req", False),
                   "helm": {"cap": cap, "kn": float(sc.get("vitesse_initiale_kn", 12)), "rudder": 0, "last": 0, "steady": True}}
            with self.lock: self.run = run; self.phase = "running"
            self.say("SYSTÈME", "TOUS", "", f"Scénario « {sc['titre']} » démarré. Tu es {player.upper()}" + (" (guide)." if player == guide else ", escorte du guide " + guide.upper() + "."), "info")
        except Exception:
            traceback.print_exc(); self.step("erreur", "Erreur interne", "err", traceback.format_exc()[-300:]); self.phase = "error"

    def stop(self):
        with self.lock:
            r = self.run; self.run = None; self.phase = "idle"; self.steps = []
        if r: threading.Thread(target=lambda: self.ros.delete(list(r["ships"])), daemon=True).start()

    # --- messages
    def say(self, frm, to, text_en, text_fr, kind, pending=False):
        run = self.run
        if run is None: return
        self.msg_id += 1
        m = {"id": self.msg_id, "t": round(time.time() - run["t0"], 1), "from": frm, "to": to, "en": text_en, "fr": text_fr, "kind": kind, "pending": pending}
        run["msgs"].append(m); run["msgs"] = run["msgs"][-80:]
        return m

    # --- ordres
    MOTION = ("CORPEN", "TURN", "SPEED", "FORM", "RESUME")

    def _group(self, run, o):
        if o["type"] == "FORM":
            run["form"] = o["name"]; run["axis"] = None
            if o["name"] == "bearing":
                run["form_rel"] = (o["rel"] if "rel" in o else o["true"] - run["gcap"]) % 360
            run["form_key"] = o["name"] + (":%d" % round(run["form_rel"]) if o["name"] == "bearing" else "")
            run["form_t"] = time.time() - run["t0"]
        elif o["type"] in ("CORPEN", "TURN", "SPEED"):
            if o["type"] != "SPEED":
                # TURN (virage ensemble) : l'axe de la formation ne tourne pas, chaque navire vire en meme temps.
                # CORPEN (conversion) : la formation tourne avec le guide.
                if o.get("together"):
                    if run.get("axis") is None: run["axis"] = run["gcap"]
                else: run["axis"] = None
            cap, spd = sim.apply_orders(run["gcap"], run["gspeed"], [o]); run["gcap"], run["gspeed"] = cap, clamp(spd, 1.5, VMAX_GUIDE)

    def _free(self, run, n, o):
        sh = run["ships"][n]; s = self.ros.st.get(n)
        base_cap = sh["cap"] if sh["mode"] in ("free", "pending") else (s["hdg"] if s else run["gcap"])
        base_v = sh["v"] if sh["mode"] in ("free", "pending") else (s["sog"] if s else run["gspeed"])
        cap, spd = sim.apply_orders(base_cap, base_v, [o])
        sh.update(mode="free", cap=cap, v=clamp(spd, 1.5, VMAX))

    def _to_pending(self, run, n, o, group):
        sh = run["ships"][n]; s = self.ros.st.get(n)
        if run.get("manual") and n == run["player"]:
            tg = {}
            if s and o["type"] in ("CORPEN", "TURN", "SPEED"):
                cap, v = sim.apply_orders(s["hdg"], s["sog"], [o]); tg = {"cap": cap, "v": v}
            run["pending"].append({"orders": [o], "group": group, "t": time.time() - run["t0"], "target": tg})
            if not run.get("await_ack"): run["await_ack"] = {"t": time.time() - run["t0"], "n": 0}
            return
        if sh["mode"] == "formation":
            sh.update(cap=s["hdg"] if s else run["gcap"], v=s["sog"] if s else run["gspeed"])
        sh["mode"] = "pending"
        run["pending"].append({"orders": [o], "group": group, "t": time.time() - run["t0"]})

    def execute(self, to, orders, source, by_player):
        """Applique des ordres. by_player=True : le joueur execute (pour son navire s'il est escorte)."""
        run = self.run; me = run["player"]; guide = run["guide"]; S = run["ships"]
        for o in orders:
            t = o["type"]
            if t not in self.MOTION: continue
            if by_player and me != guide:                      # escorte : il ne commande que son navire
                p = next((p for p in run["pending"] if p["orders"] == [o]), None)
                if t in ("RESUME", "FORM"): S[me]["mode"] = "formation"; run["pending"] = [q for q in run["pending"] if q["orders"][0]["type"] != "FORM"]
                elif p and p["group"]:
                    S[me]["mode"] = "formation"; run["pending"] = [q for q in run["pending"] if not q["group"]]
                else:
                    if p: run["pending"].remove(p)
                    self._free(run, me, o)
                continue
            if to == ["TOUS"]:
                if t == "RESUME":
                    for n in S: S[n]["mode"] = "formation"
                    continue
                self._group(run, o)
                if not by_player and me != guide: self._to_pending(run, me, o, True)
                continue
            for tn in to:
                n = tn.lower()
                if n not in S: continue
                if n == guide: self._group(run, o) if t != "RESUME" else None; continue
                if t == "RESUME": S[n]["mode"] = "formation"; continue
                if t == "FORM": continue
                if n == me and not by_player: self._to_pending(run, n, o, False)
                else: self._free(run, n, o)

    def player_order(self, text, force_to=None):
        run = self.run
        if not run: return {"ok": False, "error": "Aucun scénario en cours."}
        me, guide = run["player"], run["guide"]
        pr = mtp.parse(text, list(run["ships"]))
        if not pr["ok"]: return {"ok": False, "error": pr["error"], "hint": pr["hint"]}
        to, orders = pr["to"], pr["orders"]
        motion = [o for o in orders if o["type"] in ("CORPEN", "TURN", "SPEED", "FORM", "RESUME")]
        if me != guide and motion and to not in (["TOUS"], [me.upper()]):
            return {"ok": False, "error": "Seul le guide peut ordonner à un autre navire.", "hint": f"Adresse l'ordre à {me.upper()}."}
        if me != guide and motion and to == ["TOUS"]: to = [me.upper()]
        txt_en = mtp.to_text(to, orders, me)
        fr = mtp.fr_message(to, orders)
        with self.lock:
            self.execute(to, orders, me, True)
            run["plog"].append({"t": time.time() - run["t0"], "to": to, "orders": orders})
            for o in orders:
                if o["type"] == "EMERG":
                    for c in run["contacts"]: run["reported"].add(c)
            self.say(me.upper(), "TOUS" if to == ["TOUS"] else to[0], txt_en, fr, "joueur")
        return {"ok": True, "fr": fr, "en": txt_en}

    def classify(self, cid, cls):
        with self.lock:
            c = self.run["contacts"].get(cid) if self.run else None
            if not c or cls not in ("ami", "neutre", "hostile", "inconnu"): return False
            c["cls"] = cls; c["cls_t"] = time.time() - self.run["t0"]; return True

    # --- HANNIBAL X : voix / texte -> signal MTP -> approbation -> execution
    def voice(self, data, target):
        """Audio recu : transcription, interpretation, puis attente de l'approbation de l'operateur."""
        if not self.run: return {"ok": False, "error": "Aucun scénario en cours."}
        if len(data) < 2000: return {"ok": False, "error": "Enregistrement trop court."}
        r = hxbridge.call("/voice", data=data, timeout=90)
        if "error" in r: return {"ok": False, "error": r["error"]}
        return self._build(r["transcript"], target, "voix", asr=r, audio=data)

    def interpret_text(self, text, target, parent=None):
        if not self.run: return {"ok": False, "error": "Aucun scénario en cours."}
        if not text.strip(): return {"ok": False, "error": "Message vide."}
        return self._build(text, target, "texte", parent=parent)

    def _build(self, text, target, source, asr=None, audio=None, parent=None):
        run = self.run; me = run["player"]; guide = run["guide"]; ships = list(run["ships"])
        cid = self.audit.new_id()
        if audio: self.audit.save_audio(cid, audio)
        fixed, note_frame = hxbridge.fix_frame(text, ships, me)
        ans = hxbridge.reply_word(fixed, ships)
        if ans:                                            # « affirmative » / « negative » : reponse a une demande
            word, dest_ship = ans
            pend = list(run.get("requests", {}))
            tgt = dest_ship or (target.lower() if target and target.upper() != "TOUS" and target.lower() in ships else (pend[0] if pend else None))
            if word in ("roger", "wilco"):
                tgt = dest_ship or (guide if me != guide else tgt)
                rec = {"id": cid, "t": round(time.time() - run["t0"], 1), "source": source, "parent": parent, "transcript": text, "interpreted_text": fixed,
                       "words": (asr or {}).get("words", []), "asr_seconds": (asr or {}).get("asr_seconds"), "asr_model": (asr or {}).get("asr_model"),
                       "status": "ok" if tgt else "empty", "status_fr": "Accusé de réception" if tgt else "Accusé sans destinataire", "signal": None, "signal_id": None,
                       "meaning": None, "reference": None, "params": {}, "warnings": [], "notes": [] if tgt else ["Dites le nom du navire, ou choisissez-le à l'écran."],
                       "to": [tgt.upper()] if tgt else None, "from": me.upper(), "method": "plain", "written_signal": word.upper(),
                       "orders": [{"type": "ACK", "text": word.upper()}], "effect": None,
                       "fr": (f"À {tgt.capitalize()} : " if tgt else "") + ("bien reçu." if word == "roger" else "bien reçu, j'exécute."),
                       "legacy": False, "audio": bool(audio), "hint": None, "groups": [], "can_execute": bool(tgt), "state": "awaiting_review", "llm": None}
                with self.lock: self.cmds[cid] = rec
                self.audit.log(cid, "received", me, source=source, scenario=run["sc"]["id"], t=rec["t"], audio=bool(audio))
                if asr: self.audit.log(cid, "transcribed", me, transcript=text, words=rec["words"], asr_model=rec["asr_model"], asr_seconds=rec["asr_seconds"])
                self.audit.log(cid, "interpreted", me, text=fixed, status=rec["status"], signal=rec["written_signal"], to=rec["to"], orders=rec["orders"])
                self.audit.log(cid, "awaiting_review", me)
                return {"ok": True, "cmd": rec}
            rec = {"id": cid, "t": round(time.time() - run["t0"], 1), "source": source, "parent": parent, "transcript": text, "interpreted_text": fixed,
                   "words": (asr or {}).get("words", []), "asr_seconds": (asr or {}).get("asr_seconds"), "asr_model": (asr or {}).get("asr_model"),
                   "status": "ok" if tgt else "empty", "status_fr": "Réponse reconnue" if tgt else "Réponse sans destinataire", "signal": None, "signal_id": None, "meaning": None,
                   "reference": None, "params": {}, "warnings": [], "notes": [] if tgt in pend else (["Ce navire n'a pas de demande en attente."] if tgt else ["Dites le nom du navire, ou choisissez-le à l'écran."]),
                   "to": [tgt.upper()] if tgt else None, "from": me.upper(), "method": "plain", "written_signal": "AFFIRMATIVE" if word == "affirm" else "NEGATIVE",
                   "orders": [{"type": "CAPT", "do": word}], "effect": "Le commandant du navire agit selon votre réponse.",
                   "fr": (f"À {tgt.capitalize()} : " if tgt else "") + ("affirmatif, autorisation accordée." if word == "affirm" else "négatif, restez à votre poste."),
                   "legacy": False, "audio": bool(audio), "hint": None, "groups": [], "can_execute": bool(tgt), "state": "awaiting_review", "llm": None}
            with self.lock: self.cmds[cid] = rec
            self.audit.log(cid, "received", me, source=source, scenario=run["sc"]["id"], t=rec["t"], audio=bool(audio))
            if asr: self.audit.log(cid, "transcribed", me, transcript=text, words=rec["words"], asr_model=rec["asr_model"], asr_seconds=rec["asr_seconds"])
            self.audit.log(cid, "interpreted", me, text=fixed, status=rec["status"], signal=rec["written_signal"], to=rec["to"], orders=rec["orders"])
            self.audit.log(cid, "awaiting_review", me)
            return {"ok": True, "cmd": rec}
        r = hxbridge.call("/interpret", body={"text": fixed})
        if "error" in r: return {"ok": False, "error": r["error"]}
        it = r["interp"]; notes = [n for n in (note_frame,) if n]
        to, note_to = hxbridge.destination(it, ships, target)
        if note_to: notes.append(note_to)
        if it.get("from") and it["from"].upper() != me.upper():
            notes.append(f"L'émetteur énoncé ({it['from']}) n'est pas votre indicatif ({me.upper()}).")
        ref_ship = to[0].lower() if to and to != ["TOUS"] else guide
        st = self.ros.st.get(ref_ship)
        groups = it.get("groups") or [it]
        orders, effects, frs, status = [], [], [], "ok"
        for g in groups:                                   # un message peut porter plusieurs signaux
            o, e = hxbridge.to_orders(g, (st["sog"] if st else run["gspeed"]) / KN)
            if g["status"] != "ok" and status == "ok": status = g["status"]
            if o is None: o = []; g["status"] = "invalid_parameter"; g.setdefault("warnings", []).append(e); status = "invalid_parameter" if status == "ok" else status
            elif e: effects.append(e)
            orders += o
            g["status_fr"] = hxbridge.STATUS_FR.get(g["status"], g["status"])
            if g["status"] == "ok":
                frs.append(hxbridge.fr_signal(g, to) or (mtp.fr_message(to or ["TOUS"], o) if o else
                           "Signal " + (g.get("signal") or "") + " — sens d'après la publication : " + (g.get("meaning") or "")))
        it["status"] = status
        effect = " ".join(effects) or None
        legacy = False
        if status != "ok":                                 # ancienne syntaxe simplifiee du simulateur
            pr = mtp.parse(text, ships)
            if pr["ok"]:
                legacy, orders, to = True, pr["orders"], pr["to"]
                effect = "Syntaxe simplifiée du simulateur, hors publication MTP."
        escort_block = False
        if me != guide:
            if not it.get("to"): to = [guide.upper()]; notes = [n for n in notes if not n.startswith("Destinataire non énoncé")]
            if any(o["type"] in self.MOTION or o["type"] == "CAPT" for o in orders):
                notes.append("Vous commandez une escorte : seul le guide donne des ordres de manœuvre. Rendez compte au guide (ROGER, A STATION, M SPEED…).")
                escort_block = True
        ok_sig = (status == "ok" or legacy) and not escort_block
        if escort_block: fr = "Message non envoyé : une escorte ne donne pas d'ordre de manœuvre."
        elif legacy: fr = mtp.fr_message(to, orders)
        elif not ok_sig: fr = hxbridge.STATUS_FR.get(status, status) + "."
        else:
            who = frs[0].split(" : ", 1)[0] if " : " in frs[0] else ""
            fr = frs[0] + "".join(" Puis : " + (f.split(" : ", 1)[1] if who and f.startswith(who + " : ") else f) for f in frs[1:])
        hint = None if ok_sig else hxbridge.HINTS.get(status)
        rec = {"id": cid, "t": round(time.time() - run["t0"], 1), "source": source, "parent": parent,
               "transcript": text, "interpreted_text": fixed, "words": (asr or {}).get("words", []),
               "asr_seconds": (asr or {}).get("asr_seconds"), "asr_model": (asr or {}).get("asr_model"),
               "status": "ok" if legacy else it["status"], "status_fr": "Syntaxe simplifiée reconnue" if legacy else hxbridge.STATUS_FR.get(it["status"], it["status"]),
               "signal": None if legacy else it.get("signal"), "signal_id": None if legacy else it.get("signal_id"),
               "meaning": None if legacy else it.get("meaning"), "reference": None if legacy else it.get("reference"),
               "params": it.get("params") or {}, "warnings": it.get("warnings") or [], "notes": notes,
               "to": to, "from": it.get("from"), "method": it.get("method"), "written_signal": it.get("written_signal"),
               "orders": orders, "effect": effect, "fr": fr, "legacy": legacy, "audio": bool(audio), "hint": hint,
               "groups": [] if legacy else [{k: g.get(k) for k in ("status", "status_fr", "signal", "meaning", "reference", "params", "written_signal")} for g in groups],
               "can_execute": bool(ok_sig and to), "state": "awaiting_review", "llm": None}
        with self.lock: self.cmds[cid] = rec; self.cmds = dict(list(self.cmds.items())[-200:])
        self.audit.log(cid, "received", me, source=source, parent=parent, scenario=run["sc"]["id"], t=rec["t"], audio=bool(audio))
        if asr: self.audit.log(cid, "transcribed", me, transcript=text, words=rec["words"], asr_model=rec["asr_model"], asr_seconds=rec["asr_seconds"])
        self.audit.log(cid, "interpreted", me, text=fixed, status=rec["status"], signal=rec["signal"], signal_id=rec["signal_id"],
                       reference=rec["reference"], params=rec["params"], to=to, orders=orders, warnings=rec["warnings"], notes=notes, legacy=legacy)
        self.audit.log(cid, "awaiting_review", me)
        return {"ok": True, "cmd": rec}

    def confirm(self, cid, decision):
        run = self.run; rec = self.cmds.get(cid)
        if not run or not rec: return {"ok": False, "error": "Commande introuvable."}
        if rec["state"] != "awaiting_review": return {"ok": False, "error": "Commande déjà traitée."}
        me = run["player"]
        if decision != "execute":
            rec["state"] = "rejected"; self.audit.log(cid, "rejected", me); return {"ok": True, "cmd": rec}
        if not rec["can_execute"]: return {"ok": False, "error": "Ce message ne peut pas être approuvé : " + rec["status_fr"] + "."}
        to, orders = rec["to"], rec["orders"]
        dest = "ALL SHIPS" if to == ["TOUS"] else to[0]
        en = mtp.to_text(to, orders, me) if rec["legacy"] else f"{dest} THIS IS {me.upper()} {rec['written_signal']} OVER"
        emerg = (rec.get("signal") or "").startswith("EMERG") or any(o["type"] == "EMERG" for o in orders)
        with self.lock:
            if orders: self.execute(to, orders, me, True)
            run["plog"].append({"t": time.time() - run["t0"], "to": to, "orders": orders + ([{"type": "EMERG", "text": rec.get("signal") or ""}] if emerg and not rec["legacy"] else [])})
            if emerg:
                for c in run["contacts"]: run["reported"].add(c)
            self.say(me.upper(), "TOUS" if to == ["TOUS"] else to[0], en, rec["fr"], "joueur")
            # les navires adresses accusent reception
            who = [n for n in run["ships"] if n != me] if to == ["TOUS"] else [n.lower() for n in to if n.lower() in run["ships"] and n.lower() != me]
            t = time.time() - run["t0"]
            self._captain_orders(run, to, orders, t)
            if any(o["type"] in ("CAPT", "ACK") for o in orders): who = []
            if me != run["guide"]: run.pop("await_ack", None)        # l'escorte a parle au guide
            for i, n in enumerate(who):
                run["events"].append({"t": t + 2.5 + 1.6 * i, "de": n, "a": me, "ordres": [{"type": "ACK", "text": "ROGER"}]})
            run["events"].sort(key=lambda e: e["t"])
        rec["state"] = "approved"
        self.audit.log(cid, "approved", me, sent=en, to=to, orders=orders)
        self.audit.log(cid, "logged", me)
        return {"ok": True, "cmd": rec, "en": en}

    def explain(self, cid):
        rec = self.cmds.get(cid)
        if not rec: return {"ok": False, "error": "Commande introuvable."}
        r = hxbridge.call("/explain", body={"text": rec["interpreted_text"]}, timeout=150)
        if "error" in r: return {"ok": False, "error": r["error"]}
        rec["llm"] = {k: r.get(k) for k in ("explanation_fr", "explanation_en", "explanation_source", "ambiguities", "clarification_questions", "references_used", "llm", "seconds")}
        self.audit.log(cid, "llm_explained", self.run["player"] if self.run else None, **rec["llm"])
        return {"ok": True, "llm": rec["llm"]}

    # --- boucle de controle (2 Hz)
    def tick(self):
        try:
            with self.lock:
                run = self.run
                if not run or run["ended"]: return
                t = time.time() - run["t0"]
                self.events(run, t)
                self.autopilot(run, t)
                self.control(run)
                dt = time.time() - run.get("last", time.time()); run["last"] = time.time()
                self.observe(run, t, dt)
                self._contacts(run, t, dt); self._drill(run, t); self._captains(run, t, dt); self._manual(run, t)
                if t > run["sc"]["duree_s"] or t > run.get("end_at", 1e12): self.finish(run)
        except Exception:
            traceback.print_exc()

    def autopilot(self, run, t):
        """Mode automatique : le navire du joueur agit seul comme un capitaine (accusé, exécution)."""
        if not run.get("auto") or run.get("manual"): return
        me, guide = run["player"], run["guide"]
        if me == guide: return
        acked = run.setdefault("auto_acked", set())
        for m in run["msgs"]:
            if m["kind"] == "urgence" and m["id"] not in acked and t - m["t"] > 6:
                acked.add(m["id"]); self.player_order(f"{guide.upper()} THIS IS {me.upper()} ROGER OVER")
        for p in list(run["pending"]):
            if t - p["t"] > 5 and p in run["pending"]:
                self.player_order(mtp.to_text([me.upper()], p["orders"], me))

    def set_auto(self, on):
        if not self.run: return False
        self.run["auto"] = bool(on); return True

    def events(self, run, t):
        sc, me, guide = run["sc"], run["player"], run["guide"]
        while run["events"] and run["events"][0]["t"] <= t:
            ev = run["events"].pop(0)
            if "piste" in ev:
                self._spawn_contact(run, ev["piste"], t)
                continue
            to = ["TOUS"] if ev["a"] == "TOUS" else [ev["a"].upper()]
            orders = ev["ordres"]; frm = ev["de"].upper()
            en = mtp.to_text(to, orders, frm); fr = mtp.fr_message(to, orders)
            urgent = any(o["type"] == "EMERG" for o in orders)
            to_me = to == ["TOUS"] or to == [me.upper()]
            mot = [o for o in orders if o["type"] in ("CORPEN", "TURN", "SPEED", "FORM", "RESUME")]
            if me == guide and ev["de"] == guide and run.get("auto"):
                run["plog"].append({"t": t, "to": to, "orders": orders})
            elif me == guide and ev["de"] == guide:
                self.say(frm, to[0], en, fr, "plan")        # ordre prevu : au joueur de l'executer
                continue
            ack = all(o["type"] == "ACK" for o in orders)
            self.say(frm, to[0], en, fr, "ack" if ack else "urgence" if urgent else "ordre", pending=bool(to_me and mot and me != guide))
            self.execute(to, orders, frm, False)

    # --- scenarios interactifs : pistes qui manoeuvrent, comptes rendus, exercice de formations
    def _slots(self, run):
        if run["form"] != "bearing": return FORMS[run["form"]]
        r = math.radians(run.get("form_rel", 180.0)); out = {run["guide"]: (0.0, 0.0)}
        for i, n in enumerate([x for x in run["ships"] if x != run["guide"]], start=1):
            out[n] = (SPACING * i * math.cos(r), SPACING * i * math.sin(r))
        return out

    def _spawn_contact(self, run, p, t):
        g = self.ros.st.get(run["guide"])
        if not g: return
        b = math.radians(g["hdg"] + p["rel"]); d = p["dist_nm"] * NM; cr = math.radians(p["cap"]); v = p["vit_kn"] * KN
        run["contacts"][p["id"]] = {"id": p["id"], "type": p["type"], "x": g["x"] + d * math.sin(b), "y": g["y"] + d * math.cos(b),
                                    "vx": v * math.sin(cr), "vy": v * math.cos(cr), "cls": "inconnu", "cls_reel": p.get("cls_reel", "inconnu"), "t0": t,
                                    "cap": p["cap"], "vit": p["vit_kn"], "beh": p.get("comportement"), "etat": "approche",
                                    "echec_nm": p.get("echec_dist_nm"), "bloc_nm": p.get("blocage_nm", 1.0), "bloc_s": p.get("blocage_s", 20), "blk": 0.0,
                                    "rep_left": sorted(p.get("rapports_nm", []), reverse=True)}

    def _drill_init(self, sc):
        steps = sc.get("etapes")
        if not steps: return None
        import random
        n = sc.get("etapes_aleatoires")
        if n:
            pool, out = list(steps), []
            while len(out) < n:
                c = random.choice(pool)
                if "rel_tens" in c:                   # ligne de relevement tiree au hasard
                    tens = random.choice(c["rel_tens"]); side = random.choice(["STBD", "PORT"])
                    c = {"key": "bearing:%d" % ((tens * 10) if side == "STBD" else (360 - tens * 10)),
                         "ordre": f"FORM {side} {tens}", "texte": f"Ligne de relèvement à {tens * 10}° sur {'tribord' if side == 'STBD' else 'bâbord'}"}
                if (out[-1]["key"] if out else sc.get("formation_depart")) != c["key"]: out.append(dict(c))
            steps = out
        return {"steps": [dict(x) for x in steps], "i": 0, "t_step": None, "ok_since": None, "delai": sc.get("etapes_delai_s", 150), "hint": False}

    def _drill(self, run, t):
        d = run["drill"]
        if not d or d["i"] >= len(d["steps"]): return
        st = d["steps"][d["i"]]
        if d["t_step"] is None:
            if t < 8: return
            d["t_step"] = t; d["hint"] = False
            run["dyn"].append({"texte": f"{d['i'] + 1}. {st['texte']}", "avant_t": round(t + d["delai"]), "ok": False, "t": None})
            self.say("DIRECTION", "TOUS", "", f"Exercice {d['i'] + 1} sur {len(d['steps'])} : faites prendre la formation « {st['texte']} ».", "info")
            return
        el = t - d["t_step"]
        if not d["hint"] and el > d["delai"] * 0.4 and run.get("form_key") != st["key"]:
            d["hint"] = True; self.say("DIRECTION", "TOUS", "", f"Indice : le signal est {st['ordre']}.", "info")
        S = run["ships"]
        in_st = all(sh["mode"] == "formation" and sh.get("err", 1e9) < 150 for n, sh in S.items() if n != run["guide"])
        good = run.get("form_key") == st["key"] and run.get("form_t", -1) >= d["t_step"] - 1
        d["ok_since"] = (d["ok_since"] or t) if (good and in_st) else None
        obj = run["dyn"][-1]
        if d["ok_since"] and t - d["ok_since"] >= 4:
            obj.update(ok=True, t=round(t)); d["i"] += 1; d["t_step"] = None; d["ok_since"] = None
            self.say("DIRECTION", "TOUS", "", f"Formation prise en {int(el // 60)} min {int(el % 60):02d} s.", "info")
        elif el > d["delai"]:
            d["i"] += 1; d["t_step"] = None; d["ok_since"] = None
            self.say("DIRECTION", "TOUS", "", f"Délai dépassé pour « {st['texte']} » (signal : {st['ordre']}).", "info")
        if d["i"] >= len(d["steps"]):
            self.say("DIRECTION", "TOUS", "", "Exercice terminé.", "info"); run["end_at"] = t + 5

    def _contacts(self, run, t, dt):
        """Pistes qui manoeuvrent : interception du guide, comptes rendus des escortes, repoussee par une escorte."""
        g = self.ros.st.get(run["guide"]); me = run["player"]
        if not g: return
        for e in list(run["cond"]):                       # evenements declenches par une situation
            c0 = run["contacts"].get(e.get("apres_repousse"))
            if c0 and c0["etat"] == "repousse" and t - c0["rep_t"] >= e.get("delai_s", 30):
                run["cond"].remove(e)
                if "piste" in e: self._spawn_contact(run, e["piste"], t)
        for c in run["contacts"].values():
            dx, dy = g["x"] - c["x"], g["y"] - c["y"]; dist = math.hypot(dx, dy); d_nm = dist / NM
            brg_from_guide = math.degrees(math.atan2(-dx, -dy)) % 360
            esc = [(math.hypot(s["x"] - c["x"], s["y"] - c["y"]), n) for n in run["ships"] if n != run["guide"] for s in [self.ros.st.get(n)] if s]
            near = min(esc)[1] if esc else run["guide"]
            while c["rep_left"] and d_nm < c["rep_left"][0] and c["etat"] == "approche":
                c["rep_left"].pop(0)
                self.say(near.upper(), me.upper(), f"{me.upper()} THIS IS {near.upper()} CONTACT {c['id']} BEARING {round(brg_from_guide) % 360:03d} RANGE {d_nm:.1f} MILES CLOSING OVER",
                         f"{near.capitalize()} : contact {c['id']} au {round(brg_from_guide) % 360:03d}, distance {d_nm:.1f} NM du guide, en rapprochement.", "rapport")
            if not c.get("beh"): continue
            if c["etat"] == "approche":
                gv = (g["sog"] * math.sin(math.radians(g["hdg"])), g["sog"] * math.cos(math.radians(g["hdg"])))
                v = c["vit"] * KN; lead = min(dist / max(v, 1.0), 120.0) * 0.6          # vise un peu en avant du guide
                want = math.degrees(math.atan2(dx + gv[0] * lead, dy + gv[1] * lead)) % 360
                if esc and min(esc)[0] < c["bloc_nm"] * NM: c["blk"] += dt
                else: c["blk"] = max(0.0, c["blk"] - dt * 0.5)
                if c["blk"] >= c["bloc_s"]:
                    c["etat"] = "repousse"; c["rep_t"] = t
                    self.say(near.upper(), me.upper(), f"{me.upper()} THIS IS {near.upper()} CONTACT {c['id']} TURNING AWAY OVER",
                             f"{near.capitalize()} : le contact {c['id']} fait demi-tour.", "rapport")
                elif c.get("echec_nm") and d_nm < c["echec_nm"]:
                    c["etat"] = "atteint"
                    self.say("DIRECTION", "TOUS", "", f"{c['id']} est arrivé à moins de {c['echec_nm']} NM du guide : la force est atteinte.", "urgence")
                    run["end_at"] = t + 4
            else:
                want = brg_from_guide                                   # il s'eloigne du guide
            if c["etat"] in ("approche", "repousse"):
                d = angdiff(want, c["cap"]); c["cap"] = (c["cap"] + clamp(d, -TURN_CONTACT * dt, TURN_CONTACT * dt)) % 360
                v = c["vit"] * KN; c["vx"], c["vy"] = v * math.sin(math.radians(c["cap"])), v * math.cos(math.radians(c["cap"]))
        act = [c for c in run["contacts"].values() if c.get("beh")]
        if act and not run["cond"] and all(c["etat"] == "repousse" and t - c["rep_t"] > 25 for c in act) and "end_at" not in run:
            self.say("DIRECTION", "TOUS", "", "Toutes les pistes hostiles sont repoussées.", "info"); run["end_at"] = t + 5

    # --- barre manuelle : le joueur gouverne lui-meme son navire
    def helm(self, b):
        run = self.run
        if not run or not run.get("manual"): return {"ok": False, "error": "La barre manuelle n'est pas active."}
        h = run["helm"]
        with self.lock:
            if "rudder" in b: h["rudder"] = int(clamp(int(b["rudder"]), -1, 1))
            if "dcap" in b: h["cap"] = (h["cap"] + float(b["dcap"])) % 360; h["rudder"] = 0; h["steady"] = True
            if "cap" in b: h["cap"] = float(b["cap"]) % 360; h["rudder"] = 0; h["steady"] = True
            if "dkn" in b: h["kn"] = clamp(h["kn"] + float(b["dkn"]), 0.0, 29.0)
            if "kn" in b: h["kn"] = clamp(float(b["kn"]), 0.0, 29.0)
        return {"ok": True, "helm": h}

    def _helm_tick(self, run):
        """Barre : tant qu'elle est tenue le navire vire ; relachee, il se stabilise sur son cap du moment."""
        h = run["helm"]; s = self.ros.st.get(run["player"])
        if not s: return h["cap"], max(h["kn"] * KN, 0.8)
        if h["rudder"]:
            h["cap"] = (s["hdg"] + 40.0 * h["rudder"]) % 360; h["last"] = h["rudder"]; h["steady"] = False
        elif not h["steady"]:
            h["cap"] = (s["hdg"] + 5.0 * h["last"]) % 360; h["steady"] = True
        return h["cap"], clamp(h["kn"] * KN, 0.8, VMAX)

    def _manual(self, run, t):
        """Joueur a la barre d'une escorte : le guide attend un accuse, et un ordre est tenu pour execute quand le navire y est."""
        me, guide = run["player"], run["guide"]
        if not run.get("manual") or me == guide: return
        s = self.ros.st.get(me); sh = run["ships"][me]
        aw = run.get("await_ack")
        if aw and t - aw["t"] > 25 and aw["n"] < 2:
            aw["t"] = t; aw["n"] += 1
            self.say(guide.upper(), me.upper(), f"{me.upper()} THIS IS {guide.upper()} ACKNOWLEDGE OVER", f"{guide.capitalize()} : accusez réception.", "ordre")
        if not s: return
        for p in list(run["pending"]):
            o = p["orders"][0]; tp = o["type"]
            if tp in ("FORM", "RESUME") or (p["group"] and tp in ("CORPEN", "TURN", "SPEED") and run["form"]):
                ok = sh.get("err", 1e9) < 250 and t - p["t"] > 8   # ordre a la formation : etre a son poste...
                if tp in ("CORPEN", "TURN"): ok = ok and abs(angdiff(run["gcap"], s["hdg"])) < 10     # ...sur la nouvelle route
                if tp == "SPEED" and p["group"]: ok = ok and abs(s["sog"] - run["gspeed"]) < 1.5
            else:
                tg = p.get("target") or {}
                ok = abs(angdiff(tg.get("cap", s["hdg"]), s["hdg"])) < 8 and abs(tg.get("v", s["sog"]) - s["sog"]) < 1.3
            p["ok_t"] = (p.get("ok_t") or t) if ok else None
            if p["ok_t"] and t - p["ok_t"] > 4:
                run["pending"].remove(p); run["plog"].append({"t": t, "to": [me.upper()], "orders": [o]})
                self.say("SYSTÈME", me.upper(), "", "Ordre exécuté : " + mtp.fr_order(o) + ".", "info")

    # --- capitaines : les commandants des autres navires repondent, rendent compte et prennent des initiatives
    def _cap(self, run, n):
        return run.setdefault("capt", {}).setdefault(n, {"task": None, "target": None, "rs": False, "rs_t": 0.0, "in_t": None})

    def _radio(self, run, frm, en_body, fr, kind="rapport", delay=0.0):
        run.setdefault("later", []).append((time.time() - run["t0"] + delay, frm, en_body, fr, kind))

    def _threat(self, run):
        g = self.ros.st.get(run["guide"])
        cs = [c for c in run["contacts"].values() if c.get("etat", "approche") == "approche" and c["cls"] != "ami"]
        return min(cs, key=lambda c: math.hypot(c["x"] - g["x"], c["y"] - g["y"])) if g and cs else None

    def _start_intercept(self, run, n, cid):
        cp = self._cap(run, n); cp.update(task="intercept", target=cid, rs=False)
        run.get("requests", {}).pop(n, None)

    def _captain_orders(self, run, to, orders, t):
        """Suites donnees par les commandants a un message approuve."""
        me = run["player"]; S = run["ships"]
        names = [n for n in S if n != me] if to == ["TOUS"] else [x.lower() for x in to if x.lower() in S and x.lower() != me]
        kn = lambda n: round((self.ros.st.get(n) or {}).get("sog", 0.0) / KN)
        for o in orders:
            if o["type"] in self.MOTION:
                for n in names:
                    cp = self._cap(run, n)
                    if cp["task"] and to == ["TOUS"]: continue      # un navire detache ne suit pas les ordres a la formation
                    if cp["task"]: cp.update(task=None, target=None)
                    if o["type"] in ("FORM", "RESUME") and run.get("auto"): cp.update(rs=True, rs_t=t, in_t=None)
                continue
            if o["type"] != "CAPT": continue
            do = o["do"]
            if do == "investigate":
                c0 = self._threat(run)
                if not c0:
                    for n in names[:1]: self._radio(run, n, "NEGAT TA62", "aucun contact à reconnaître.", delay=3)
                    continue
                if to == ["TOUS"]:
                    free = [(math.hypot(s["x"] - c0["x"], s["y"] - c0["y"]), n) for n in names if n != run["guide"] and not self._cap(run, n)["task"] for s in [self.ros.st.get(n)] if s]
                    names_i = [min(free)[1]] if free else []
                else: names_i = names
                for n in names_i:
                    self._start_intercept(run, n, c0["id"])
                    self._radio(run, n, f"WILCO BA TA62 {c0['id']}", f"bien reçu, je pars reconnaître {c0['id']} et je manœuvre pour lui barrer la route.", delay=3)
            elif do == "int_speed":
                for i, n in enumerate(names): self._radio(run, n, f"M SPEED {kn(n)}", f"ma vitesse est de {kn(n)} nœuds.", delay=3 + 2 * i)
            elif do == "int_corpen":
                for i, n in enumerate(names):
                    h = round((self.ros.st.get(n) or {}).get("hdg", 0.0)) % 360
                    self._radio(run, n, f"M CORPEN {h:03d} SPEED {kn(n)}", f"ma route est au {h:03d}, vitesse {kn(n)} nœuds.", delay=3 + 2 * i)
            elif do == "int_station":
                for i, n in enumerate(names):
                    sh = S[n]; cp = self._cap(run, n)
                    if cp["task"] == "intercept": self._radio(run, n, f"BA TA62 {cp['target']}", f"je suis détaché, en reconnaissance de {cp['target']}.", delay=3 + 2 * i)
                    elif sh["mode"] == "formation" and sh.get("err", 1e9) < 150: self._radio(run, n, "A STATION", "je suis en station.", delay=3 + 2 * i)
                    elif sh["mode"] == "formation": self._radio(run, n, "B STATION", f"je rejoins mon poste, encore à {int(sh.get('err', 0))} m.", delay=3 + 2 * i)
                    else: self._radio(run, n, "B STATION", "je suis hors formation, sur la route que vous m'avez ordonnée.", delay=3 + 2 * i)
            elif do == "report_station":
                for n in names: self._cap(run, n).update(rs=True, rs_t=t, in_t=None)
            elif do in ("affirm", "negat"):
                for n in names:
                    rq = run.get("requests", {}).get(n)
                    if not rq: self._radio(run, n, "ROGER", "bien reçu.", delay=3); continue
                    if do == "affirm":
                        self._start_intercept(run, n, rq["cid"])
                        self._radio(run, n, f"WILCO BA TA62 {rq['cid']}", f"bien reçu, je pars reconnaître {rq['cid']}.", delay=3)
                    else:
                        run["requests"].pop(n, None)
                        self._radio(run, n, "ROGER", "bien reçu, je reste à mon poste.", delay=3)

    def reply(self, ship, yes):
        """Reponse de l'operateur a une demande d'autorisation (bouton de la console)."""
        run = self.run
        if not run or ship not in run.get("requests", {}): return {"ok": False, "error": "Aucune demande en attente pour ce navire."}
        me = run["player"]; cid = self.audit.new_id(); en = f"{ship.upper()} THIS IS {me.upper()} {'AFFIRMATIVE' if yes else 'NEGATIVE'} OVER"
        with self.lock:
            self.say(me.upper(), ship.upper(), en, f"À {ship.capitalize()} : {'affirmatif, autorisation accordée' if yes else 'négatif, restez à votre poste'}.", "joueur")
            self._captain_orders(run, [ship.upper()], [{"type": "CAPT", "do": "affirm" if yes else "negat"}], time.time() - run["t0"])
        self.audit.log(cid, "received", me, source="bouton", scenario=run["sc"]["id"], audio=False)
        self.audit.log(cid, "approved", me, sent=en, to=[ship.upper()], orders=[])
        self.audit.log(cid, "logged", me)
        return {"ok": True}

    def _captains(self, run, t, dt):
        me = run["player"]; guide = run["guide"]; S = run["ships"]; g = self.ros.st.get(guide); auto = run.get("auto")
        for item in sorted(run.setdefault("later", [])):
            if t >= item[0]:
                run["later"].remove(item); _, frm, en_body, fr, kind = item
                self.say(frm.upper(), me.upper(), f"{me.upper()} THIS IS {frm.upper()} {en_body} OVER", f"{frm.capitalize()} : {fr}", kind)
        if not g: return
        RQ = run.setdefault("requests", {})
        for n in list(RQ):                                     # la demande tombe si la piste ne menace plus
            c = run["contacts"].get(RQ[n]["cid"])
            if not c or c.get("etat", "approche") != "approche": RQ.pop(n)
        if auto:
            for c in run["contacts"].values():
                if c.get("etat", "approche") != "approche" or c["cls"] == "ami" or not (c.get("beh") or c["cls"] == "hostile"): continue
                d_nm = math.hypot(c["x"] - g["x"], c["y"] - g["y"]) / NM
                if any(cp["task"] == "intercept" and cp["target"] == c["id"] for cp in run.get("capt", {}).values()): continue
                rq = next((r for r in RQ.values() if r["cid"] == c["id"]), None)
                brg = round(math.degrees(math.atan2(c["x"] - g["x"], c["y"] - g["y"]))) % 360
                if rq is None and d_nm < 3.0 and t - c.get("asked_t", -1e9) > 75:
                    free = [(math.hypot(s["x"] - c["x"], s["y"] - c["y"]), n) for n in S if n not in (me, guide) and not self._cap(run, n)["task"] and n not in RQ
                            for s in [self.ros.st.get(n)] if s]
                    if free:
                        n = min(free)[1]; c["asked_t"] = t
                        RQ[n] = {"ship": n, "cid": c["id"], "t": t, "fr": f"{n.capitalize()} demande l'autorisation d'aller reconnaître {c['id']} (au {brg:03d}, à {d_nm:.1f} NM du guide)."}
                        self._radio(run, n, f"BH TA62 {c['id']}", f"demande l'autorisation d'aller reconnaître {c['id']}, au {brg:03d} à {d_nm:.1f} NM du guide.", "demande")
                elif rq and d_nm < 1.7 and t - rq["t"] > 25:
                    n = rq["ship"]; self._start_intercept(run, n, c["id"])
                    self._radio(run, n, f"BA TA62 {c['id']}", f"sans réponse et {c['id']} à {d_nm:.1f} NM du guide : j'interviens de ma propre initiative.")
        for n, cp in run.get("capt", {}).items():
            s = self.ros.st.get(n); sh = S.get(n)
            if not s or not sh: continue
            if cp["task"] == "intercept":
                c = run["contacts"].get(cp["target"])
                if not c or c.get("etat", "approche") != "approche":
                    done = cp["target"]; cp.update(task=None, target=None, rs=True, rs_t=t, in_t=None); sh["mode"] = "formation"
                    self._radio(run, n, f"BB TA62 {done}", f"{done} ne menace plus, je reprends mon poste.", delay=4)
                    continue
                dx, dy = c["x"] - s["x"], c["y"] - s["y"]; d = math.hypot(dx, dy)
                lead = min(d / (VMAX + c["vit"] * KN * 0.5), 90.0) * 0.8        # viser en avant de la piste
                sh.update(mode="free", cap=math.degrees(math.atan2(dx + c["vx"] * lead, dy + c["vy"] * lead)) % 360, v=VMAX)
            elif cp["rs"] and sh["mode"] == "formation":
                err = sh.get("err", 1e9)
                cp["in_t"] = (cp["in_t"] or t) if err < 150 else None
                if cp["in_t"] and t - cp["in_t"] > 3 and t - cp["rs_t"] > 6:
                    cp.update(rs=False, in_t=None); self._radio(run, n, "A STATION", "en station.")
                elif t - cp["rs_t"] > 330:
                    cp.update(rs=False, in_t=None); self._radio(run, n, "B STATION", f"je n'arrive pas à tenir mon poste, encore à {int(err)} m.")
        if auto:                                               # routes de collision entre navires
            names = list(S); W = run.setdefault("warned", {})
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    sa, sb = self.ros.st.get(a), self.ros.st.get(b)
                    if not sa or not sb or math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]) > 230: continue
                    if t - W.get((a, b), -1e9) < 90: continue
                    W[(a, b)] = t; who, other = (b, a) if a == me else (a, b)
                    self._radio(run, who, "EMERG C", f"route de collision avec {other.capitalize()}, je m'écarte.", "urgence")

    def control(self, run):
        g = self.ros.st.get(run["guide"]); S = run["ships"]
        if not g: return
        man = run.get("manual"); me = run["player"]
        if man: hcap, hv = self._helm_tick(run)
        if man and me == run["guide"]: run["gcap"], run["gspeed"] = hcap, hv      # le guide est a la main : la formation le suit
        S[run["guide"]]["dI"] = self.ros.carrot(run["guide"], run["gcap"], run["gspeed"], S[run["guide"]]["dI"])
        r = math.radians(g["hdg"] if run.get("axis") is None else run["axis"]); u = (math.sin(r), math.cos(r)); sd = (math.cos(r), -math.sin(r))
        form = self._slots(run)
        for n, sh in S.items():
            s = self.ros.st.get(n)
            if n == run["guide"] or not s: continue
            sa, sc = form[n]
            sx, sy = g["x"] + sa * u[0] + sc * sd[0], g["y"] + sa * u[1] + sc * sd[1]
            vx, vy = sx - s["x"], sy - s["y"]; dist = math.hypot(vx, vy)
            sh["err"] = dist; sh["slot"] = (sx, sy)
            if man and n == me:
                course, v = hcap, hv
            elif sh["mode"] == "formation" and dist > 120:
                # loin de son poste : le navire glisse vers lui (plus vite si le poste est devant ou par le travers,
                # en ralentissant s'il est derriere), sans jamais faire demi-tour
                gr = math.radians(g["hdg"]); gu = (math.sin(gr), math.cos(gr)); gs_ = (math.cos(gr), -math.sin(gr))
                e_al = vx * gu[0] + vy * gu[1]; e_cr = vx * gs_[0] + vy * gs_[1]
                al = g["sog"] + clamp(0.045 * e_al, -max(g["sog"] - 0.8, 0.0), 13.0); cr = clamp(0.045 * e_cr, -13.0, 13.0)
                wx, wy = al * gu[0] + cr * gs_[0], al * gu[1] + cr * gs_[1]
                for n2 in S:                                  # s'ecarter d'un navire trop proche (moins de 260 m)
                    o2 = self.ros.st.get(n2)
                    if n2 == n or not o2: continue
                    ox, oy = s["x"] - o2["x"], s["y"] - o2["y"]; od = math.hypot(ox, oy)
                    if 1.0 < od < 260.0:                       # rayon inferieur a l'espacement en station (300 m)
                        f = 16.0 * ((260.0 - od) / 260.0) ** 0.6; wx += f * ox / od; wy += f * oy / od
                course = math.degrees(math.atan2(wx, wy)) % 360
                v = clamp(math.hypot(wx, wy), 0.8, VMAX)
            elif sh["mode"] == "formation":
                ea = sa - ((s["x"] - g["x"]) * u[0] + (s["y"] - g["y"]) * u[1])
                brg = math.degrees(math.atan2(vx, vy)) % 360
                w = clamp(dist / 200.0, 0.0, 1.0)
                course = (g["hdg"] + w * angdiff(brg, g["hdg"])) % 360
                v = clamp(run["gspeed"] + clamp(0.02 * ea, -3.0, 5.0) + (2.0 if dist > 300 else 0.0), 1.5, VMAX)
            else:
                course, v = sh["cap"], sh["v"]
            sh["dI"] = self.ros.carrot(n, course, v, sh["dI"])

    def observe(self, run, t, dt):
        S = run["ships"]; names = list(S)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                sa, sb = self.ros.st.get(a), self.ros.st.get(b)
                if sa and sb: run["min_ship"] = min(run["min_ship"], math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]))
        for cid, c in run["contacts"].items():
            c["x"] += c["vx"] * dt; c["y"] += c["vy"] * dt
            me = self.ros.st.get(run["player"])
            if me:
                d = math.hypot(c["x"] - me["x"], c["y"] - me["y"]) / NM
                run["min_cpa"][cid] = min(run["min_cpa"].get(cid, 1e9), d)

    def _eval(self, run):
        res = []
        for a in run["sc"].get("attendu", []):
            ok, when = False, None
            if "repousse" in a:
                c = run["contacts"].get(a["repousse"]); ok = bool(c and c["etat"] == "repousse"); when = c.get("rep_t") if ok else None
            elif "garde_nm" in a:
                c = run["contacts"].get(a["piste"]); ok = bool(c) and run["min_cpa"].get(a["piste"], 1e9) >= a["garde_nm"]
            elif "ordre" in a:
                for p in run["plog"]:
                    if any(o["type"] == a["ordre"] for o in p["orders"]) and p["t"] <= a["avant_t"] + TOL:
                        ok, when = True, p["t"]; break
                    if any(o["type"] == a["ordre"] for o in p["orders"]) and p["t"] > a["avant_t"]: when = p["t"]
                if not ok and a["ordre"] == "ACK":
                    ok = any(o["type"] in ("ACK", "EMERG") for p in run["plog"] if p["t"] <= a["avant_t"] + TOL for o in p["orders"])
            elif "classe" in a:
                c = run["contacts"].get(a["classe"])
                ok = bool(c and c["cls"] == a["cls"])
            res.append({"texte": a["texte"], "avant_t": a.get("avant_t", run["sc"]["duree_s"]), "ok": ok, "t": None if when is None else round(when)})
        return res + [dict(x) for x in run.get("dyn", [])]

    def finish(self, run):
        run["ended"] = True
        res = self._eval(run)
        run["debrief"] = {"checks": res, "score": sum(1 for r in res if r["ok"]), "total": len(res),
                          "min_ship_m": None if run["min_ship"] > 1e8 else int(run["min_ship"]),
                          "min_cpa": {k: round(v, 2) for k, v in run["min_cpa"].items()},
                          "classes": {k: {"choisie": c["cls"], "reelle": c["cls_reel"]} for k, c in run["contacts"].items()}}
        self.say("SYSTÈME", "TOUS", "", "Fin du scénario.", "info")

    # --- etat pour l'interface
    def state(self):
        with self.lock:
            run = self.run
            base = {"phase": self.phase, "steps": self.steps, "now": time.time()}
            if not run: return base
            t = time.time() - run["t0"]; me = run["player"]; guide = run["guide"]
            ships = []
            for n, sh in run["ships"].items():
                s = self.ros.st.get(n)
                if not s: continue
                if n == guide: etat = "Guide"
                elif sh["mode"] == "pending": etat = "Hors formation"
                elif run.get("capt", {}).get(n, {}).get("task") == "intercept": etat = "Reconnaissance " + run["capt"][n]["target"]
                elif sh["mode"] == "free": etat = "Libre"
                else: etat = "En station" if sh.get("err", 0) < 150 else ("Hors formation" if sh.get("err", 0) > 600 else "Rejoint")
                if n == me: etat = "Vous" if n != guide else "Vous (guide)"
                ships.append({"name": n, "x": s["x"], "y": s["y"], "hdg": s["hdg"], "sog": s["sog"], "role": sh["role"], "etat": etat,
                              "etat_c": ("Guide" if n == guide else etat)})
            own = next((s for s in ships if s["name"] == me), None)
            contacts = []
            for c in run["contacts"].values():
                info = sim.cpa_now(own, c) if own else {}
                contacts.append({"id": c["id"], "type": c["type"], "x": c["x"], "y": c["y"], "cap": round(c["cap"]), "vit": c["vit"], "cls": c["cls"], "etat": c.get("etat"),
                                 "range_nm": info.get("range_nm"), "brg": info.get("brg"), "cpa_nm": info.get("cpa_nm"), "tcpa_min": info.get("tcpa_min")})
            plan = [{"t": m["t"], "en": m["en"], "fr": m["fr"]} for m in run["msgs"] if m["kind"] == "plan"]
            return {**base, "t": round(t, 1), "duree": run["sc"]["duree_s"], "titre": run["sc"]["titre"], "player": me, "guide": guide, "form": run["form"],
                    "gcap": run["gcap"], "gspeed_kn": run["gspeed"] / KN, "ships": ships, "contacts": contacts, "msgs": run["msgs"][-40:], "plan": plan[-3:],
                    "pending": [{"fr": mtp.fr_order(p["orders"][0])} for p in run["pending"]], "ended": run["ended"], "debrief": run["debrief"],
                    "attendu": self._eval(run), "auto": bool(run.get("auto")), "requests": list(run.get("requests", {}).values()), "manual": bool(run.get("manual")),
                    "helm": {"cap": round(run["helm"]["cap"], 1), "kn": round(run["helm"]["kn"], 1), "rudder": run["helm"]["rudder"]},
                    "station": (lambda sh: None if me == guide or "slot" not in sh else {"x": sh["slot"][0], "y": sh["slot"][1], "err": round(sh.get("err", 0))})(run["ships"][me]),
                    "tasks": {n: cp["target"] for n, cp in run.get("capt", {}).items() if cp["task"] == "intercept"}}

    def sim_state_for_calc(self):
        with self.lock:
            run = self.run
            ships = [{"name": n, "x": s["x"], "y": s["y"], "hdg": s["hdg"], "sog": s["sog"]} for n in run["ships"] for s in [self.ros.st.get(n)] if s]
            contacts = [{"id": c["id"], "x": c["x"], "y": c["y"], "vx": c["vx"], "vy": c["vy"], "cls": c["cls"]} for c in run["contacts"].values()]
            return ships, contacts

    def simulate(self, text):
        run = self.run
        if not run: return {"ok": False, "error": "Aucun scénario en cours."}
        pr = mtp.parse(text, list(run["ships"]))
        if not pr["ok"]: return {"ok": False, "error": pr["error"], "hint": pr["hint"]}
        mot = [o for o in pr["orders"] if o["type"] in ("CORPEN", "TURN", "SPEED")]
        if not mot: return {"ok": False, "error": "Rien à simuler : utilise CORPEN, TURN ou SPEED.", "hint": "Exemple : TURN 30 STBD"}
        ships, contacts = self.sim_state_for_calc()
        to = pr["to"]
        if run["player"] != run["guide"] and to == ["TOUS"]: to = [run["player"].upper()]
        g = sim.ghost(ships, to, mot, contacts, 900)
        return {"ok": True, "to": to, "fr": mtp.fr_message(pr["to"], pr["orders"]), **g}

    def recommend(self):
        run = self.run
        if not run: return []
        ships, contacts = self.sim_state_for_calc()
        for c in contacts: c["cls"] = run["contacts"][c["id"]]["cls"]
        st = {"ships": [dict(s, etat=next((x["etat"] for x in self.state()["ships"] if x["name"] == s["name"]), "")) for s in ships],
              "contacts": contacts}
        return reco.recommend(st, run["player"], run["guide"], run["pending"], run["reported"])


H = None


class Handler(http.server.BaseHTTPRequestHandler):
    need_password = False               # vrai sur le port public (acces par tunnel)

    def log_message(self, *a): pass

    def _auth(self):
        """Port public : mot de passe obligatoire (authentification HTTP de base)."""
        if not self.need_password: return True
        import base64, hmac
        h = self.headers.get("Authorization", ""); ok = False
        if h.startswith("Basic "):
            try: ok = hmac.compare_digest(base64.b64decode(h[6:]).decode("utf-8", "ignore").split(":", 1)[-1], PUBLIC_PASSWORD)
            except Exception: ok = False
        if not ok:
            self.send_response(401); self.send_header("WWW-Authenticate", 'Basic realm="HANNIBAL X", charset="UTF-8"')
            self.send_header("Content-Length", "0"); self.end_headers()
        return ok

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def _file(self, path, ctype):
        try: b = open(path, "rb").read()
        except OSError: self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if not self._auth(): return
        p = urllib.parse.urlparse(self.path).path
        web = os.path.join(HERE, "web")
        if p in ("/", "/index.html"): return self._file(os.path.join(web, "index.html"), "text/html; charset=utf-8")
        if p == "/console": return self._file(os.path.join(web, "console.html"), "text/html; charset=utf-8")
        if p in ("/vue3d", "/3d"): return self._file(os.path.join(web, "view3d.html"), "text/html; charset=utf-8")
        if p == "/registre": return self._file(os.path.join(web, "registre.html"), "text/html; charset=utf-8")
        if p == "/api/audit": return self._json({"items": H.audit.tail(400)})
        if p == "/api/hx": return self._json(hxbridge.call("/health", timeout=4))
        if p.startswith("/api/audio/"):
            f = H.audit.audio_path(p[11:].replace(".wav", ""))
            return self._file(f, "audio/wav") if f else self.send_error(404)
        if p.startswith("/static/"):
            f = os.path.normpath(os.path.join(web, p[8:]))
            if f.startswith(web): return self._file(f, "text/css" if f.endswith(".css") else "application/javascript" if f.endswith(".js") else "application/octet-stream")
        if p == "/api/scenarios": return self._json(H.scenarios())
        if p == "/api/state": return self._json(H.state())
        if p == "/events":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-store"); self.end_headers()
            try:
                while True:
                    self.wfile.write(("data: " + json.dumps(H.state(), ensure_ascii=False) + "\n\n").encode()); self.wfile.flush(); time.sleep(0.25)
            except Exception: return
        self.send_error(404)

    def do_POST(self):
        if not self._auth(): return
        p = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(n)
        if p == "/api/voice":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self._json(H.voice(raw, (q.get("target") or ["TOUS"])[0]))
        try: body = json.loads(raw or b"{}")
        except Exception: body = {}
        if p == "/api/interpret": return self._json(H.interpret_text(body.get("text", ""), body.get("target", "TOUS"), body.get("parent")))
        if p == "/api/confirm": return self._json(H.confirm(body.get("id"), body.get("decision")))
        if p == "/api/explain": return self._json(H.explain(body.get("id")))
        if p == "/api/helm": return self._json(H.helm(body))
        if p == "/api/reply": return self._json(H.reply(str(body.get("ship", "")).lower(), bool(body.get("yes"))))
        if p == "/api/start":
            H.start(body.get("scenario"), body.get("player", "hannibal"), False, bool(body.get("auto", False)), bool(body.get("manual", False))); return self._json({"ok": True})
        if p == "/api/auto": return self._json({"ok": H.set_auto(body.get("on"))})
        if p == "/api/stop": H.stop(); return self._json({"ok": True})
        if p == "/api/unity_ready": H.unity_ok.set(); return self._json({"ok": True})
        if p == "/api/order": return self._json(H.player_order(body.get("text", "")))
        if p == "/api/simulate": return self._json(H.simulate(body.get("text", "")))
        if p == "/api/recommend": return self._json({"items": H.recommend()})
        if p == "/api/classify": return self._json({"ok": H.classify(body.get("id"), body.get("cls"))})
        self.send_error(404)


def main():
    global H
    rclpy.init(); H = Hannibal()
    ex = SingleThreadedExecutor(); ex.add_node(H.ros)
    threading.Thread(target=ex.spin, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler); srv.daemon_threads = True
    if PUBLIC_PORT and PUBLIC_PASSWORD:
        # second port, ecoute locale seulement, avec mot de passe : c'est le seul qu'un tunnel doit exposer
        class PublicHandler(Handler): need_password = True
        pub = http.server.ThreadingHTTPServer(("127.0.0.1", PUBLIC_PORT), PublicHandler); pub.daemon_threads = True
        threading.Thread(target=pub.serve_forever, daemon=True).start()
        print(f"Port public protégé par mot de passe : 127.0.0.1:{PUBLIC_PORT}", flush=True)
    signal.signal(signal.SIGTERM, lambda s, f: (H.stop(), os._exit(0)))
    print(f"Hannibal sur http://0.0.0.0:{PORT}", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: H.stop()


if __name__ == "__main__":
    main()
