#pragma once
#include <stdint.h>

// Board configuration. The station/route/column selection is no longer baked in
// here -- it is fetched at runtime from the backend (see config_runtime.cpp) so
// it can be edited from the website. This header now holds only the fixed bits
// (feeds, cadence, capacities) plus `extern` declarations of the runtime config
// globals, whose NAMES match the old compile-time symbols so the rest of the
// firmware is unchanged apart from array sizes and now-runtime counts.

// ---- Backend (remote config) ----
#define WORKER_BASE       "https://subwayboard.adnanjuzarbasrai.workers.dev"
#define CONFIG_REFETCH_MS (5UL * 60UL * 1000UL)   // re-pull settings every 5 min

// ---- Data refresh cadence (compile-time; not user-editable yet) ----
#define ALERTS_EVERY_MIN     5        // alerts feed (~430 KB) every N minutes
#define WEATHER_INTERVAL_MS  (30UL * 60UL * 1000UL)   // weather every 30 min
#define CITIBIKE_EVERY_MIN   2        // refresh the e-bike count every N minutes
#define HTTP_TIMEOUT_MS      15000

// ---- MTA GTFS-realtime feeds (fixed universe; a route's feedIndex picks one) ----
#define FEED_IRT   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"        // 1-7 + S
#define FEED_BDFM  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm"
#define FEED_NQRW  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
#define FEED_ACE   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
#define FEED_ALERTS "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"
#define NUM_FEEDS 4

// ---- Citi Bike ----
#define CITIBIKE_STATUS_URL "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"

// ---- Runtime config capacities (arrays are sized to these; counts are runtime) ----
#define MAX_ROUTES 12     // MUST stay <= 16 (the alert parser caps routes at 16)
#define MAX_COLS   4
#define MAX_MERGE  2      // routes merged into one column (e.g. 4/5)
#define MAX_FILTER 2      // destination-name filters per column
#define ARRIVALS_SHOWN 3  // arrivals listed per column (1 big + 2 rows)

struct RouteConfig {
  char route[4];       // e.g. "4"
  char stopId[8];      // e.g. "631N" (suffix is the GTFS direction)
  uint8_t feedIndex;   // 0 = IRT, 1 = BDFM, 2 = NQRW, 3 = ACE
};

struct ColumnConfig {
  char label[12];                 // bullet text, e.g. "4/5"
  char station[40];               // fallback shown when the column has no train
  uint8_t routeIdx[MAX_MERGE];    // indexes into ROUTES[]
  uint8_t nRoutes;
  char destFilter[MAX_FILTER][40];// allowed destination names ("" slot = unused)
  uint8_t nFilter;                // 0 = accept every train
};

// Runtime config, populated from the backend (defined in config_runtime.cpp).
extern RouteConfig  ROUTES[MAX_ROUTES];
extern uint8_t      NUM_ROUTES;              // active route count
extern ColumnConfig COLUMNS[MAX_COLS];
extern uint8_t      NUM_TRAIN_COLS;          // active train-column count
extern char         WEATHER_URL[280];        // built from the config's lat/lon/tz
extern char         CITIBIKE_STATION_ID[40]; // "" = hide the e-bike row
extern char         DISPLAY_ID[16];          // shown on screen for sign-in
extern char         DEVICE_PIN[12];          // shown until the board is claimed
extern uint32_t     CONFIG_REV;
