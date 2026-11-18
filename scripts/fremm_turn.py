import math, signal, time, os
WORLD = os.environ.get('WORLD', 'lotusim'), os
WORLD = os.environ.get('WORLD', 'lotusim')
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geographic_msgs.msg import GeoPoint
from lotusim_msgs.msg import VesselPositionArray
from lotusim_msgs.msg import MASCmd as MASCmdMsg
from lotusim_msgs.action import MASCmdArray
from lotusim_msgs.msg import RendererCmd
from geometry_msgs.msg import Pose
from lotusim_msgs.srv import SetWaypoints

LAT0, LON0 = 1.2605794416, 103.7516212463
SPACING_M, M_PER_DEG = 200.0, 111320.0
NAMES = ["alfa", "hannibal", "charlie", "delta"]
TURN_AT, NEW_HDG, DIST = 20.0, 45.0, 30000.0
SDF = """<lotus_param><render_interface><publish_render>true</publish_render><renderer_type_name>fremm</renderer_type_name></render_interface><waypoint_follower><follower><loop>false</loop><range_tolerance>5</range_tolerance><line><direction>0</direction><length>5000</length></line></follower></waypoint_follower></lotus_param>"""

class T(Node):
    def __init__(self):
        super().__init__('hannibal_turn_test', namespace='/lotusim')
        self.create_subscription(VesselPositionArray, f'/{WORLD}/poses', self.on_poses, 10)
        self.arr = ActionClient(self, MASCmdArray, f'/{WORLD}/mas_cmd_array')
        self.rpub = self.create_publisher(RendererCmd, f'/{WORLD}/renderer_cmd', 10)
        self.pos, self.prev = {}, {}
        self.t0 = None
        self.turned = False
        self.want_turn = False
        self.create_timer(2.0, self.report)

    def on_poses(self, msg):
        for v in msg.vessels:
            self.pos[v.vessel_name] = (v.geo_point.latitude, v.geo_point.longitude, v.speed_over_ground)

    def report(self):
        for n, p in sorted(self.pos.items()):
            q = self.prev.get(n)
            if q:
                dn = (p[0]-q[0])*M_PER_DEG
                de = (p[1]-q[1])*M_PER_DEG*math.cos(math.radians(p[0]))
                hdg = (math.degrees(math.atan2(de, dn)) + 360) % 360
                self.get_logger().info(f"{n}: cap {hdg:5.1f}  sog {p[2]:.1f}")
            self.prev[n] = p
        if self.t0 and not self.turned and time.time() - self.t0 > TURN_AT:
            self.turned = True
            self.want_turn = True

    def send(self, cmds):
        g = MASCmdArray.Goal()
        for c in cmds: g.cmd.append(c)
        self.arr.wait_for_server()
        f = self.arr.send_goal_async(g)
        rclpy.spin_until_future_complete(self, f)
        h = f.result()
        if h and h.accepted:
            rclpy.spin_until_future_complete(self, h.get_result_async())

    def spawn(self):
        cmds = []
        for i, n in enumerate(NAMES):
            m = MASCmdMsg()
            m.cmd_type = MASCmdMsg.CREATE_CMD
            m.model_name = "fremm"
            m.vessel_name = n
            m.vessel_position = Pose(); m.vessel_position.position.x = 0.0 - i*SPACING_M; m.vessel_position.position.y = -300.0; m.vessel_position.position.z = 0.0; m.vessel_position.orientation.w = 0.7071068; m.vessel_position.orientation.z = 0.7071068
            m.sdf_string = SDF
            cmds.append(m)
        self.send(cmds)
        self.t0 = time.time()
        self.get_logger().info("spawn sent")
        time.sleep(1.0)
        for n in (NAMES if os.environ.get('MANUAL_RENDER') else []):
            m = RendererCmd(); m.cmd_type = RendererCmd.CREATE_CMD; m.renderer_obj_name = os.environ.get("OBJ", "fremm"); m.vessel_name = n; m.vessel_position = Pose()
            self.rpub.publish(m)
        self.get_logger().info("renderer cmd sent")

    def find_service(self, name):
        for sname, types in self.get_service_names_and_types():
            if sname.endswith(f"/{name}/waypoints"):
                return sname
        return None

    def turn(self):
        self.get_logger().info(f"=== TURN: cap {NEW_HDG} pour tous ===")
        for n in NAMES:
            sname = self.find_service(n)
            self.get_logger().info(f"{n}: service = {sname}")
            if not sname or n not in self.pos: continue
            lat, lon, _ = self.pos[n]
            h = math.radians(NEW_HDG)
            pt = GeoPoint(latitude=lat + DIST*math.cos(h)/M_PER_DEG,
                          longitude=lon + DIST*math.sin(h)/(M_PER_DEG*math.cos(math.radians(lat))),
                          altitude=0.0)
            cli = self.create_client(SetWaypoints, sname)
            cli.wait_for_service(timeout_sec=3.0)
            req = SetWaypoints.Request()
            req.path = [pt]
            req.loop = False
            fut = cli.call_async(req)
            rclpy.spin_until_future_complete(self, fut, timeout_sec=3.0)
            self.get_logger().info(f"{n}: reponse = {fut.result()}")

    def delete(self):
        cmds = []
        for n in NAMES:
            m = MASCmdMsg(); m.cmd_type = MASCmdMsg.DELETE_CMD; m.vessel_name = n
            cmds.append(m)
        self.send(cmds)

def main():
    rclpy.init()
    t = T()
    stop = {"v": False}
    def h(s, f): stop["v"] = True
    signal.signal(signal.SIGINT, h); signal.signal(signal.SIGTERM, h)
    t.spawn()
    while rclpy.ok() and not stop["v"]:
        rclpy.spin_once(t, timeout_sec=0.1)
        if t.want_turn:
            t.want_turn = False
            t.turn()
    t.delete()
    t.destroy_node()
    if rclpy.ok(): rclpy.shutdown()

main()
