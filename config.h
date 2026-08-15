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
// Feeds 0-3 are the subway; 4-5 are commuter rail. All key-free. LIRR and
// Metro-North publish the same TripUpdate shape the subway does, so the same
// parser reads them -- but their route ids and stop ids collide with the
// subway's (LIRR route "1" is the Babylon Branch, MNR stop "1" is Grand
// Central). Routes are matched per feed, and stop ids are namespaced by
// FEED_AGENCY below. Metro-North also omits direction_id entirely, which is
// why direction comes from the trip's terminal rather than the feed.
#define FEED_IRT   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"        // 1-7 + S
#define FEED_BDFM  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm"
#define FEED_NQRW  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw"
#define FEED_ACE   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
#define FEED_LIRR  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr"
#define FEED_MNR   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/mnr%2Fgtfs-mnr"
#define NUM_FEEDS 6

// Stop-id namespace per feed: '\0' = subway (bare numeric ids), 'L' = LIRR,
// 'M' = Metro-North. Matches the prefixes baked into stopnames.h.
#define FEED_AGENCY_INIT { 0, 0, 0, 0, 'L', 'M' }

// Service alerts, one feed per agency (indexed by the agency codes above).
// The subway's is ~500 KB; the rail ones are a tenth of that.
#define FEED_ALERTS "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"
#define FEED_ALERTS_LIRR "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Flirr-alerts"
#define FEED_ALERTS_MNR  "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fmnr-alerts"

// ---- Citi Bike ----
#define CITIBIKE_STATUS_URL "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"

// ---- Runtime config capacities (arrays are sized to these; counts are runtime) ----
#define MAX_ROUTES 12     // MUST stay <= 16 (the alert parser caps routes at 16)
#define MAX_COLS   4
#define MAX_MERGE  2      // routes merged into one column (e.g. 4/5)
#define MAX_FILTER 2      // destination-name filters per column
#define ARRIVALS_SHOWN 3  // arrivals listed per column (1 big + 2 rows)

struct RouteConfig {
  char route[4];       // subway line ("4"), or the rail branch's route id ("1")
  char stopId[8];      // "631N" (subway; suffix is the GTFS direction), or an
                       // agency-prefixed rail id ("L237" = LIRR Penn Station)
  uint8_t feedIndex;   // 0=IRT, 1=BDFM, 2=NQRW, 3=ACE, 4=LIRR, 5=Metro-North
};

struct ColumnConfig {
  char label[12];                 // bullet text, e.g. "4/5"
  char station[40];               // fallback shown when the column has no train
  uint8_t routeIdx[MAX_MERGE];    // indexes into ROUTES[]
  uint8_t nRoutes;
  char destFilter[MAX_FILTER][40];// allowed destination names ("" slot = unused)
  uint8_t nFilter;                // 0 = accept every train
  // Commuter rail only: the compass direction ('N'/'E'/'S'/'W') a train must be
  // travelling to count. Subway stop ids end in N or S, so the stop alone picks
  // the direction; rail stop ids don't, and Metro-North's feed has no
  // direction_id either, so without this a mid-line station would mix inbound
  // and outbound trains together. 0 = no filter.
  char dirFilter;
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
// Board style, chosen on the website: 'R' Refined Signage (default),
// 'H' Hero Digit, 'P' Platform Cards. See display.h.
extern char         LAYOUT;
