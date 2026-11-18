import json, math, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import rclpy
from rclpy.node import Node
from lotusim_msgs.msg import VesselPositionArray

M = 111320.0
STATE, LOCK, ORIGIN = {}, threading.Lock(), {}

class Sub(Node):
    def __init__(self):
        super().__init__('viz_bridge', namespace='/lotusim')
        self.create_subscription(VesselPositionArray, '/lotusim/poses', self.cb, 10)
    def cb(self, msg):
        with LOCK:
            for v in msg.vessels:
                lat, lon = v.geo_point.latitude, v.geo_point.longitude
                if not ORIGIN:
                    ORIGIN.update(lat=lat, lon=lon)
                x = (lon - ORIGIN['lon']) * M * math.cos(math.radians(ORIGIN['lat']))
                y = (lat - ORIGIN['lat']) * M
                s = STATE.get(v.vessel_name, {'hdg': 90.0, 'x': x, 'y': y})
                dx, dy = x - s['x'], y - s['y']
                hdg = s['hdg']
                if math.hypot(dx, dy) > 0.3:
                    hdg = (math.degrees(math.atan2(dx, dy)) + 360) % 360
                STATE[v.vessel_name] = {'x': x, 'y': y, 'hdg': hdg, 'sog': v.speed_over_ground}

HTML = r"""<!doctype html><meta charset=utf-8><title>Hannibal - vue tactique</title>
<style>html,body{margin:0;height:100%;background:#06121c;color:#cfe;font:13px monospace}canvas{display:block}
#h{position:fixed;left:10px;top:8px;background:#0008;padding:6px 10px;border:1px solid #2a4}</style>
<div id=h>HANNIBAL - vue tactique (molette = zoom) - <span id=st>connexion...</span></div><canvas id=c></canvas>
<script>
const c=document.getElementById('c'),g=c.getContext('2d');let scale=0.4,ships={},trails={};
function rs(){c.width=innerWidth;c.height=innerHeight}rs();onresize=rs;
onwheel=e=>{scale*=e.deltaY<0?1.15:0.87;scale=Math.max(0.02,Math.min(5,scale))};
const es=new EventSource('/stream');
es.onopen=()=>document.getElementById('st').textContent='en direct';
es.onmessage=e=>{ships=JSON.parse(e.data);for(const n in ships){(trails[n]=trails[n]||[]).push([ships[n].x,ships[n].y]);if(trails[n].length>600)trails[n].shift()}};
function draw(){
 g.clearRect(0,0,c.width,c.height);const ns=Object.keys(ships);
 let cx=0,cy=0;ns.forEach(n=>{cx+=ships[n].x;cy+=ships[n].y});if(ns.length){cx/=ns.length;cy/=ns.length}
 const sx=x=>c.width/2+(x-cx)*scale, sy=y=>c.height/2-(y-cy)*scale;
 g.strokeStyle='#12303f';g.lineWidth=1;const step=100;
 for(let x=Math.floor((cx-c.width/2/scale)/step)*step;x<cx+c.width/2/scale;x+=step){g.beginPath();g.moveTo(sx(x),0);g.lineTo(sx(x),c.height);g.stroke()}
 for(let y=Math.floor((cy-c.height/2/scale)/step)*step;y<cy+c.height/2/scale;y+=step){g.beginPath();g.moveTo(0,sy(y));g.lineTo(c.width,sy(y));g.stroke()}
 g.fillStyle='#4a7';g.fillText('N ^   grille: 100 m',c.width-150,20);
 ns.forEach(n=>{const s=ships[n],own=n==='hannibal';
  g.strokeStyle=own?'#4fd':'#58a';g.lineWidth=1.5;g.beginPath();
  (trails[n]||[]).forEach((p,i)=>{i?g.lineTo(sx(p[0]),sy(p[1])):g.moveTo(sx(p[0]),sy(p[1]))});g.stroke();
  g.save();g.translate(sx(s.x),sy(s.y));g.rotate(s.hdg*Math.PI/180);
  const L=Math.max(14,150*scale);g.fillStyle=own?'#4fd':'#8cf';
  g.beginPath();g.moveTo(0,-L);g.lineTo(L*0.28,L*0.5);g.lineTo(-L*0.28,L*0.5);g.closePath();g.fill();
  g.strokeStyle='#fd4';g.beginPath();g.moveTo(0,-L);g.lineTo(0,-L-30);g.stroke();g.restore();
  g.fillStyle=own?'#4fd':'#cfe';
  g.fillText(n+'  '+s.hdg.toFixed(0).padStart(3,'0')+'  '+(s.sog*1.944).toFixed(1)+' kn',sx(s.x)+14,sy(s.y)-10)});
 requestAnimationFrame(draw)}
draw();
</script>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            try:
                while True:
                    with LOCK:
                        d = json.dumps(STATE)
                    self.wfile.write(('data: ' + d + '\n\n').encode())
                    self.wfile.flush()
                    time.sleep(0.2)
            except Exception:
                pass
        elif self.path in ('/3d', '/fremm.dae'):
            f = {'/3d': ('3d.html', 'text/html; charset=utf-8'), '/fremm.dae': ('fremm.dae', 'model/vnd.collada+xml')}[self.path]
            b = open('/scripts/web/' + f[0], 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', f[1])
            self.send_header('Content-Length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        else:
            b = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)

def main():
    rclpy.init()
    n = Sub()
    srv = ThreadingHTTPServer(('0.0.0.0', 8765), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print('Vue tactique: http://<ip-serveur>:8765', flush=True)
    rclpy.spin(n)

main()
