"""SubwayBoard e-ink emulator server.

Runs the same fetch/render loop the ESP32 firmware runs -- minute-aligned,
alerts every 5 min, weather every 30 min -- and serves the rendered 792x272
board over HTTP inside a little e-ink "device" so you can watch it live in a
browser before flashing the real panel.

    python3 server.py            # http://127.0.0.1:8080
    python3 server.py 9000       # custom port

Stdlib + Pillow only. Nothing to pip-install, no API keys.
"""

import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import board_config as cfg
from board_data import BoardState

HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# Shared, lock-guarded latest frame.
_lock = threading.Lock()
_latest = {"png": b"", "version": -1, "status": {}}


# The board state lives in the updater thread but is shared with the HTTP
# handler so the "force refresh" button can drive a fetch. _fetch_lock
# serializes fetches so a manual refresh and the minute loop never overlap.
_state = None
_fetch_lock = threading.Lock()


def _log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def _publish(state):
    png = state.render_png()
    with _lock:
        _latest["png"] = png
        _latest["version"] = state.refresh_count
        _latest["status"] = state.render_status()


def force_refresh():
    """Immediate fetch + repaint, triggered by the button. Returns new version."""
    if _state is None:
        return None
    with _fetch_lock:
        _state.update_weather()
        _state.update_citibike()
        _state.update_arrivals(with_alerts=True)
        _state.refresh_count += 1
        _publish(_state)
    _log("manual refresh -> #%d" % _state.refresh_count)
    return _state.refresh_count


