#!/usr/bin/env python3
"""Generate D1 seed SQL for the editor's catalogs:

  stops.sql            - subway parent stations (id, name, lat, lon) from the
                         MTA static GTFS (emulator/stops_cache.csv)
  citibike.sql         - Citi Bike stations (id, name, lat, lon) from GBFS

Run from backend/seed/:  python3 gen_catalog.py
Then load them:          wrangler d1 execute subwayboard --file=seed/stops.sql
                         wrangler d1 execute subwayboard --file=seed/citibike.sql
(add --remote for production; drop it for local dev)
"""

import csv
import json
import os
import ssl
import urllib.request

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


if __name__ == "__main__":
    gen_stops()
    gen_citibike()
