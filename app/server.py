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
import mtp, sim, reco

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.environ.get("WORLD", "defenseScenario")
PORT = int(os.environ.get("PORT", "8770"))
ENGINE = os.environ.get("ENGINE_CONTAINER", "lotusim")
RELAY = os.environ.get("RELAY_CONTAINER", "hannibal-relay")
RELAY_IMAGE = os.environ.get("RELAY_IMAGE", "hannibal-jazzy")
YAW_OFFSET = os.environ.get("YAW_OFFSET_DEG", "90")
M, KN, NM = 111320.0, 0.514444, 1852.0
START = (0.0, -300.0)           # position du guide au depart (repere local du monde)
VMAX_GUIDE, VMAX = 8.0, 9.8
FORMS = {
    "column":       {"hannibal": (0, 0), "alfa": (-400, 0), "charlie": (-800, 0), "delta": (-1200, 0)},
    "line_abreast": {"hannibal": (0, 0), "alfa": (0, -400), "charlie": (0, 400), "delta": (0, 800)},
    "screen":       {"hannibal": (0, 0), "alfa": (600, -500), "charlie": (600, 500), "delta": (-500, 0)},
}
SDF = ("<lotus_param><render_interface><publish_render>true</publish_render><renderer_type_name>fremm</renderer_type_name>"
       "</render_interface><waypoint_follower><follower><loop>false</loop><range_tolerance>1</range_tolerance>"
       "<line><direction>0</direction><length>5000</length></line></follower></waypoint_follower></lotus_param>")


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
        super().__init__("hannibal_server", namespace="/lotusim")
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

    def start(self, sid, player, with_unity, auto=False):
        self.auto_req = bool(auto)
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
                   "events": sorted(sc["evenements"], key=lambda e: e["t"]), "contacts": {}, "msgs": [], "pending": [],
                   "reported": set(), "plog": [], "ended": False, "debrief": None, "min_ship": 1e9, "min_cpa": {}, "plan": [], "auto": getattr(self, "auto_req", False)}
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
        if o["type"] == "FORM": run["form"] = o["name"]
        elif o["type"] in ("CORPEN", "TURN", "SPEED"):
            cap, spd = sim.apply_orders(run["gcap"], run["gspeed"], [o]); run["gcap"], run["gspeed"] = cap, clamp(spd, 1.5, VMAX_GUIDE)

    def _free(self, run, n, o):
        sh = run["ships"][n]; s = self.ros.st.get(n)
        base_cap = sh["cap"] if sh["mode"] in ("free", "pending") else (s["hdg"] if s else run["gcap"])
        base_v = sh["v"] if sh["mode"] in ("free", "pending") else (s["sog"] if s else run["gspeed"])
        cap, spd = sim.apply_orders(base_cap, base_v, [o])
        sh.update(mode="free", cap=cap, v=clamp(spd, 1.5, VMAX))

    def _to_pending(self, run, n, o, group):
        sh = run["ships"][n]; s = self.ros.st.get(n)
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
                if t > run["sc"]["duree_s"]: self.finish(run)
        except Exception:
            traceback.print_exc()

    def autopilot(self, run, t):
        """Mode automatique : le navire du joueur agit seul comme un capitaine (accusé, exécution)."""
        if not run.get("auto"): return
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
                p = ev["piste"]; g = self.ros.st.get(guide)
                if not g: continue
                b = math.radians(p["rel"]); d = p["dist_nm"] * NM; cr = math.radians(p["cap"]); v = p["vit_kn"] * KN
                run["contacts"][p["id"]] = {"id": p["id"], "type": p["type"], "x": g["x"] + d * math.sin(b), "y": g["y"] + d * math.cos(b),
                                            "vx": v * math.sin(cr), "vy": v * math.cos(cr), "cls": "inconnu", "cls_reel": p.get("cls_reel", "inconnu"), "t0": t,
                                            "cap": p["cap"], "vit": p["vit_kn"]}
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
            self.say(frm, to[0], en, fr, "urgence" if urgent else "ordre", pending=bool(to_me and mot and me != guide))
            self.execute(to, orders, frm, False)

    def control(self, run):
        g = self.ros.st.get(run["guide"]); S = run["ships"]
        if not g: return
        S[run["guide"]]["dI"] = self.ros.carrot(run["guide"], run["gcap"], run["gspeed"], S[run["guide"]]["dI"])
        r = math.radians(g["hdg"]); u = (math.sin(r), math.cos(r)); sd = (math.cos(r), -math.sin(r))
        form = FORMS[run["form"]]
        for n, sh in S.items():
            s = self.ros.st.get(n)
            if n == run["guide"] or not s: continue
            sa, sc = form[n]
            sx, sy = g["x"] + sa * u[0] + sc * sd[0], g["y"] + sa * u[1] + sc * sd[1]
            vx, vy = sx - s["x"], sy - s["y"]; dist = math.hypot(vx, vy)
            sh["err"] = dist
            if sh["mode"] == "formation":
                ea = sa - ((s["x"] - g["x"]) * u[0] + (s["y"] - g["y"]) * u[1])
                brg = math.degrees(math.atan2(vx, vy)) % 360
                w = clamp(dist / 200.0, 0.0, 1.0)
                course = (g["hdg"] + w * angdiff(brg, g["hdg"])) % 360
                v = clamp(run["gspeed"] + clamp(0.02 * ea, -3.0, 5.0) + (2.0 if dist > 300 else 0.0), 1.5, 10.0)
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
        for a in run["sc"]["attendu"]:
            ok, when = False, None
            if "ordre" in a:
                for p in run["plog"]:
                    if any(o["type"] == a["ordre"] for o in p["orders"]) and p["t"] <= a["avant_t"] + TOL:
                        ok, when = True, p["t"]; break
                    if any(o["type"] == a["ordre"] for o in p["orders"]) and p["t"] > a["avant_t"]: when = p["t"]
                if not ok and a["ordre"] == "ACK":
                    ok = any(o["type"] in ("ACK", "EMERG") for p in run["plog"] if p["t"] <= a["avant_t"] + TOL for o in p["orders"])
            elif "classe" in a:
                c = run["contacts"].get(a["classe"])
                ok = bool(c and c["cls"] == a["cls"])
            res.append({"texte": a["texte"], "avant_t": a["avant_t"], "ok": ok, "t": None if when is None else round(when)})
        return res

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
                elif sh["mode"] == "free": etat = "Libre"
                else: etat = "En station" if sh.get("err", 0) < 150 else ("Hors formation" if sh.get("err", 0) > 600 else "Rejoint")
                if n == me: etat = "Vous" if n != guide else "Vous (guide)"
                ships.append({"name": n, "x": s["x"], "y": s["y"], "hdg": s["hdg"], "sog": s["sog"], "role": sh["role"], "etat": etat,
                              "etat_c": ("Guide" if n == guide else etat)})
            own = next((s for s in ships if s["name"] == me), None)
            contacts = []
            for c in run["contacts"].values():
                info = sim.cpa_now(own, c) if own else {}
                contacts.append({"id": c["id"], "type": c["type"], "x": c["x"], "y": c["y"], "cap": c["cap"], "vit": c["vit"], "cls": c["cls"],
                                 "range_nm": info.get("range_nm"), "brg": info.get("brg"), "cpa_nm": info.get("cpa_nm"), "tcpa_min": info.get("tcpa_min")})
            plan = [{"t": m["t"], "en": m["en"], "fr": m["fr"]} for m in run["msgs"] if m["kind"] == "plan"]
            return {**base, "t": round(t, 1), "duree": run["sc"]["duree_s"], "titre": run["sc"]["titre"], "player": me, "guide": guide, "form": run["form"],
                    "gcap": run["gcap"], "gspeed_kn": run["gspeed"] / KN, "ships": ships, "contacts": contacts, "msgs": run["msgs"][-40:], "plan": plan[-3:],
                    "pending": [{"fr": mtp.fr_order(p["orders"][0])} for p in run["pending"]], "ended": run["ended"], "debrief": run["debrief"],
                    "attendu": self._eval(run), "auto": bool(run.get("auto"))}

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
    def log_message(self, *a): pass

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
        p = urllib.parse.urlparse(self.path).path
        web = os.path.join(HERE, "web")
        if p in ("/", "/index.html"): return self._file(os.path.join(web, "index.html"), "text/html; charset=utf-8")
        if p == "/console": return self._file(os.path.join(web, "console.html"), "text/html; charset=utf-8")
        if p in ("/vue3d", "/3d"): return self._file(os.path.join(web, "view3d.html"), "text/html; charset=utf-8")
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
        p = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length", "0") or 0)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception: body = {}
        if p == "/api/start":
            H.start(body.get("scenario"), body.get("player", "hannibal"), False, bool(body.get("auto", False))); return self._json({"ok": True})
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
    signal.signal(signal.SIGTERM, lambda s, f: (H.stop(), os._exit(0)))
    print(f"Hannibal sur http://0.0.0.0:{PORT}", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: H.stop()


if __name__ == "__main__":
    main()
