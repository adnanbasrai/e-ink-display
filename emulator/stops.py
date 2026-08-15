"""Stop-ID -> station-name map, from the MTA static GTFS `stops.txt`.

Used to turn a train's terminal stop id (the last stop in its trip) into a
human destination like "Woodlawn", "34 St-Hudson Yards" or "Poughkeepsie".
Fetched once and cached to disk so restarts are instant and work offline. Falls
back to a small bundled map of the common IRT terminals if the download fails.

Three agencies share this table, and their stop ids collide -- LIRR "1" is
Albertson, Metro-North "1" is Grand Central, and the subway's own "101" is Van
Cortlandt Park. So every non-subway id is stored with a one-letter **agency
prefix** ("L237", "M124"); subway ids stay bare. Subway ids are always numeric,
which is what makes the prefix unambiguous to strip. Prefixes are applied by the
feed parser (a route's feed index decides its agency) so the same key format
reaches both this map and the firmware's `stopnames.h`.

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

# MTA static GTFS, one zip per agency: (id prefix, url). Each contains a
# stops.txt with stop_id / stop_name / stop_lat / stop_lon.
_GTFS_SOURCES = [
    ("", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"),
    ("L", "http://web.mta.info/developers/data/lirr/google_transit.zip"),
    ("M", "http://web.mta.info/developers/data/mnr/google_transit.zip"),
]
# Named for the combined (multi-agency) format -- a subway-only cache left by an
# older build must not be reused, or every rail destination would come back "".
_CACHE = os.path.join(os.path.dirname(__file__), "stops_cache_all.csv")

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
        text = fetch_combined(log)
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


def fetch_combined(log=print):
    """Download every agency's stops.txt and return one prefixed CSV.

    Emitted with just the four columns anything downstream reads, because the
    three agencies' stops.txt files don't agree on their other columns.
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon"])
    total = 0
    for prefix, url in _GTFS_SOURCES:
        req = urllib.request.Request(url, headers={"User-Agent": "x"})
        raw = urllib.request.urlopen(req, timeout=60, context=_SSL).read()
        text = zipfile.ZipFile(io.BytesIO(raw)).read("stops.txt").decode("utf-8-sig")
        n = 0
        for row in csv.DictReader(io.StringIO(text)):
            w.writerow([prefix + row["stop_id"], row["stop_name"],
                        row.get("stop_lat", ""), row.get("stop_lon", "")])
            n += 1
        total += n
        log("stops: %s %d" % (prefix or "subway", n))
    return buf.getvalue()


def _base(stop_id):
    """Strip the subway's N/S direction suffix. Agency-prefixed (rail) ids are
    numeric after the prefix and carry no suffix, so they're returned as-is."""
    if not stop_id or stop_id[0].isalpha():
        return stop_id
    return stop_id[:-1] if stop_id[-1] in "NS" else stop_id


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
