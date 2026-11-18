"""Controleur de flotte Hannibal (jalon 1).
Ordres par UDP 127.0.0.1:9100, une ligne JSON par paquet :
  {"type":"CORPEN","cap":90} {"type":"TURN","deg":30,"side":"STBD"}
  {"type":"SPEED","kn":12}   {"type":"FORM","name":"line_abreast"}
TEST=1 joue une sequence de test automatique."""
import math, signal, time, os, json, socket
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geographic_msgs.msg import GeoPoint
from lotusim_msgs.msg import VesselPositionArray
from lotusim_msgs.msg import MASCmd as MASCmdMsg
from lotusim_msgs.action import MASCmdArray
from geometry_msgs.msg import Pose
from lotusim_msgs.srv import SetWaypoints

WORLD = os.environ.get('WORLD', 'defenseScenario')
M = 111320.0
KN = 0.514444
GUIDE = "hannibal"
NAMES = ["hannibal", "alfa", "charlie", "delta"]
FORMS = {  # (devant, tribord) en metres, repere du guide
    "column":       {"hannibal": (0, 0), "alfa": (-400, 0), "charlie": (-800, 0), "delta": (-1200, 0)},
    "line_abreast": {"hannibal": (0, 0), "alfa": (0, -400), "charlie": (0, 400), "delta": (0, 800)},
    "screen":       {"hannibal": (0, 0), "alfa": (600, -500), "charlie": (600, 500), "delta": (-500, 0)},
}
SDF = """<lotus_param><render_interface><publish_render>true</publish_render><renderer_type_name>fremm</renderer_type_name></render_interface><waypoint_follower><follower><loop>false</loop><range_tolerance>1</range_tolerance><line><direction>0</direction><length>5000</length></line></follower></waypoint_follower></lotus_param>"""
VMAX_GUIDE = 8.0   # m/s : laisse de la marge aux escorteurs pour rattraper
DT = 0.5

def clamp(x, a, b): return max(a, min(b, x))

