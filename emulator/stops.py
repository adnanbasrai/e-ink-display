"""Stop-ID -> station-name map, from the MTA static GTFS `stops.txt`.

Used to turn a train's terminal stop id (the last stop in its trip) into a
human destination like "Woodlawn" or "34 St-Hudson Yards". Fetched once and
cached to disk so restarts are instant and work offline. Falls back to a small
bundled map of the common IRT terminals if the download ever fails.

This is emulator-only convenience -- the display shows a nicer label; the data
itself is the same the device sees.
"""

import csv
import io
import math
import os
import ssl
import urllib.request
import zipfile

# MTA static GTFS (subway). Contains stops.txt with stop_id -> stop_name.
_GTFS_ZIP = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
_CACHE = os.path.join(os.path.dirname(__file__), "stops_cache.csv")

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

# The destination line uses a small font, so full station names fit and are
# shown as-is (anything past the column width is fit-truncated at render time).
# Add entries here only if you want a custom shorter label for some terminal.
OVERRIDES = {
    # "34 St-Hudson Yards": "Hudson Yards",
}

# Minimal fallback if the download fails on a fresh machine (IRT terminals).
_FALLBACK = {
    "401": "Woodlawn", "501": "Eastchester-Dyre Av", "504": "Nereid Av",
    "247": "Flatbush Av-Brooklyn College", "257": "New Lots Av",
    "640": "Brooklyn Bridge-City Hall", "726": "34 St-Hudson Yards",
    "701": "Flushing-Main St", "418": "Crown Hts-Utica Av",
    "302": "Harlem-148 St", "301": "Wakefield-241 St",
}


def _parse_csv(text):
    names = {}
    rdr = csv.DictReader(io.StringIO(text))
    for row in rdr:
        names[row["stop_id"]] = row["stop_name"]
    return names


def load_stop_names(log=print):
    """Return {stop_id: stop_name}. Cache on disk; fetch + extract if missing."""
    if os.path.exists(_CACHE):
        try:
            with open(_CACHE, "r", encoding="utf-8") as f:
                names = _parse_csv(f.read())
            log("stops: loaded %d from cache" % len(names))
            return names
        except Exception as e:
            log("stops: cache unreadable (%s), refetching" % e)

    try:
        req = urllib.request.Request(_GTFS_ZIP, headers={"User-Agent": "x"})
        raw = urllib.request.urlopen(req, timeout=30, context=_SSL).read()
        z = zipfile.ZipFile(io.BytesIO(raw))
        text = z.read("stops.txt").decode("utf-8")
        names = _parse_csv(text)
        try:
            with open(_CACHE, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass  # non-fatal; just means we refetch next start
        log("stops: fetched %d, cached to %s" % (len(names), os.path.basename(_CACHE)))
        return names
    except Exception as e:
        log("stops: download failed (%s); using bundled fallback" % e)
        return dict(_FALLBACK)


def _base(stop_id):
    return stop_id[:-1] if stop_id and stop_id[-1] in "NS" else stop_id


def load_stop_coords():
    """{base stop id: (lat, lon)} from the cached stops.txt (for direction)."""
    coords = {}
    if not os.path.exists(_CACHE):
        return coords
    try:
        for row in csv.DictReader(open(_CACHE, encoding="utf-8")):
            try:
                coords.setdefault(_base(row["stop_id"]),
                                  (float(row["stop_lat"]), float(row["stop_lon"])))
            except (ValueError, KeyError):
                pass
    except Exception:
        pass
    return coords


def direction4(from_id, to_id, coords):
    """Compass heading from one stop to another, snapped to the dominant axis:
    'N'/'S'/'E'/'W', or None if either stop's coordinates are unknown."""
    a = coords.get(_base(from_id))
    b = coords.get(_base(to_id))
    if not a or not b:
        return None
    d_north = b[0] - a[0]
    d_east = (b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    if abs(d_north) >= abs(d_east):
        return "N" if d_north >= 0 else "S"
    return "E" if d_east >= 0 else "W"


def dest_name(stop_id, names):
    """Human destination for a terminal stop id ('' if unknown)."""
    if not stop_id:
        return ""
    n = names.get(stop_id)
    if n is None and stop_id[-1] in "NS":
        n = names.get(stop_id[:-1])   # strip direction suffix -> parent station
    if n is None:
        return ""
    return OVERRIDES.get(n, n)
