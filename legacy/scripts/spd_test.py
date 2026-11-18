import math, signal, time, os
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
NAMES = ["alfa", "hannibal", "charlie", "delta"]
DISTS = {"alfa": 8.0, "hannibal": 15.0, "charlie": 30.0, "delta": 1000.0}
SDF = """<lotus_param><render_interface><publish_render>true</publish_render><renderer_type_name>fremm</renderer_type_name></render_interface><waypoint_follower><follower><loop>false</loop><range_tolerance>1</range_tolerance><line><direction>0</direction><length>5000</length></line></follower></waypoint_follower></lotus_param>"""
class T(Node):
    def __init__(self):
        super().__init__('spd_test', namespace='/lotusim')
        self.create_subscription(VesselPositionArray, f'/{WORLD}/poses', self.on_poses, 10)
        self.arr = ActionClient(self, MASCmdArray, f'/{WORLD}/mas_cmd_array')
        self.pos = {}; self.cli = {}
    def on_poses(self, msg):
        for v in msg.vessels:
            self.pos[v.vessel_name] = (v.geo_point.latitude, v.geo_point.longitude, v.speed_over_ground)
    def send(self, cmds):
        g = MASCmdArray.Goal()
        for c in cmds: g.cmd.append(c)
        self.arr.wait_for_server()
        f = self.arr.send_goal_async(g); rclpy.spin_until_future_complete(self, f)
        h = f.result()
        if h and h.accepted: rclpy.spin_until_future_complete(self, h.get_result_async())
    def spawn(self):
        cmds = []
        for i, n in enumerate(NAMES):
            m = MASCmdMsg(); m.cmd_type = MASCmdMsg.CREATE_CMD; m.model_name = "fremm"; m.vessel_name = n
            m.vessel_position = Pose(); m.vessel_position.position.x = -i*400.0; m.vessel_position.position.y = -300.0
            m.vessel_position.orientation.w = 0.7071068; m.vessel_position.orientation.z = 0.7071068
            m.sdf_string = SDF; cmds.append(m)
        self.send(cmds)
    def find(self, n):
        for s, _ in self.get_service_names_and_types():
            if s.endswith(f"/{n}/waypoints"): return s
    def carrot(self, n, d):
        if n not in self.pos: return
        if n not in self.cli:
            s = self.find(n)
            if not s: return
            self.cli[n] = self.create_client(SetWaypoints, s)
        lat, lon, _ = self.pos[n]
        r = SetWaypoints.Request(); r.loop = False
        r.path = [GeoPoint(latitude=lat + d/M, longitude=lon, altitude=0.0)]
        self.cli[n].call_async(r)
    def delete(self):
        cmds = []
        for n in NAMES:
            m = MASCmdMsg(); m.cmd_type = MASCmdMsg.DELETE_CMD; m.vessel_name = n; cmds.append(m)
        self.send(cmds)
def main():
    rclpy.init(); t = T(); stop = {"v": False}
    signal.signal(signal.SIGINT, lambda s, f: stop.update(v=True))
    t.spawn(); t0 = time.time(); last_log = 0; last_c = 0
    while rclpy.ok() and not stop["v"] and time.time()-t0 < float(os.environ.get('DUR', '70')):
        rclpy.spin_once(t, timeout_sec=0.05); now = time.time()
        if now-last_c > 0.5:
            last_c = now
            for n in NAMES: t.carrot(n, DISTS[n])
        if now-last_log > 5:
            last_log = now
            print(f"t={now-t0:4.0f}s " + "  ".join(f"{n}(D={DISTS[n]:.0f}): {t.pos[n][2]:.2f} m/s" for n in NAMES if n in t.pos), flush=True)
    t.delete(); t.destroy_node(); rclpy.shutdown()
main()
