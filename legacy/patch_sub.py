p='/build/src/ROS-TCP-Endpoint/ros_tcp_endpoint/subscriber.py'
s=open(p).read()
helper='''
import os, math
_YAW = math.radians(float(os.environ.get('YAW_OFFSET_DEG', '0')))

def _rot(q):
    # q_new = Rz(_YAW) * q
    cw, sz = math.cos(_YAW / 2.0), math.sin(_YAW / 2.0)
    w = cw * q.w - sz * q.z
    x = cw * q.x - sz * q.y
    y = cw * q.y + sz * q.x
    z = cw * q.z + sz * q.w
    q.w, q.x, q.y, q.z = w, x, y, z

def _to_old(d):
    from lotusim_old_msgs.msg import VesselPositionArray2 as A, VesselPosition2 as V
    o = A()
    o.header = d.header
    for v in d.vessels:
        n = V()
        n.vessel_name = v.vessel_name
        n.pose = v.pose
        _rot(n.pose.orientation)
        n.geo_point = v.geo_point
        o.vessels.append(n)
    return o

'''
s=s.replace('class RosSubscriber(RosReceiver):', helper+'class RosSubscriber(RosReceiver):',1)
s=s.replace('        self.tcp_server.send_unity_message(self.topic, data)',
 "        if self.topic.endswith('renderer_poses'):\n            data = _to_old(data)\n        self.tcp_server.send_unity_message(self.topic, data)",1)
open(p,'w').write(s)
