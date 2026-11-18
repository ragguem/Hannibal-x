import os, time, rclpy
from rclpy.node import Node
from lotusim_msgs.msg import RendererCmd
from geometry_msgs.msg import Pose

WORLD = os.environ.get('WORLD', 'defenseScenario')
OBJ = os.environ.get('OBJ', 'fremm')
NAMES = ['alfa', 'hannibal', 'charlie', 'delta']

rclpy.init()
n = Node('render_register')
pub = n.create_publisher(RendererCmd, f'/{WORLD}/renderer_cmd', 10)
time.sleep(2)
for v in NAMES:
    m = RendererCmd()
    m.cmd_type = RendererCmd.CREATE_CMD
    m.renderer_obj_name = OBJ
    m.vessel_name = v
    m.vessel_position = Pose()
    pub.publish(m)
    print('RendererCmd CREATE', v, OBJ, flush=True)
    time.sleep(0.3)
time.sleep(1)
rclpy.shutdown()
