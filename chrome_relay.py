#!/usr/bin/env python3
"""Tiny local proxy relay for Echo's Google Chrome.

Why this exists (2026-10-19): this VM's egress proxy intermittently
refuses CONNECT tunnels with 403 when a client opens many at once —
and a real web browser opens a burst of tunnels on every page load,
so Chrome's page loads kept failing with ERR_TUNNEL_CONNECTION_FAILED
while single-shot tools (curl, urllib) went through fine. This relay
sits between Chrome and the egress proxy: it limits how many tunnel
handshakes are in flight at once and patiently retries a refused
CONNECT a few times before giving up. Chrome points at
127.0.0.1:18081; the relay talks to the real egress proxy
(hatch-egress-proxy:3128). The concurrency limit applies only to the
handshake — an established tunnel holds no slot while it streams.
"""
import socket
import socketserver
import threading
import time

LISTEN = ("127.0.0.1", 18081)
UPSTREAM_HOST = "hatch-egress-proxy"
UPSTREAM_PORT = 3128
MAX_HANDSHAKES = 3
CONNECT_RETRIES = 8

_sem = threading.Semaphore(MAX_HANDSHAKES)


def upstream_socket():
    """Connect to the egress proxy, preferring its IPv4 address."""
    infos = socket.getaddrinfo(UPSTREAM_HOST, UPSTREAM_PORT,
                               type=socket.SOCK_STREAM)
    infos.sort(key=lambda i: 0 if i[0] == socket.AF_INET else 1)
    last = None
    for fam, typ, proto, _, addr in infos:
        s = None
        try:
            s = socket.socket(fam, typ, proto)
            s.settimeout(10)
            s.connect(addr)
            return s
        except OSError as e:
            last = e
            try:
                if s:
                    s.close()
            except Exception:
                pass
    raise last or OSError("no upstream address")


def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        try:
            b.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def read_until(sock, marker, limit=262144):
    buf = b""
    while marker not in buf and len(buf) < limit:
        chunk = sock.recv(16384)
        if not chunk:
            break
        buf += chunk
    return buf


def is_200(status_line):
    return b" 200 " in status_line or status_line.rstrip().endswith(b" 200")


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        client = self.request
        client.settimeout(120)
        try:
            first = read_until(client, b"\r\n\r\n")
            if not first:
                return
            head = first.split(b"\r\n\r\n", 1)[0]
            method = head.split(b" ", 1)[0].upper()
            if method == b"CONNECT":
                self.handle_connect(client, first)
            else:
                self.handle_http(client, first)
        except OSError:
            pass
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _handshake(self, request_head):
        """Send request_head upstream under the handshake limit; return
        (socket, response_bytes) on a 200/any final response for HTTP,
        retrying refused (403) CONNECTs. Caller owns the socket."""
        for attempt in range(CONNECT_RETRIES):
            up = None
            try:
                with _sem:
                    up = upstream_socket()
                    up.sendall(request_head)
                    resp = read_until(up, b"\r\n\r\n")
                status = resp.split(b"\r\n", 1)[0] if resp else b""
                return up, resp, status
            except OSError:
                try:
                    if up:
                        up.close()
                except Exception:
                    pass
                time.sleep(0.3 * (attempt + 1))
        return None, b"", b""

    def handle_connect(self, client, request_head):
        for attempt in range(CONNECT_RETRIES):
            up, resp, status = self._handshake(request_head)
            if up is None:
                break
            if is_200(status):
                client.sendall(resp)
                # Streaming phase: no socket timeouts, or a slow page
                # dies mid-load when an idle recv times out.
                client.settimeout(None)
                up.settimeout(None)
                t = threading.Thread(target=pipe, args=(client, up),
                                     daemon=True)
                t.start()
                pipe(up, client)
                t.join(timeout=5)
                try:
                    up.close()
                except OSError:
                    pass
                return
            # Refused (403) or other: drop it and retry the handshake.
            try:
                up.close()
            except OSError:
                pass
            time.sleep(0.35 * (attempt + 1))
        client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n"
                       b"Content-Length: 0\r\nConnection: close\r\n\r\n")

    def handle_http(self, client, request_bytes):
        # Plain-HTTP proxied request: forward under the handshake limit
        # until response headers arrive; retry a 403 (nothing has been
        # sent to the client yet, so retrying is safe).
        for attempt in range(5):
            up, resp, status = self._handshake(request_bytes)
            if up is None:
                break
            if b" 403 " in status and attempt < 4:
                try:
                    up.close()
                except OSError:
                    pass
                time.sleep(0.35 * (attempt + 1))
                continue
            client.sendall(resp)
            client.settimeout(None)
            up.settimeout(None)
            pipe(up, client)
            try:
                up.close()
            except OSError:
                pass
            return


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    with Server(LISTEN, Handler) as srv:
        print(f"chrome relay listening on {LISTEN[0]}:{LISTEN[1]} "
              f"-> {UPSTREAM_HOST}:{UPSTREAM_PORT}", flush=True)
        srv.serve_forever()
