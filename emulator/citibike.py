"""Citi Bike GBFS reader (public, no API key).

Finds the station nearest a lat/lon once (cached to disk), then reports the
e-bikes available there. GBFS has no per-station endpoint -- station_status is
~960 KB -- so we fetch the whole feed and scan for our station id. On the ESP32
the same approach needs the feed buffer bumped past 1 MB and the station id
hardcoded (see config.h); here it just works.
"""

import json
import os
import ssl
import urllib.request

import board_config as cfg

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE
_CACHE = os.path.join(os.path.dirname(__file__), "citibike_station.json")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "subwayboard/1.0"})
    return urllib.request.urlopen(req, timeout=30, context=_SSL).read()


def nearest_station(lat, lon, log=print):
    """Return (station_id, name) nearest lat/lon. Cached to disk after first use."""
    if os.path.exists(_CACHE):
        try:
            c = json.loads(open(_CACHE, encoding="utf-8").read())
            if c.get("lat") == lat and c.get("lon") == lon:
                log("citibike: station %s (%s) [cache]" % (c["id"], c["name"]))
                return c["id"], c["name"]
        except Exception:
            pass
    stations = json.loads(_get(cfg.CITIBIKE_STATION_INFO))["data"]["stations"]
    best, bestd = None, None
    for s in stations:
        d = (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2
        if bestd is None or d < bestd:
            bestd, best = d, s
    try:
        with open(_CACHE, "w", encoding="utf-8") as f:
            json.dump({"lat": lat, "lon": lon, "id": best["station_id"],
                       "name": best["name"]}, f)
    except Exception:
        pass
    log("citibike: nearest is %s (%s)" % (best["station_id"], best["name"]))
    return best["station_id"], best["name"]


def ebikes(station_id):
    """e-bikes available at station_id (None on failure/not found)."""
    stations = json.loads(_get(cfg.CITIBIKE_STATION_STATUS))["data"]["stations"]
    for s in stations:
        if s["station_id"] == station_id:
            return s.get("num_ebikes_available",
                         s.get("num_bikes_available", 0))
    return None
