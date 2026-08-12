"""Turn a device-ready config dict (what the Worker serves / the board fetches)
into an object with the attribute names the emulator's BoardState/render expect.

Device config shape (same as emulator/board_config.py, backend/src/config.js):
    routes:  [{ route, stop_id, feed }]
    columns: [{ label, fallback, route_idx[], dest_filter[] }]
    weather: { lat, lon, tz }
    citibike:{ station_id }        # already resolved, unlike board_config's lat/lon
"""

import types
from urllib.parse import quote

# The fixed MTA feed universe (same URLs as config.h / board_config.py).
FEED_IRT = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"
FEED_BDFM = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm"
FEED_NQRW = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
FEED_ACE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
FEED_URLS = [FEED_IRT, FEED_BDFM, FEED_NQRW, FEED_ACE]
FEED_ALERTS = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"


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
         list(col["route_idx"]), list(col.get("dest_filter", [])))
        for col in config["columns"]
    ]
    c.ARRIVALS_SHOWN = int(config.get("arrivals_shown", 3))
    c.NUM_FEEDS = len(FEED_URLS)
    c.FEED_URLS = FEED_URLS
    c.FEED_ALERTS = FEED_ALERTS

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
