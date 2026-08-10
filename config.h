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

// ---- Weather (Open-Meteo, no API key; downtown Brooklyn) ----
#define WEATHER_URL \
  "https://api.open-meteo.com/v1/forecast?latitude=40.6883&longitude=-73.9805" \
  "&current_weather=true&hourly=precipitation_probability,weathercode" \
  "&daily=temperature_2m_max,temperature_2m_min" \
  "&temperature_unit=fahrenheit&timezone=America%2FNew_York&forecast_days=1"

// ---- Stops (Manhattan-bound => "N" suffix) ----
#define STOP_NEVINS_NB  "234N"
#define STOP_DEKALB_NB  "R30N"
#define STOP_HOYT_NB    "A42N"

// ---- Routes fetched ----
#define NUM_ROUTES 7
struct RouteConfig {
  const char* route;
  const char* stopId;
  uint8_t feedIndex;   // 0 = IRT, 1 = BDFM, 2 = NQRW, 3 = ACE
};

static const RouteConfig ROUTES[NUM_ROUTES] = {
  { "2", STOP_NEVINS_NB, 0 },
  { "3", STOP_NEVINS_NB, 0 },
  { "4", STOP_NEVINS_NB, 0 },
  { "5", STOP_NEVINS_NB, 0 },
  { "A", STOP_HOYT_NB,   3 },
  { "B", STOP_DEKALB_NB, 1 },
  { "Q", STOP_DEKALB_NB, 2 },
};

// ---- Display columns ----
// Column 0 on screen is weather; these are the four train columns after it.
#define NUM_TRAIN_COLS 4
struct ColumnConfig {
  const char* label;      // bullet text
  const char* station;    // shown under the bullet
  uint8_t routeIdx[2];    // indexes into ROUTES
  uint8_t nRoutes;
};

static const ColumnConfig COLUMNS[NUM_TRAIN_COLS] = {
  { "2/3", "Nevins",       {0, 1}, 2 },
  { "4/5", "Nevins",       {2, 3}, 2 },
  { "A",   "Schermerhorn", {4, 0}, 1 },
  { "B/Q", "DeKalb",       {5, 6}, 2 },
};

#define ARRIVALS_SHOWN 4     // arrivals listed per column (1 big + 3 rows)
