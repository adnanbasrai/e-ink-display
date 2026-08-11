"""Board configuration -- a direct port of the firmware's config.h.

Change routes/stops/columns/weather location here exactly as you would on the
device, and the emulator matches what the panel will show.
"""

# ---- Data refresh cadence ----
FULL_REFRESH_EVERY = 30                    # (cosmetic here) deep clean every N updates
ALERTS_EVERY_MIN = 5                       # alerts feed (~430 KB) every N minutes
WEATHER_INTERVAL_S = 30 * 60               # weather every 30 min
HTTP_TIMEOUT_S = 15

# ---- MTA GTFS-realtime feeds (no API key required) ----
FEED_IRT = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"        # 1-7 + S
FEED_BDFM = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm"
FEED_NQRW = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
FEED_ACE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
FEED_ALERTS = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"

FEED_URLS = [FEED_IRT, FEED_BDFM, FEED_NQRW, FEED_ACE]  # index 0..3
NUM_FEEDS = len(FEED_URLS)

# ---- Weather (Open-Meteo, no API key; Grand Central-42 St) ----
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=40.7527&longitude=-73.9772"
    "&current=apparent_temperature,wind_gusts_10m,uv_index"
    "&hourly=precipitation_probability"
    "&temperature_unit=fahrenheit&wind_speed_unit=mph"
    "&timezone=America%2FNew_York&forecast_days=1"
)

# ---- Citi Bike (GBFS, no API key) ----
# The board shows e-bikes available at the station nearest CITIBIKE_LAT/LON.
CITIBIKE_STATION_INFO = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"
CITIBIKE_STATION_STATUS = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"
CITIBIKE_LAT = 40.75118       # E 44 St & 2 Ave
CITIBIKE_LON = -73.97139
CITIBIKE_INTERVAL_S = 120     # refresh the e-bike count every N seconds

# ---- Stops (Grand Central-42 St) ----
# N = uptown/Bronx-bound, S = downtown/Brooklyn-bound (GTFS direction suffix).
STOP_GC_LEX_NB = "631N"   # 4/5/6 Lexington Ave line, uptown
STOP_GC_LEX_SB = "631S"   # 4/5/6 Lexington Ave line, downtown
STOP_GC_7_SB = "723S"     # 7 Flushing line, toward 34 St-Hudson Yards ("S")

# ---- Routes fetched ---- (route, stopId, feedIndex)  0=IRT 1=BDFM 2=NQRW 3=ACE
# The 4 appears twice (uptown + downtown), so arrivals are tracked per
# (route, stop), keyed by their index below.
ROUTES = [
    ("4", STOP_GC_LEX_NB, 0),   # 0  uptown 4 (Woodlawn / 149 St short-turns)
    ("4", STOP_GC_LEX_SB, 0),   # 1  downtown 4
    ("5", STOP_GC_LEX_SB, 0),   # 2  downtown 5
    ("6", STOP_GC_LEX_SB, 0),   # 3  downtown 6
    ("7", STOP_GC_7_SB, 0),     # 4  7 toward 34 St-Hudson Yards
]

# ---- Display columns ----  (bullet, fallback, [route idxs], [dest filter])
# The label under the bullet is the DESTINATION of the next train, derived live
# from the feed (via stops.py). `fallback` shows only when a column has no
# upcoming train. `dest filter`, when non-empty, keeps only trains whose
# destination name is in the list -- e.g. the uptown 4 to Woodlawn but not its
# 149 St short-turns. Empty list = show every train at that stop.
COLUMNS = [
    ("4",   "Woodlawn",         [0],    ["Woodlawn"]),
    ("4/5", "Brooklyn",         [1, 2], []),
    ("6",   "Bklyn Bridge",     [3],    []),
    ("7",   "34 St-Hudson Yds", [4],    []),
]

ARRIVALS_SHOWN = 3  # arrivals listed per column (1 big + 2 rows)

# ---- Timezone for the clock / arrival math ----
TZ_NAME = "America/New_York"
