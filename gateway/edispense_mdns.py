# -*- coding: utf-8 -*-
import os, socket, time
from zeroconf import Zeroconf, ServiceInfo

def _detect_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

IP = os.environ.get("EDISPENSE_HOST_IP") or _detect_ip()
NAME = "edispense"

zc = Zeroconf()
addr = socket.inet_aton(IP)

# 1) HTTP服务广播(_http._tcp),很多客户端靠这个发现
http_info = ServiceInfo(
    "_http._tcp.local.",
    "EDispense._http._tcp.local.",
    addresses=[addr], port=80,
    properties={"path": "/"},
    server="edispense.local.",
)
zc.register_service(http_info)
print("mDNS registered: edispense.local ->", IP, "flush")
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    zc.unregister_service(http_info); zc.close()
