# -*- coding: utf-8 -*-

"""EDispense 80-port reverse proxy.

  http://edispense/ai      -> 127.0.0.1:8080  (offline LLM)

  http://edispense/gerber  -> 127.0.0.1:8090  (Gerber upload -> board)

Absolute-path APIs of the two backends do not overlap, so we route by prefix

without rewriting page HTML. LLM SSE stream is passed through chunk-by-chunk.

"""

import http.client

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN = ("0.0.0.0", 80)

LLM = ("127.0.0.1", 8080)

GERBER = ("127.0.0.1", 8090)

CONTROL = ("127.0.0.1", 8091)

NAV = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>EDispense</title>

<style>*{box-sizing:border-box;margin:0;padding:0}

body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;

background:linear-gradient(160deg,#1c1c1e,#2c2c2e);color:#f2f2f7;min-height:100vh;

display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;padding:24px}

h1{font-size:24px}a.card{display:block;width:280px;max-width:90vw;padding:22px 24px;

background:rgba(44,44,46,.85);border:1px solid rgba(255,255,255,.08);border-radius:18px;

text-decoration:none;color:#f2f2f7}a.card .t{font-size:18px;font-weight:700}

a.card .s{font-size:13px;color:#98989f;margin-top:6px}</style></head>

<body><h1>EDispense</h1>

<a class="card" href="/ai"><div class="t">离线 AI 助手</div><div class="s">断网也能用 /ai</div></a>

<a class="card" href="/gerber"><div class="t">Gerber 上传</div><div class="s">传板到点锡机 /gerber</div></a>

<a class="card" href="/control"><div class="t">运动控制台</div><div class="s">远程操控点锡机 /control</div></a>

</body></html>"""

def route(path):

    """return (host, port, newpath) or None"""

    if path == "/ai" or path.startswith("/ai/") or path.startswith("/ai?"):

        rest = path[3:]

        if not rest.startswith("/"):

            rest = "/" + rest if rest else "/"

        return (LLM[0], LLM[1], rest or "/")

    if path == "/gerber" or path.startswith("/gerber/") or path.startswith("/gerber?"):

        rest = path[7:]

        if not rest.startswith("/"):

            rest = "/" + rest if rest else "/"

        return (GERBER[0], GERBER[1], rest or "/")

    # control page + api: prefix NOT stripped, backend serves full /control path
    if path == "/control" or path.startswith("/control/") or path.startswith("/control?"):
        return (CONTROL[0], CONTROL[1], path)

    # absolute-path APIs (non-overlapping)

    if path.startswith("/v1"):

        return (LLM[0], LLM[1], path)

    if path.startswith("/upload") or path.startswith("/list"):

        return (GERBER[0], GERBER[1], path)

    return None

class H(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"

    def _nav(self):

        body = NAV.encode("utf-8")

        self.send_response(200)

        self.send_header("Content-Type", "text/html; charset=utf-8")

        self.send_header("Content-Length", str(len(body)))

        self.end_headers()

        self.wfile.write(body)

    def _proxy(self):

        if self.path in ("/", ""):

            return self._nav()

        r = route(self.path)

        if r is None:

            self.send_error(404)

            return

        host, port, newpath = r

        length = int(self.headers.get("Content-Length", 0) or 0)

        body = self.rfile.read(length) if length else None

        headers = {k: v for k, v in self.headers.items()

                   if k.lower() not in ("host", "connection")}

        try:

            conn = http.client.HTTPConnection(host, port, timeout=300)

            conn.request(self.command, newpath, body=body, headers=headers)

            resp = conn.getresponse()

        except Exception as e:

            self.send_error(502, "proxy error: %s" % e)

            return

        self.send_response(resp.status)

        cl = resp.getheader("Content-Length")

        for k, v in resp.getheaders():

            if k.lower() in ("transfer-encoding", "connection", "content-length"):

                continue

            self.send_header(k, v)

        if cl is not None:

            self.send_header("Content-Length", cl)

            self.end_headers()

            remaining = int(cl)

            while remaining > 0:

                chunk = resp.read(min(65536, remaining))

                if not chunk:

                    break

                self.wfile.write(chunk)

                remaining -= len(chunk)

        else:

            # unknown length (SSE / stream): close-delimited, flush per chunk

            self.send_header("Connection", "close")

            self.close_connection = True

            self.end_headers()

            while True:

                chunk = resp.read(8192)

                if not chunk:

                    break

                self.wfile.write(chunk)

                self.wfile.flush()

        conn.close()

    do_GET = _proxy

    do_POST = _proxy

    def log_message(self, *a):

        pass

if __name__ == "__main__":

    srv = ThreadingHTTPServer(LISTEN, H)

    print("edispense_proxy on %s:%d" % LISTEN)

    srv.serve_forever()

