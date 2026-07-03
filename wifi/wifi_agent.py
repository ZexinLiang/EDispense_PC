# -*- coding: utf-8 -*-
"""WiFi配置agent: 供RK3588触摸屏调用, 绑内网口137.222, 只做WiFi扫描/连接"""
import os, subprocess, re, json, sys, socket, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND_IP = os.environ.get("EDISPENSE_WIFI_BIND_IP", "192.168.137.1")
PORT = 8765

def _run(args, timeout=30):
    # netsh输出走系统ANSI(中文Win=cp936/gbk)
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    for enc in ("gbk", "utf-8"):
        try:
            return p.stdout.decode(enc)
        except Exception:
            continue
    return p.stdout.decode("gbk", "ignore")

def scan():
    """扫描周边WiFi, 返回[{ssid,signal,band,auth}]"""
    txt = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    nets, cur = [], None
    for line in txt.splitlines():
        line = line.strip()
        m = re.match(r"SSID\s+\d+\s*:\s*(.*)$", line)
        if m:
            if cur and cur["ssid"]:
                nets.append(cur)
            cur = {"ssid": m.group(1).strip(), "signal": "", "band": "", "auth": ""}
            continue
        if cur is None:
            continue
        if "Authentication" in line or "身份验证" in line:
            cur["auth"] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line.startswith("Signal") or line.startswith("信号"):
            if not cur["signal"]:
                cur["signal"] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line.startswith("Band") or "频带" in line or "Band" in line:
            if not cur["band"] and ":" in line:
                cur["band"] = line.split(":", 1)[1].strip()
    if cur and cur["ssid"]:
        nets.append(cur)
    # 去重(同SSID多BSSID只留一个), 按信号排序
    seen = {}
    for n in nets:
        if n["ssid"] not in seen:
            seen[n["ssid"]] = n
    return list(seen.values())

def current_status():
    txt = _run(["netsh", "wlan", "show", "interfaces"])
    ssid, state = "", ""
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("SSID") and "BSSID" not in s:
            ssid = s.split(":", 1)[1].strip() if ":" in s else ""
        elif s.startswith("State") or s.startswith("状态"):
            state = s.split(":", 1)[1].strip() if ":" in s else ""
    ip = ""
    try:
        out = _run(["powershell", "-NoProfile", "-Command",
                    "(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias WLAN -ErrorAction SilentlyContinue).IPAddress"])
        ip = out.strip().splitlines()[0].strip() if out.strip() else ""
    except Exception:
        pass
    return {"ssid": ssid, "state": state, "ip": ip}

def _profile_xml(ssid, pwd):
    # 开放网络无密码
    if pwd:
        sec = ('<security><authEncryption><authentication>WPA2PSK</authentication>'
               '<encryption>AES</encryption><useOneX>false</useOneX></authEncryption>'
               '<sharedKey><keyType>passPhrase</keyType><protected>false</protected>'
               '<keyMaterial>%s</keyMaterial></sharedKey></security>' % pwd)
    else:
        sec = ('<security><authEncryption><authentication>open</authentication>'
               '<encryption>none</encryption><useOneX>false</useOneX></authEncryption></security>')
    import xml.sax.saxutils as sx
    e = sx.escape(ssid)
    return ('<?xml version="1.0"?>'
            '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">'
            '<name>%s</name><SSIDConfig><SSID><name>%s</name></SSID></SSIDConfig>'
            '<connectionType>ESS</connectionType><connectionMode>auto</connectionMode>%s</WLANProfile>'
            % (e, e, sec))

def connect(ssid, pwd):
    import tempfile, os
    xml = _profile_xml(ssid, pwd)
    fd, path = tempfile.mkstemp(suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(xml)
    try:
        _run(["netsh", "wlan", "add", "profile", "filename=" + path, "user=all"])
        _run(["netsh", "wlan", "connect", "name=" + ssid, "ssid=" + ssid])
    finally:
        try: os.remove(path)
        except Exception: pass
    # 轮询等待连上: 必须校验实际连上的SSID==目标SSID(否则连接失败时仍挂在原网络会误判成功)
    target = ssid.strip()
    for _ in range(20):
        time.sleep(1)
        st = current_status()
        state_ok = st["state"].lower().startswith("connect") or "已连接" in st["state"]
        ssid_ok = st["ssid"].strip() == target
        if state_ok and ssid_ok and st["ip"]:
            return {"ok": True, **st}
    st = current_status()
    return {"ok": False, "msg": "未能连接到目标网络(超时或密码错误)", **st}

class H(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/scan"):
            self._send({"networks": scan()})
        elif self.path.startswith("/status"):
            self._send(current_status())
        else:
            self._send({"err": "not found"}, 404)
    def do_POST(self):
        if self.path.startswith("/connect"):
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            self._send(connect(data.get("ssid", ""), data.get("pwd", "")))
        else:
            self._send({"err": "not found"}, 404)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        print(json.dumps(scan(), ensure_ascii=False, indent=2)); sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(current_status(), ensure_ascii=False, indent=2)); sys.exit(0)
    srv = ThreadingHTTPServer((BIND_IP, PORT), H)
    print("wifi_agent on %s:%d" % (BIND_IP, PORT))
    srv.serve_forever()
