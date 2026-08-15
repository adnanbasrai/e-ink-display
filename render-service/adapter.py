"""Turn a device-ready config dict (what the Worker serves / the board fetches)
into an object with the attribute names the emulator's BoardState/render expect.

Device config shape (same as emulator/board_config.py, backend/src/config.js):
    routes:  [{ route, stop_id, feed }]
    columns: [{ label, fallback, route_idx[], dest_filter[] }]
    weather: { lat, lon, tz }
    citibike:{ station_id }        # already resolved, unlike board_config's lat/lon
"""

import os
import sys
import types
from urllib.parse import quote

# The fixed MTA feed universe. Taken straight from the emulator's config rather
# than copied, so adding a feed (LIRR, Metro-North) can't leave the preview
# renderer one table behind the board.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "emulator"))
import board_config  # noqa: E402

FEED_URLS = board_config.FEED_URLS
FEED_AGENCY = board_config.FEED_AGENCY
FEED_ALERTS = board_config.FEED_ALERTS
FEED_ALERTS_BY_AGENCY = board_config.FEED_ALERTS_BY_AGENCY


def _weather_url(lat, lon, tz):
    return (
        "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
        "&current=apparent_temperature,wind_gusts_10m,uv_index"
        "&hourly=precipitation_probability"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph"
        "&timezone=%s&forecast_days=1"
    ) % (lat, lon, quote(str(tz), safe=""))


def cfg_from_device(config):
    c = types.SimpleNamespace()
    c.ROUTES = [(r["route"], r["stop_id"], int(r["feed"])) for r in config["routes"]]
    c.COLUMNS = [
        (col["label"], col.get("fallback", ""),
         list(col["route_idx"]), list(col.get("dest_filter", [])),
         # Commuter rail only: the compass direction its trains must be headed.
         str(col.get("dir_filter", "") or ""))
        for col in config["columns"]
    ]
    c.ARRIVALS_SHOWN = int(config.get("arrivals_shown", 3))
    # Board style: "R" Refined Signage / "H" Hero Digit / "P" Platform Cards.
    c.LAYOUT = str(config.get("layout", "R")).upper()
    c.NUM_FEEDS = len(FEED_URLS)
    c.FEED_URLS = FEED_URLS
    c.FEED_AGENCY = FEED_AGENCY
    c.FEED_ALERTS = FEED_ALERTS
    c.FEED_ALERTS_BY_AGENCY = FEED_ALERTS_BY_AGENCY

    w = config.get("weather") or {}
    lat = w.get("lat", 40.7527)
    lon = w.get("lon", -73.9772)
    tz = w.get("tz", "America/New_York")
    c.WEATHER_URL = _weather_url(lat, lon, tz)
    c.TZ_NAME = tz

    cb = config.get("citibike") or {}
    if cb.get("station_id"):
        c.CITIBIKE_STATION_ID = cb["station_id"]

    c.HTTP_TIMEOUT_S = 15
    return c
