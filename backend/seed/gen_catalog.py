#!/usr/bin/env python3
"""Generate D1 seed SQL for the editor's catalogs:

  stops.sql            - subway parent stations (id, name, lat, lon) from the
                         MTA static GTFS (emulator/stops_cache.csv)
  citibike.sql         - Citi Bike stations (id, name, lat, lon) from GBFS
  rail.sql             - LIRR + Metro-North stations, with the branches serving
                         each, from each agency's static GTFS

Run from backend/seed/:  python3 gen_catalog.py
Then load them:          wrangler d1 execute subwayboard --file=seed/stops.sql
                         wrangler d1 execute subwayboard --file=seed/citibike.sql
(add --remote for production; drop it for local dev)
"""

import csv
import io
import json
import os
import ssl
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
# MTA "Subway Stations" dataset: one row per GTFS stop, with the daytime routes
# that stop serves and the Complex ID that groups a station's stops together.
MTA_STATIONS = "https://data.ny.gov/api/views/39hk-dx4f/rows.csv?accessType=DOWNLOAD"
GBFS = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


def batched_insert(table, cols, rows, out, batch=400):
    out.write(f"DELETE FROM {table};\n")
    collist = ",".join(cols)
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        values = ",".join("(" + ",".join(r) + ")" for r in chunk)
        out.write(f"INSERT INTO {table} ({collist}) VALUES {values};\n")


def gen_stops():
    req = urllib.request.Request(MTA_STATIONS, headers={"User-Agent": "subwayboard-seed/1.0"})
    text = urllib.request.urlopen(req, timeout=60, context=_SSL).read().decode("utf-8")
    rows = []
    for r in csv.DictReader(text.splitlines()):
        sid = r["GTFS Stop ID"]
        if not sid:
            continue
        rows.append([q(sid), q(r["Stop Name"]), r["GTFS Latitude"], r["GTFS Longitude"],
                     q(r["Daytime Routes"].strip()), q(r["Complex ID"])])
    with open(os.path.join(HERE, "stops.sql"), "w", encoding="utf-8") as out:
        batched_insert("stops", ["stop_id", "name", "lat", "lon", "routes", "complex_id"], rows, out)
    print(f"stops.sql: {len(rows)} stops")


def gen_citibike():
    req = urllib.request.Request(GBFS, headers={"User-Agent": "subwayboard-seed/1.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=30, context=_SSL).read())
    stations = data["data"]["stations"]
    rows = [[q(s["station_id"]), q(s["name"]), str(s["lat"]), str(s["lon"])]
            for s in stations if s.get("name")]
    with open(os.path.join(HERE, "citibike.sql"), "w", encoding="utf-8") as out:
        batched_insert("citibike_stations", ["station_id", "name", "lat", "lon"], rows, out)
    print(f"citibike.sql: {len(rows)} stations")


def gen_rail():
    """Commuter-rail stations, with the branches that actually serve each one.

    Which branch calls at which station isn't in stops.txt, so it's derived the
    only way the static GTFS offers: trips.txt maps trip -> route, stop_times.txt
    maps trip -> stops, and joining them gives route -> stations. Stop ids are
    written with their agency prefix ("L237", "M1") because the three agencies
    reuse each other's numbers -- see emulator/stops.py.
    """
    sources = [("L", "http://web.mta.info/developers/data/lirr/google_transit.zip"),
               ("M", "http://web.mta.info/developers/data/mnr/google_transit.zip")]
    rows = []
    for prefix, url in sources:
        req = urllib.request.Request(url, headers={"User-Agent": "subwayboard-seed/1.0"})
        raw = urllib.request.urlopen(req, timeout=120, context=_SSL).read()
        z = zipfile.ZipFile(io.BytesIO(raw))

        def table(name):
            return csv.DictReader(io.StringIO(z.read(name).decode("utf-8-sig")))

        trip_route = {t["trip_id"]: t["route_id"] for t in table("trips.txt")}
        stop_routes = {}
        for st in table("stop_times.txt"):
            r = trip_route.get(st["trip_id"])
            if r:
                stop_routes.setdefault(st["stop_id"], set()).add(r)

        n = 0
        for s in table("stops.txt"):
            sid = s["stop_id"]
            routes = sorted(stop_routes.get(sid, ()), key=lambda x: int(x) if x.isdigit() else 99)
            if not routes:
                continue          # yards and other non-passenger stops
            rows.append([q(prefix + sid), q(prefix), q(s["stop_name"]),
                         s.get("stop_lat") or "0", s.get("stop_lon") or "0",
                         q(" ".join(routes))])
            n += 1
        print(f"  {prefix}: {n} stations")

    with open(os.path.join(HERE, "rail.sql"), "w", encoding="utf-8") as out:
        batched_insert("rail_stops",
                       ["stop_id", "agency", "name", "lat", "lon", "routes"], rows, out)
    print(f"rail.sql: {len(rows)} stations")


if __name__ == "__main__":
    gen_stops()
    gen_citibike()
    gen_rail()
