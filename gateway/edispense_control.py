# -*- coding: utf-8 -*-
"""EDispense /control backend  (127.0.0.1:8091)

Serves the browser control page and bridges HTTP -> SSH tunnel -> board
127.0.0.1:8931 (ui_cmd_bridge). Reached through edispense_proxy /control prefix.

Routes (prefix NOT stripped by proxy):
  GET  /control            -> control page HTML
  GET  /control/api/state  -> {"op":"query"} snapshot
  POST /control/api/cmd    -> body {"op":"cmd"|"cmd_wait","cmd":N,"args":[...]}
  POST /control/api/ui     -> body {"method":"_cmd_home","args":[...]}
  GET  /control/api/frame  -> grab top-cam frame, returns image/jpeg
"""
import os, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import paramiko

BOARD_HOST = os.environ.get("EDISPENSE_BOARD_HOST", "192.168.137.100")
BOARD_PORT = int(os.environ.get("EDISPENSE_BOARD_PORT", "22"))
BOARD_USER = os.environ.get("EDISPENSE_BOARD_USER", "root")
BOARD_PWD  = os.environ.get("EDISPENSE_BOARD_PWD", "")
BRIDGE     = ("127.0.0.1", 8931)
LISTEN     = ("127.0.0.1", 8091)
FRAME_PATH = "/tmp/web_frame.jpg"

# ---------------- persistent SSH to board ----------------
_ssh_lock = threading.Lock()
_ssh = None

def _get_ssh():
    """Return a live SSHClient, (re)connecting under lock if needed."""
    global _ssh
    with _ssh_lock:
        if _ssh is not None:
            t = _ssh.get_transport()
            if t is not None and t.is_active():
                return _ssh
            try: _ssh.close()
            except Exception: pass
            _ssh = None
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(BOARD_HOST, port=BOARD_PORT, username=BOARD_USER, password=BOARD_PWD,
                  timeout=10, look_for_keys=False, allow_agent=False, banner_timeout=15)
        _ssh = c
        return c

