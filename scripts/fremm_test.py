import math, signal
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geographic_msgs.msg import GeoPoint
from lotusim_msgs.msg import VesselPositionArray
from lotusim_msgs.msg import MASCmd as MASCmdMsg
from lotusim_msgs.action import MASCmdArray

LAT0, LON0 = 1.2605794416, 103.7516212463
SPACING_M = 200.0
M_PER_DEG = 111320.0
NAMES = ["alfa", "hannibal", "charlie", "delta"]
SDF = """
<lotus_param>
  <waypoint_follower>
    <follower>
      <loop>false</loop>
      <range_tolerance>5</range_tolerance>
      <line>
        <direction>0</direction>
        <length>5000</length>
      </line>
    </follower>
  </waypoint_follower>
</lotus_param>
"""

class T(Node):
    def __init__(self):
        super().__init__('hannibal_fremm_test', namespace='/lotusim')
        self.create_subscription(VesselPositionArray, '/lotusim/poses', self.on_poses, 10)
        self.arr = ActionClient(self, MASCmdArray, '/lotusim/mas_cmd_array')
        self.pos, self.start = {}, {}
        self.create_timer(2.0, self.report)

    def on_poses(self, msg):
        for v in msg.vessels:
            p = (v.geo_point.latitude, v.geo_point.longitude, v.speed_over_ground)
            self.pos[v.vessel_name] = p
            self.start.setdefault(v.vessel_name, p)

    def report(self):
        for n, p in sorted(self.pos.items()):
            s = self.start[n]
            dy = (p[0] - s[0]) * M_PER_DEG
            dx = (p[1] - s[1]) * M_PER_DEG * math.cos(math.radians(p[0]))
            self.get_logger().info(f"{n}: moved {math.hypot(dx, dy):7.1f} m  (east {dx:7.1f}, north {dy:7.1f})  sog {p[2]:.2f}")

    def send(self, cmds):
        g = MASCmdArray.Goal()
        for c in cmds:
            g.cmd.append(c)
        self.arr.wait_for_server()
        f = self.arr.send_goal_async(g)
        rclpy.spin_until_future_complete(self, f)
        h = f.result()
        if h and h.accepted:
            r = h.get_result_async()
            rclpy.spin_until_future_complete(self, r)

    def spawn(self):
        cmds = []
        for i, n in enumerate(NAMES):
            m = MASCmdMsg()
            m.cmd_type = MASCmdMsg.CREATE_CMD
            m.model_name = "fremm"
            m.vessel_name = n
            m.geo_point = GeoPoint(latitude=LAT0, longitude=LON0 - i * SPACING_M / M_PER_DEG, altitude=0.0)
            m.sdf_string = SDF
            cmds.append(m)
        self.send(cmds)
        self.get_logger().info("spawn sent")

    def delete(self):
        cmds = []
        for n in NAMES:
            m = MASCmdMsg()
            m.cmd_type = MASCmdMsg.DELETE_CMD
            m.vessel_name = n
            cmds.append(m)
        self.send(cmds)

def main():
    rclpy.init()
    t = T()
    stop = {"v": False}
    def h(s, f): stop["v"] = True
    signal.signal(signal.SIGINT, h)
    signal.signal(signal.SIGTERM, h)
    t.spawn()
    while rclpy.ok() and not stop["v"]:
        rclpy.spin_once(t, timeout_sec=0.1)
    t.get_logger().info("deleting vessels")
    t.delete()
    t.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

main()
