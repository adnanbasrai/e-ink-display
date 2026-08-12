"""Fetch + hold board state -- the emulator's version of board_main.cpp.

Fetches the same MTA GTFS-realtime feeds and Open-Meteo forecast the device
uses (no API key), keeps the last good data per feed on failure, and renders
the current board to PNG. Stdlib only (urllib) so there's nothing to pip-install.
"""

import io
import json
import ssl
import time
import urllib.request

import board_config as cfg
import citibike
import render
import stops
from gtfs_rt import RouteArrivals, RouteAlert, gtfs_rt_parse, gtfs_alerts_parse
from weather import weather_parse

try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo(cfg.TZ_NAME)
except Exception:  # pragma: no cover - fallback if tz database is missing
    _NY = None

# The firmware skips TLS verification for these public feeds; do the same so a
# stale system cert bundle can't stop the emulator from fetching.
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

_UA = "SubwayBoard-Emulator/1.0"


def _fetch(url, timeout=cfg.HTTP_TIMEOUT_S):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return r.read()


def _clock12(dt):
    h12 = ((dt.tm_hour + 11) % 12) + 1
    ampm = "AM" if dt.tm_hour < 12 else "PM"
    return "%d:%02d %s" % (h12, dt.tm_min, ampm)


class BoardState:
    def __init__(self, config=None, log=print):
        self.log = log
        # `config` defaults to the board_config module (emulator behaviour). The
        # render service passes a per-board config object with the same attribute
        # names, so one code path draws any board.
        self.cfg = config if config is not None else cfg
        c = self.cfg
        # Persistent per-(route,stop) data, keyed by ROUTES index so the same
        # route can appear at more than one stop. Kept across failed fetches.
        self.arrivals = {i: RouteArrivals(r[0], r[1]) for i, r in enumerate(c.ROUTES)}
        # Alerts are per route name (a service alert isn't stop-specific).
        self.alerts = {r[0]: RouteAlert(r[0]) for r in c.ROUTES}
        self.weather = weather_parse({}, 0)  # invalid until first good fetch
        self.last_feed_ok = [0.0] * c.NUM_FEEDS  # monotonic secs, 0 = never
        self.last_weather = 0.0
        self.refresh_count = 0
        # Terminal stop id -> station name, for the destination sub-labels.
        self.stop_names = stops.load_stop_names(log=self.log)
        # Stop id -> (lat, lon), for the direction arrows.
        self.stop_coords = stops.load_stop_coords()
        self.ebikes = None
        self.last_cb = 0.0
        # Citi Bike: a pre-resolved station id (device config) is used directly;
        # otherwise find the nearest station to a lat/lon (board_config path).
        station_id = getattr(c, "CITIBIKE_STATION_ID", None)
        if station_id:
            self.cb_id, self.cb_name = station_id, getattr(c, "CITIBIKE_NAME", "station")
        else:
            try:
                self.cb_id, self.cb_name = citibike.nearest_station(
                    c.CITIBIKE_LAT, c.CITIBIKE_LON, log=self.log)
            except Exception as e:
                self.log("citibike station lookup failed: %s" % e)
                self.cb_id, self.cb_name = None, None

    # ---- fetching ----

    def update_weather(self):
        try:
            raw = _fetch(self.cfg.WEATHER_URL)
            data = json.loads(raw)
        except Exception as e:
            self.log("weather fetch failed: %s" % e)
            return
        hour = (_to_ny(time.time()) if _NY else time.localtime()).tm_hour
        fresh = weather_parse(data, hour)
        if fresh.valid:
            self.weather = fresh
            self.log("weather: feels %dF, gust %dmph, UV %d(%s), rain %d%%@%dh" % (
                fresh.feels, fresh.gusts, fresh.uv, fresh.uv_level,
                fresh.rain_prob, fresh.rain_hour))
        else:
            self.log("weather parse failed")
        self.last_weather = time.monotonic()

    def update_citibike(self):
        if not self.cb_id:
            return
        try:
            self.ebikes = citibike.ebikes(self.cb_id)
            self.log("citibike: %s e-bikes at %s" % (self.ebikes, self.cb_name))
        except Exception as e:
            self.log("citibike fetch failed: %s" % e)
        self.last_cb = time.monotonic()

    def update_arrivals(self, with_alerts):
        for f in range(self.cfg.NUM_FEEDS):
            idxs_for_feed = [i for i, r in enumerate(self.cfg.ROUTES) if r[2] == f]
            if not idxs_for_feed:
                continue
            # Parse into fresh scratch objects; only swap in on success so a
            # failed feed keeps the previous (slightly stale) times.
            fresh = {i: RouteArrivals(self.cfg.ROUTES[i][0], self.cfg.ROUTES[i][1])
                     for i in idxs_for_feed}
            try:
                raw = _fetch(self.cfg.FEED_URLS[f])
            except Exception as e:
                self.log("feed %d fetch failed: %s" % (f, e))
                continue
            n_entities = gtfs_rt_parse(raw, list(fresh.values()))
            if n_entities < 0:
                self.log("feed %d parse failed" % f)
                continue
            if n_entities == 0:
                # Empty/near-empty 200 (CDN or proxy hiccup): don't let it wipe
                # the last-good times. Keep stale data and let the age counter
                # climb instead of flashing every column to "no service".
                self.log("feed %d empty body; keeping last-good" % f)
                continue
            self.last_feed_ok[f] = time.monotonic()
            for i, ra in fresh.items():
                self.arrivals[i] = ra
            counts = ", ".join("%s@%s:%d" % (v.route, v.stop_id, len(v.times))
                               for v in fresh.values())
            self.log("feed %d ok (%s)" % (f, counts))

        if not with_alerts:
            return
        fresh_alerts = {r[0]: RouteAlert(r[0]) for r in self.cfg.ROUTES}
        try:
            raw = _fetch(self.cfg.FEED_ALERTS)
        except Exception as e:
            self.log("alerts fetch failed: %s" % e)
            return
        if gtfs_alerts_parse(raw, int(time.time()), list(fresh_alerts.values())):
            self.alerts = fresh_alerts
            active = [a.route for a in fresh_alerts.values() if a.text]
            self.log("alerts ok (%s)" % (", ".join(active) or "none active"))
        else:
            self.log("alerts parse failed")

    # ---- rendering ----

    def _bottom_right(self):
        now_t = time.time()
        dt = time.localtime(now_t) if _NY is None else _to_ny(now_t)
        clock = _clock12(dt)
        oks = [t for t in self.last_feed_ok if t > 0]
        if not oks:
            return "waiting for data  " + clock
        age_min = int((time.monotonic() - min(oks)) / 60)
        if age_min >= 3:
            return "data %d min old  %s" % (age_min, clock)
        return clock

    def render_png(self):
        now_t = int(time.time())
        img = render.render(self.arrivals, self.alerts, self.weather,
                            now_t, self.refresh_count, self._bottom_right(),
                            stop_names=self.stop_names, ebikes=self.ebikes,
                            stop_coords=self.stop_coords, cfg=self.cfg)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def render_status(self):
        """Small dict for the emulator's status line (not shown on the panel)."""
        oks = [t for t in self.last_feed_ok if t > 0]
        age = int((time.monotonic() - min(oks))) if oks else None
        return {
            "refresh": self.refresh_count,
            "weather_valid": self.weather.valid,
            "data_age_s": age,
        }


def _to_ny(epoch):
    import datetime
    return datetime.datetime.fromtimestamp(epoch, _NY).timetuple()