def bridge_send(obj, timeout=8):
    """Open a fresh direct-tcpip channel, send one json line, read one json line."""
    ssh = _get_ssh()
    t = ssh.get_transport()
    ch = t.open_channel("direct-tcpip", BRIDGE, ("127.0.0.1", 0), timeout=timeout)
    try:
        ch.settimeout(timeout)
        ch.sendall((json.dumps(obj) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            d = ch.recv(8192)
            if not d:
                break
            buf += d
        line = buf.split(b"\n", 1)[0]
        return json.loads(line.decode("utf-8", "ignore"))
    finally:
        try: ch.close()
        except Exception: pass

def grab_frame():
    """Ask bridge to snap a frame on board, then pull the jpeg back over SFTP."""
    r = bridge_send({"op": "grab", "path": FRAME_PATH}, timeout=20)
    if not r.get("ok"):
        return None, r
    ssh = _get_ssh()
    sftp = ssh.open_sftp()
    try:
        with sftp.open(FRAME_PATH, "rb") as f:
            data = f.read()
        return data, r
    finally:
        try: sftp.close()
        except Exception: pass

# ---------------- control page ----------------
PAGE = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDispense 控制台</title>
<style>*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
background:linear-gradient(160deg,#1c1c1e,#2c2c2e);color:#f2f2f7;min-height:100vh;padding:20px}
.wrap{max-width:900px;margin:0 auto}
h1{font-size:22px;margin-bottom:16px;font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:rgba(44,44,46,.85);border:1px solid rgba(255,255,255,.08);
border-radius:16px;padding:18px}
.card.full{grid-column:1/-1}
.card h2{font-size:14px;color:#98989f;font-weight:600;margin-bottom:12px;letter-spacing:.5px}
.stat{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stat .k{font-size:11px;color:#98989f}
.stat .v{font-size:20px;font-weight:700;margin-top:2px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}
.on{background:#30d158}.off{background:#ff453a}
button{font-family:inherit;border:none;border-radius:12px;color:#fff;font-size:15px;
font-weight:600;padding:13px 10px;cursor:pointer;transition:filter .15s}
button:active{filter:brightness(.8)}
button:disabled{opacity:.4;cursor:not-allowed}
.b{background:#0a84ff}.g{background:#30d158}.r{background:#ff453a}.gray{background:#48484a}
.amber{background:#ff9f0a}
.row{display:flex;gap:10px;flex-wrap:wrap}
.row>*{flex:1}
input{font-family:inherit;font-size:15px;padding:12px;border-radius:10px;border:1px solid #48484a;
background:#1c1c1e;color:#f2f2f7;width:100%}
label{font-size:12px;color:#98989f;display:block;margin-bottom:5px}
.step-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.step-b{background:#3a3a3c;font-size:14px;padding:11px 4px}
.step-b.sel{background:#0a84ff;box-shadow:0 0 0 2px rgba(10,132,255,.35)}
.jog{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-width:230px;margin:0 auto}
.jog button{padding:15px 4px;font-size:18px}
.jog .sp{visibility:hidden}
.z-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
#log{grid-column:1/-1;font-size:12px;color:#98989f;background:rgba(0,0,0,.25);
border-radius:10px;padding:10px;max-height:140px;overflow:auto;white-space:pre-wrap;font-family:monospace}
#frame{grid-column:1/-1;max-width:100%;border-radius:12px;margin-top:8px;display:none}
.estop{grid-column:1/-1;background:#ff453a;font-size:18px;padding:18px}
.hint{font-size:11px;color:#8e8e93;margin-top:8px;line-height:1.4}
</style></head><body><div class="wrap">
<h1>EDispense 控制台</h1>
<div class="grid">

<div class="card full">
  <h2>实时状态</h2>
  <div class="stat">
    <div><div class="k">X</div><div class="v" id="sx">--</div></div>
    <div><div class="k">Y</div><div class="v" id="sy">--</div></div>
    <div><div class="k">Z</div><div class="v" id="sz">--</div></div>
    <div><div class="k">运动</div><div class="v" id="sbusy" style="font-size:15px">--</div></div>
    <div><div class="k">在线</div><div class="v" id="sonline" style="font-size:15px">--</div></div>
    <div><div class="k">激光测距</div><div class="v" id="slaser" style="font-size:15px">--</div></div>
  </div>
</div>

<button class="estop" onclick="estop()">■ 急停 (ESTOP)</button>

<div class="card full">
  <h2>步进量 (点动步长)</h2>
  <div class="step-grid" id="stepbox"></div>
  <div class="hint">点动 (XY / Z) 按此步长移动。同步板子内部步长设置。</div>
</div>

<div class="card">
  <h2>XY 点动</h2>
  <div class="jog">
    <div class="sp"></div>
    <button class="gray" onclick="jogXY(0,1)">▲ Y+</button>
    <div class="sp"></div>
    <button class="gray" onclick="jogXY(-1,0)">◀ X-</button>
    <div class="sp"></div>
    <button class="gray" onclick="jogXY(1,0)">X+ ▶</button>
    <div class="sp"></div>
    <button class="gray" onclick="jogXY(0,-1)">▼ Y-</button>
    <div class="sp"></div>
  </div>
</div>

<div class="card">
  <h2>Z 轴点动</h2>
  <div class="z-grid" style="margin-top:30px">
    <button class="gray" onclick="jogZ(1)">▲ 抬升 Z+</button>
    <button class="gray" onclick="jogZ(-1)">▼ 下降 Z-</button>
  </div>
</div>

<div class="card full">
  <h2>运动到坐标 (绝对)</h2>
  <div class="row" style="margin-bottom:10px">
    <div><label>X (0-2475)</label><input id="ix" type="number" value="500" min="0" max="2475"></div>
    <div><label>Y (0-2475)</label><input id="iy" type="number" value="500" min="0" max="2475"></div>
    <div><label>Z (0-950)</label><input id="iz" type="number" value="0" min="0" max="950"></div>
  </div>
  <div class="row">
    <button class="b" onclick="gotoXY()">前往 XY</button>
    <button class="amber" onclick="gotoXYZ()">XYZ 联动</button>
  </div>
  <div class="hint">前往XY: 仅移动XY(单帧, 已实测)。XYZ联动: X/Y绝对 + Z由当前位置换算增量, 单帧下发。</div>
</div>

<div class="card">
  <h2>回原点 / 复位</h2>
  <button class="b" style="width:100%" onclick="home()">↺ 回原点 Home</button>
</div>

<div class="card">
  <h2>绝对零点校准</h2>
  <button class="amber" style="width:100%" onclick="calib()">标定当前为零点</button>
  <div class="hint">须先回零。单次上电仅允许校准一次。</div>
</div>

<div class="card">
  <h2>出锡 Squeeze</h2>
  <div class="row" style="margin-bottom:10px">
    <div><label>次数</label><input id="isq" type="number" value="1" min="1" max="20"></div>
  </div>
  <button class="g" style="width:100%" onclick="squeeze()">出锡</button>
</div>

<div class="card">
  <h2>顶部相机</h2>
  <button class="b" style="width:100%" onclick="grab()">拍照取帧</button>
</div>

<img id="frame">
<div id="log">就绪.</div>

</div>
<script>
var BASE="/control";
var last={x:0,y:0,z:0};
var STEPS=[1,5,10,50,100,200,500,1000];
function log(m){var l=document.getElementById("log");
  l.textContent=(new Date().toLocaleTimeString()+"  "+m+"\\n")+l.textContent;}
function poll(){
  fetch(BASE+"/api/state").then(r=>r.json()).then(d=>{
    if(!d.ok){return;}
    last.x=d.x;last.y=d.y;last.z=d.z;
    document.getElementById("sx").textContent=d.x;
    document.getElementById("sy").textContent=d.y;
    document.getElementById("sz").textContent=d.z;
    document.getElementById("sbusy").innerHTML=d.busy?'<span class="dot off"></span>运动中':'<span class="dot on"></span>空闲';
    document.getElementById("sonline").innerHTML=d.online?'<span class="dot on"></span>在线':'<span class="dot off"></span>离线';
    document.getElementById("slaser").textContent=d.laser;
  }).catch(e=>{});
}
function post(path,body){
  return fetch(BASE+path,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)}).then(r=>r.json());
}
function cmd(c,a,wait){return post("/api/cmd",{op:wait?"cmd_wait":"cmd",cmd:c,args:a||[]});}
function ui(m,a){return post("/api/ui",{method:m,args:a||[]});}
function estop(){cmd(2,[],false).then(d=>log("急停: "+JSON.stringify(d)));}
function home(){ui('_cmd_home').then(d=>log("回原点: "+JSON.stringify(d)));}
function calib(){if(!confirm("确认绝对零点校准？须已回零，单次上电仅一次。"))return;
  ui('_cmd_calib_zero').then(d=>log("零点校准: "+JSON.stringify(d)));}
function setStep(v,el){ui('_set_step_size',[v]).then(d=>log("步进量="+v));
  document.querySelectorAll('.step-b').forEach(b=>b.classList.remove('sel'));el.classList.add('sel');}
function jogXY(dx,dy){ui('_cmd_xy_move',[dx,dy]).then(d=>log("XY点动("+dx+","+dy+"): "+JSON.stringify(d)));}
function jogZ(dir){ui('_cmd_z_move',[dir]).then(d=>log("Z点动("+dir+"): "+JSON.stringify(d)));}
function gotoXY(){
  var x=parseInt(document.getElementById("ix").value);
  var y=parseInt(document.getElementById("iy").value);
  if(isNaN(x)||isNaN(y)||x<0||x>2475||y<0||y>2475){log("XY 越界 [0,2475]");return;}
  log("前往 XY ("+x+","+y+") ...");
  cmd(1,[x,y],true).then(d=>log("到位: "+JSON.stringify(d)));
}
function gotoXYZ(){
  var x=parseInt(document.getElementById("ix").value);
  var y=parseInt(document.getElementById("iy").value);
  var z=parseInt(document.getElementById("iz").value);
  if(isNaN(x)||isNaN(y)||x<0||x>2475||y<0||y>2475){log("XY 越界 [0,2475]");return;}
  if(isNaN(z)||z<0||z>950){log("Z 越界 [0,950]");return;}
  var dz=Math.round(z-(last.z||0));
  log("XYZ联动 ("+x+","+y+","+z+") dz="+dz+" ...");
  cmd(8,[x,y,dz],true).then(d=>log("到位: "+JSON.stringify(d)));
}
function squeeze(){
  var n=parseInt(document.getElementById("isq").value)||1;
  cmd(7,[n],false).then(d=>log("出锡x"+n+": "+JSON.stringify(d)));
}
function grab(){
  log("取帧中...");
  var img=document.getElementById("frame");
  img.style.display="block";
  img.src=BASE+"/api/frame?t="+Date.now();
  img.onload=function(){log("取帧完成");};
  img.onerror=function(){log("取帧失败");};
}
(function initSteps(){
  var box=document.getElementById("stepbox");
  STEPS.forEach(function(v){
    var b=document.createElement("button");
    b.className="step-b"+(v===50?" sel":"");
    b.textContent=v;
    b.onclick=function(){setStep(v,b);};
    box.appendChild(b);
  });
})();
poll();setInterval(poll,1500);
</script>
</body></html>"""

# ---------------- HTTP handler ----------------
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8", json.dumps(obj))

    def _read_body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8", "ignore") or "{}")
        except Exception:
            return {}

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p in ("/control", "/control/"):
            return self._send(200, "text/html; charset=utf-8", PAGE)
        if p == "/control/api/state":
            try:
                return self._json(bridge_send({"op": "query"}, timeout=6))
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 502)
        if p == "/control/api/frame":
            try:
                data, meta = grab_frame()
                if data is None:
                    return self._json({"ok": False, "error": meta}, 502)
                return self._send(200, "image/jpeg", data)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 502)
        self.send_error(404)

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        body = self._read_body()
        if p == "/control/api/cmd":
            op = body.get("op", "cmd")
            obj = {"op": op, "cmd": int(body.get("cmd")), "args": body.get("args", []) or []}
            tmo = 60 if op == "cmd_wait" else 8
            try:
                return self._json(bridge_send(obj, timeout=tmo))
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 502)
        if p == "/control/api/ui":
            obj = {"op": "ui", "method": body.get("method"), "args": body.get("args", []) or []}
            try:
                return self._json(bridge_send(obj, timeout=60))
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 502)
        self.send_error(404)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    srv = ThreadingHTTPServer(LISTEN, H)
    print("edispense_control on %s:%d" % LISTEN)
    srv.serve_forever()
