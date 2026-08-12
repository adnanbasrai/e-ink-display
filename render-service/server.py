#!/usr/bin/env python3
"""SubwayBoard preview render service.

    POST /preview   { "config": <device-config> }  ->  image/png
    GET  /health                                    ->  ok

Reuses the emulator's fetch+render pipeline so previews are pixel-identical to
the panel. Stdlib + Pillow only (same as the emulator).

    python3 server.py            # http://127.0.0.1:8090
    python3 server.py 9090       # custom port
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Reuse the emulator modules (renderer + fetch loop).
_EMU = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "emulator")
sys.path.insert(0, _EMU)
import board_data                        # noqa: E402
from adapter import cfg_from_device      # noqa: E402

# Local dev binds loopback on 8090; a container sets PORT + RENDER_HOST=0.0.0.0.
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8090"))
HOST = os.environ.get("RENDER_HOST", "127.0.0.1")

# A brief shared cache over the upstream feeds so a before+after preview (two
# renders in quick succession) doesn't re-download the ~960 KB CitiBike feed and
# the MTA feeds twice. Patches board_data._fetch, which its methods call.
_cache = {}
_cache_lock = threading.Lock()
_TTL = 30.0
_orig_fetch = board_data._fetch


def _cached_fetch(url, timeout=15):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < _TTL:
            return hit[1]
    data = _orig_fetch(url, timeout)
    with _cache_lock:
        _cache[url] = (now, data)
    return data


board_data._fetch = _cached_fetch


def render_config(config):
    cfg = cfg_from_device(config)
    state = board_data.BoardState(config=cfg, log=lambda *a, **k: None)
    state.update_weather()
    state.update_citibike()
    state.update_arrivals(with_alerts=True)
    return state.render_png()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send(200, "text/plain", b"render service ok")
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if self.path != "/preview":
            return self._send(404, "text/plain", b"not found")
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            config = body.get("config") or body
            png = render_config(config)
            self._send(200, "image/png", png)
        except Exception as e:
            self._send(500, "text/plain", ("render error: %s" % e).encode())


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("render service on http://%s:%d" % (HOST, PORT), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
