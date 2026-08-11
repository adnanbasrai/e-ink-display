#pragma once
#include <stdint.h>

// ---- Data refresh cadence ----
// The screen does a clean full refresh aligned to every minute boundary.
#define FULL_REFRESH_EVERY      30       // clear-to-white deep clean every N updates
#define ALERTS_EVERY_MIN        5        // alerts feed (~430 KB) every N minutes
#define WEATHER_INTERVAL_MS     (30UL * 60UL * 1000UL)   // weather every 30 min
#define HTTP_TIMEOUT_MS         15000

// ---- MTA GTFS-realtime feeds (no API key required) ----
#define FEED_IRT   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"        // 1-7 + S
#define FEED_BDFM  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm"
#define FEED_NQRW  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
#define FEED_ACE   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
// Service alerts (why a route isn't running); ~430 KB, so the feed buffer
// must stay at 512 KB+.
#define FEED_ALERTS "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"
#define NUM_FEEDS 4

// ---- Weather (Open-Meteo, no API key; Grand Central-42 St) ----
#define WEATHER_URL \
  "https://api.open-meteo.com/v1/forecast?latitude=40.7527&longitude=-73.9772" \
  "&current=apparent_temperature,wind_gusts_10m,uv_index" \
  "&hourly=precipitation_probability" \
  "&temperature_unit=fahrenheit&wind_speed_unit=mph" \
  "&timezone=America%2FNew_York&forecast_days=1"

// ---- Citi Bike (GBFS, no API key) ----
// station_status is ~960 KB, so FEED_BUF_SIZE in board_main.cpp must be >=~1.1 MB
// (it lives in PSRAM). Hardcode the nearest station's id (the emulator finds it;
// see emulator/citibike_station.json). Default: Park Ave & E 42 St (Grand Central).
#define CITIBIKE_STATUS_URL "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"
#define CITIBIKE_STATION_ID "66dea8ff-0aca-11e7-82f6-3863bb44ef7c"  // E 44 St & 2 Ave
#define CITIBIKE_EVERY_MIN 2       // refresh the e-bike count every N minutes

// ---- Stops (Grand Central-42 St) ----
// N = uptown/Bronx-bound, S = downtown/Brooklyn-bound (GTFS direction suffix).
#define STOP_GC_LEX_NB  "631N"   // 4/5/6 Lexington Ave line, uptown
#define STOP_GC_LEX_SB  "631S"   // 4/5/6 Lexington Ave line, downtown
#define STOP_GC_7_SB    "723S"   // 7 Flushing line, toward 34 St-Hudson Yards ("S")

// ---- Routes fetched ----
// The 4 appears twice (uptown + downtown). Columns reference ROUTES by index
// below, so a route living at two stops is fine.
#define NUM_ROUTES 5
struct RouteConfig {
  const char* route;
  const char* stopId;
  uint8_t feedIndex;   // 0 = IRT, 1 = BDFM, 2 = NQRW, 3 = ACE
};

static const RouteConfig ROUTES[NUM_ROUTES] = {
  { "4", STOP_GC_LEX_NB, 0 },   // 0  uptown 4 (Woodlawn / 149 St short-turns)
  { "4", STOP_GC_LEX_SB, 0 },   // 1  downtown 4
  { "5", STOP_GC_LEX_SB, 0 },   // 2  downtown 5
  { "6", STOP_GC_LEX_SB, 0 },   // 3  downtown 6
  { "7", STOP_GC_7_SB,   0 },   // 4  7 toward 34 St-Hudson Yards
};

// ---- Display columns ----
// Column 0 on screen is weather; these are the four train columns after it.
// The label under the bullet is the DESTINATION of the next train, derived live
// from the feed (each trip's terminal -> stopnames.h), auto-sized to fill the
// column. `station` is the FALLBACK, shown only when a column has no upcoming
// train. `destFilter` (when nFilter > 0) keeps only trains bound for those
// destinations -- e.g. the uptown 4 to Woodlawn but not its 149 St short-turns.
#define NUM_TRAIN_COLS 4
struct ColumnConfig {
  const char* label;         // bullet text
  const char* station;       // fallback shown under the bullet when no service
  uint8_t routeIdx[2];       // indexes into ROUTES
  uint8_t nRoutes;
  const char* destFilter[2]; // allowed destination names; empty = every train
  uint8_t nFilter;
};

static const ColumnConfig COLUMNS[NUM_TRAIN_COLS] = {
  { "4",   "Woodlawn",         {0, 0}, 1, {"Woodlawn", nullptr}, 1 },
  { "4/5", "Brooklyn",         {1, 2}, 2, {nullptr, nullptr},    0 },
  { "6",   "Bklyn Bridge",     {3, 0}, 1, {nullptr, nullptr},    0 },
  { "7",   "34 St-Hudson Yds", {4, 0}, 1, {nullptr, nullptr},    0 },
};

#define ARRIVALS_SHOWN 3     // arrivals listed per column (1 big + 2 rows)