def updater():
    """Background loop: fetch + render, aligned to the wall-clock minute."""
    global _state
    _state = BoardState(log=_log)
    state = _state

    _log("initial fetch (weather + arrivals + alerts + citibike)...")
    try:
        with _fetch_lock:
            state.update_weather()
            state.update_citibike()
            state.update_arrivals(with_alerts=True)
    except Exception as e:
        _log("initial fetch error: %s" % e)
    _publish(state)                       # first paint (refresh #0)
    _log("first frame ready -> http://%s:%d" % (HOST, PORT))

    while True:
        try:
            now = time.time()
            target = (int(now) // 60 + 1) * 60
            with_alerts = (target // 60) % cfg.ALERTS_EVERY_MIN == 0
            with_weather = (time.monotonic() - state.last_weather) >= cfg.WEATHER_INTERVAL_S
            with_cb = (time.monotonic() - state.last_cb) >= cfg.CITIBIKE_INTERVAL_S
            prefetch = 20 + (20 if with_alerts else 0) + (5 if with_weather else 0)

            _sleep_until(target - prefetch)
            with _fetch_lock:
                if with_weather:
                    state.update_weather()
                if with_cb:
                    state.update_citibike()
                state.update_arrivals(with_alerts)

            _sleep_until(target)          # hold the flip until the minute ticks
            with _fetch_lock:
                state.refresh_count += 1
                _publish(state)
            _log("refresh #%d (alerts=%s)" % (state.refresh_count, with_alerts))
        except Exception as e:
            _log("update loop error: %s" % e)
            time.sleep(5)


def _sleep_until(target_epoch):
    while True:
        dt = target_epoch - time.time()
        if dt <= 0:
            return
        time.sleep(min(dt, 2.0))


# ---- HTTP ----

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SubwayBoard - e-ink emulator</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 20px; padding: 28px;
    background: #14161a; color: #c9ced6;
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  h1 { font-size: 15px; font-weight: 600; letter-spacing: .02em; margin: 0; color: #e6e9ee; }
  h1 span { color: #7d8590; font-weight: 400; }
  /* The "device": a 5.79" CrowPanel -- charcoal bezel around a white e-ink panel. */
  .device {
    background: linear-gradient(#3a3d42, #26282c);
    padding: 26px; border-radius: 16px;
    box-shadow: 0 18px 50px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.06);
    max-width: 96vw;
  }
  .panel {
    background: #fff; border-radius: 3px; overflow: hidden;
    box-shadow: inset 0 0 0 1px rgba(0,0,0,.15);
    position: relative; line-height: 0;
  }
  .panel img {
    display: block; width: 844px; max-width: 88vw; height: auto;
    image-rendering: pixelated;   /* crisp 1-bit e-ink edges when scaled */
  }
  /* Brief grey wash to mimic the e-ink full-refresh flash on each update. */
  .flash {
    position: absolute; inset: 0; background: #b9bcc2; opacity: 0;
    pointer-events: none;
  }
  .flash.go { animation: eink .45s steps(1,end); }
  @keyframes eink { 0%{opacity:.85} 50%{opacity:0} 60%{opacity:.7} 100%{opacity:0} }
  .status {
    display: flex; gap: 22px; flex-wrap: wrap; justify-content: center;
    font-size: 12px; color: #8a909a;
  }
  .status b { color: #c9ced6; font-weight: 600; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: #3fb950;
         display: inline-block; margin-right: 6px; vertical-align: middle; }
  code { color: #9aa4b2; }
  .btn {
    appearance: none; border: 1px solid #3a3f47; border-radius: 8px;
    background: #21262d; color: #e6e9ee; font: inherit; font-weight: 600;
    padding: 9px 18px; cursor: pointer; transition: background .15s, opacity .15s;
    display: inline-flex; align-items: center; gap: 8px;
  }
  .btn:hover { background: #2b3138; }
  .btn:active { background: #1a1e24; }
  .btn:disabled { opacity: .55; cursor: default; }
  .btn .spin {
    width: 13px; height: 13px; border-radius: 50%;
    border: 2px solid #7d8590; border-top-color: transparent; display: none;
  }
  .btn.busy .spin { display: inline-block; animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style></head>
<body>
  <h1>SubwayBoard <span>&nbsp;e-ink emulator &middot; ELECROW CrowPanel 5.79&Prime; &middot; 792&times;272</span></h1>
  <div class="device">
    <div class="panel">
      <img id="board" src="/board.png" alt="subway board">
      <div class="flash" id="flash"></div>
    </div>
  </div>
  <div class="status">
    <span><span class="dot"></span>live</span>
    <span>now <b id="clock">--:--</b></span>
    <span>refresh <b id="rev">#0</b></span>
    <span>data age <b id="age">-</b></span>
    <span>next flip <b id="next">-</b></span>
  </div>
  <button class="btn" id="refresh">
    <span class="spin"></span><span id="btnlabel">Force refresh</span>
  </button>

<script>
  const $ = id => document.getElementById(id);
  let version = -1;

  function two(n){ return String(n).padStart(2,'0'); }
  function tickClock(){
    const d = new Date();
    let h = d.getHours(); const ap = h<12?'AM':'PM'; h=((h+11)%12)+1;
    $('clock').textContent = h+':'+two(d.getMinutes())+':'+two(d.getSeconds())+' '+ap;
    const s = 60 - d.getSeconds();
    $('next').textContent = s>=60 ? '0s' : s+'s';
  }
  setInterval(tickClock, 1000); tickClock();

  async function poll(){
    try {
      const r = await fetch('/status', {cache:'no-store'});
      const s = await r.json();
      $('rev').textContent = '#' + s.version;
      $('age').textContent = (s.data_age_s==null) ? 'waiting' :
                             (s.data_age_s < 90 ? s.data_age_s+'s' :
                              Math.round(s.data_age_s/60)+'m');
      if (s.version !== version){
        version = s.version;
        const img = $('board');
        img.onload = () => { const f=$('flash'); f.classList.remove('go');
                             void f.offsetWidth; f.classList.add('go'); };
        img.src = '/board.png?v=' + s.version;
      }
    } catch(e) { /* server restarting; keep last frame */ }
  }
  setInterval(poll, 3000); poll();

  const btn = $('refresh'), btnLabel = $('btnlabel');
  btn.addEventListener('click', async () => {
    if (btn.disabled) return;
    btn.disabled = true; btn.classList.add('busy'); btnLabel.textContent = 'Refreshing…';
    try {
      await fetch('/refresh', {method:'POST', cache:'no-store'});
      await poll();                       // swap in the freshly rendered frame
      btnLabel.textContent = 'Refreshed';
    } catch(e) {
      btnLabel.textContent = 'Failed — retry';
    } finally {
      btn.classList.remove('busy'); btn.disabled = false;
      setTimeout(() => { btnLabel.textContent = 'Force refresh'; }, 1600);
    }
  });
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet; we do our own logging

    def _send(self, code, ctype, body, cache=True):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, "text/html; charset=utf-8", PAGE.encode(), cache=False)
        elif path == "/board.png":
            with _lock:
                png = _latest["png"]
            if not png:
                self._send(503, "text/plain", b"warming up", cache=False)
            else:
                self._send(200, "image/png", png, cache=True)
        elif path == "/status":
            import json
            with _lock:
                st = dict(_latest["status"])
                st["version"] = _latest["version"]
            self._send(200, "application/json", json.dumps(st).encode(), cache=False)
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        import json
        path = self.path.split("?", 1)[0]
        if path == "/refresh":
            version = force_refresh()      # blocks ~1-2s while feeds are fetched
            if version is None:
                self._send(503, "text/plain", b"warming up", cache=False)
            else:
                self._send(200, "application/json",
                           json.dumps({"version": version}).encode(), cache=False)
        else:
            self._send(404, "text/plain", b"not found")


def main():
    t = threading.Thread(target=updater, daemon=True)
    t.start()
    # Wait briefly for the first frame so the browser opens to real content.
    for _ in range(60):
        with _lock:
            if _latest["png"]:
                break
        time.sleep(0.5)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    _log("serving on http://%s:%d  (Ctrl-C to stop)" % (HOST, PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        _log("bye")


if __name__ == "__main__":
    main()