class Fleet(Node):
    def __init__(self):
        super().__init__('hannibal_fleet', namespace='/lotusim')
        self.create_subscription(VesselPositionArray, f'/{WORLD}/poses', self.on_poses, 10)
        self.arr = ActionClient(self, MASCmdArray, f'/{WORLD}/mas_cmd_array')
        self.st = {}          # nom -> dict(x,y,lat,lon,sog,hdg)
        self.cli = {}
        self.dI = {n: 0.0 for n in NAMES}
        self.cap, self.speed, self.form = 0.0, 12*KN, "column"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 9100)); self.sock.setblocking(False)

    def on_poses(self, msg):
        for v in msg.vessels:
            q = v.pose.orientation
            yaw = math.degrees(math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z)))
            self.st[v.vessel_name] = dict(x=v.pose.position.x, y=v.pose.position.y,
                lat=v.geo_point.latitude, lon=v.geo_point.longitude,
                sog=v.speed_over_ground, hdg=(90 - yaw) % 360)

    def send(self, cmds):
        g = MASCmdArray.Goal()
        for c in cmds: g.cmd.append(c)
        self.arr.wait_for_server()
        f = self.arr.send_goal_async(g); rclpy.spin_until_future_complete(self, f)
        h = f.result()
        if h and h.accepted: rclpy.spin_until_future_complete(self, h.get_result_async())

    def spawn(self):
        cmds = []
        for n in NAMES:
            a, c = FORMS[self.form][n]
            m = MASCmdMsg(); m.cmd_type = MASCmdMsg.CREATE_CMD; m.model_name = "fremm"; m.vessel_name = n
            m.vessel_position = Pose()
            m.vessel_position.position.x = float(c); m.vessel_position.position.y = float(-300.0 + a)
            m.vessel_position.orientation.w = 0.7071068; m.vessel_position.orientation.z = 0.7071068
            m.sdf_string = SDF; cmds.append(m)
        self.send(cmds)

    def delete(self):
        self.send([self._del(n) for n in NAMES])
    def _del(self, n):
        m = MASCmdMsg(); m.cmd_type = MASCmdMsg.DELETE_CMD; m.vessel_name = n; return m

    def command(self, c):
        t = c.get("type")
        if t == "CORPEN": self.cap = float(c["cap"]) % 360
        elif t == "TURN":
            s = 1 if c.get("side", "STBD").upper().startswith("S") else -1
            self.cap = (self.cap + s*float(c["deg"])) % 360
        elif t == "SPEED": self.speed = clamp(float(c["kn"])*KN, 1.5, VMAX_GUIDE)
        elif t == "FORM" and c.get("name") in FORMS: self.form = c["name"]
        self.get_logger().info(f"ORDRE {c} -> cap {self.cap:.0f} vit {self.speed/KN:.1f} kn form {self.form}")

    def poll_orders(self):
        try:
            while True:
                data, _ = self.sock.recvfrom(4096)
                try: self.command(json.loads(data.decode()))
                except Exception as e: self.get_logger().warn(f"ordre invalide: {e}")
        except BlockingIOError:
            pass

    def carrot(self, n, course, v_cmd):
        s = self.st[n]
        if n not in self.cli:
            for sn, _ in self.get_service_names_and_types():
                if sn == f"/{WORLD}/{n}/waypoints": self.cli[n] = self.create_client(SetWaypoints, sn)
            if n not in self.cli: return
        if abs(v_cmd - s["sog"]) < 1.5:
            self.dI[n] = clamp(self.dI[n] + 0.15*(v_cmd - s["sog"])*DT, -6, 8)
        D = clamp((v_cmd - 1.6)/0.414 + self.dI[n], 4.0, 80.0)
        diff = ((course - s["hdg"] + 540) % 360) - 180
        r = math.radians(s["hdg"] + clamp(diff, -25.0, 25.0))
        de, dn = D*math.sin(r), D*math.cos(r)
        req = SetWaypoints.Request(); req.loop = False
        req.path = [GeoPoint(latitude=s['lat'] + dn/M, longitude=s['lon'] + de/(M*math.cos(math.radians(s['lat']))), altitude=0.0)]
        fut = self.cli[n].call_async(req)
        self.lastD = (n, round(D,1), round(course), req.path[0].latitude, req.path[0].longitude)
        self.nsent = getattr(self, "nsent", {}); self.nsent[n] = self.nsent.get(n, 0) + 1
        self.nok = getattr(self, "nok", {})
        def _cb(f, n=n):
            try: self.nok[n] = self.nok.get(n, 0) + (1 if f.result().success else 0)
            except Exception as e: self.nok[n] = -1
        fut.add_done_callback(_cb)

    def control(self):
        if GUIDE not in self.st: return None
        g = self.st[GUIDE]
        self.carrot(GUIDE, self.cap, self.speed)
        gh = g["hdg"]
        r = math.radians(gh)
        u = (math.sin(r), math.cos(r)); st = (math.cos(r), -math.sin(r))
        errs = {}
        for n in NAMES:
            if n == GUIDE or n not in self.st: continue
            s = self.st[n]; rel = (s['x']-g['x'], s['y']-g['y'])
            along = rel[0]*u[0] + rel[1]*u[1]; across = rel[0]*st[0] + rel[1]*st[1]
            sa, sc = FORMS[self.form][n]
            ea, ec = sa - along, sc - across
            sx = g["x"] + sa*u[0] + sc*st[0]; sy = g["y"] + sa*u[1] + sc*st[1]
            vx, vy = sx - s["x"], sy - s["y"]; dist = math.hypot(vx, vy)
            brg = math.degrees(math.atan2(vx, vy)) % 360
            w = clamp(dist/200.0, 0.0, 1.0)
            course = (gh + w*(((brg - gh + 540) % 360) - 180)) % 360
            v = clamp(self.speed + clamp(0.02*ea, -3.0, 5.0) + (2.0 if dist > 300 else 0.0), 1.5, 10.0)
            self.carrot(n, course, v); errs[n] = (ea, ec)
        return errs

def main():
    rclpy.init(); f = Fleet(); stop = {"v": False}
    signal.signal(signal.SIGINT, lambda s, fr: stop.update(v=True))
    signal.signal(signal.SIGTERM, lambda s, fr: stop.update(v=True))
    f.spawn(); t0 = time.time(); last = 0; lastlog = 0
    test = os.environ.get('TEST'); script = [(40, {"type":"CORPEN","cap":90}), (100, {"type":"SPEED","kn":15}), (150, {"type":"FORM","name":"line_abreast"}), (230, {"type":"TURN","deg":45,"side":"PORT"}), (290, {"type":"FORM","name":"column"})]
    dur = float(os.environ.get('DUR', '1e9'))
    while rclpy.ok() and not stop["v"] and time.time()-t0 < dur:
        rclpy.spin_once(f, timeout_sec=0.05); now = time.time()
        f.poll_orders()
        if test and script and now-t0 > script[0][0]: f.command(script.pop(0)[1])
        if now-last >= DT:
            last = now; errs = f.control()
            if errs is not None and now-lastlog > 5:
                lastlog = now
                g = f.st[GUIDE]
                print("envoyes", getattr(f, "nsent", {}), "ok", getattr(f, "nok", {}), "dernier", getattr(f, "lastD", None), "guide geo", g["lat"], g["lon"], flush=True)
                print(f"t={now-t0:4.0f}s guide cap {g['hdg']:5.1f} {g['sog']/KN:4.1f}kn | " + " ".join(f"{n}: ec{v[0]:+5.0f} ac{v[1]:+5.0f} {f.st[n]['sog']/KN:4.1f}kn" for n, v in errs.items()), flush=True)
    f.delete(); f.destroy_node(); rclpy.shutdown()
main()
