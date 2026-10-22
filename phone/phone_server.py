#!/usr/bin/env python3
"""Echo phone screen — tiny static server + same-origin bridge to Echo.

Serves the phone version of Echo's own screen (this directory) on
127.0.0.1:8798 and pass-through proxies exactly two of Echo's own API
paths to the real Echo server on 127.0.0.1:8790:

    GET  /status  ->  127.0.0.1:8790/status
    POST /chat    ->  127.0.0.1:8790/chat

Why: browsers block cross-origin calls to 8790 (Echo's server sends no
CORS headers), and every existing Echo surface reaches the brain through
a same-origin bridge (the Brain Test page does it via its server
actions). This keeps the page talking to the REAL Echo server with its
real /chat + /status contract — nothing is mocked here.
"""
import http.client
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ECHO_HOST, ECHO_PORT = "127.0.0.1", 8790
PORT = 8798

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/avatar.png": ("avatar.png", "image/png"),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {}
        if body:
            headers["Content-Type"] = self.headers.get(
                "Content-Type", "application/json")
        try:
            conn = http.client.HTTPConnection(ECHO_HOST, ECHO_PORT, timeout=120)
            conn.request(method, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self._send(resp.status, data,
                       resp.getheader("Content-Type") or "application/json")
            conn.close()
        except Exception as e:  # Echo down — say so, never fake it
            self._send(502, ('{"ok": false, "error": "Echo server '
                             'unreachable: %s"}' % e).encode(),
                       "application/json")

    def do_GET(self):
        if self.path == "/status":
            return self._proxy("GET")
        entry = STATIC.get(self.path.split("?")[0])
        if not entry:
            return self._send(404, b"not found", "text/plain")
        fname, ctype = entry
        with open(os.path.join(HERE, fname), "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        if self.path == "/chat":
            return self._proxy("POST")
        self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
