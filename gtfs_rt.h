#pragma once
#include <stdint.h>
#include <stddef.h>

// Leading agency letter of a configured stop id, or 0 for the subway. Subway
// stop ids are always numeric, so a leading letter unambiguously marks a
// namespaced commuter-rail id ("L237" = LIRR Penn Station, "M1" = Metro-North
// Grand Central). The three agencies reuse each other's stop numbers, which is
// why rail ids are namespaced at all -- see config.h and emulator/stops.py.
inline char agencyPrefix(const char* stopId) {
  char c = stopId ? stopId[0] : 0;
  return (c >= 'A' && c <= 'Z') ? c : 0;
}

// Collected arrivals for one route at one stop.
#define MAX_ARRIVALS 12

struct RouteArrivals {
  const char* route;      // e.g. "2"
  const char* stopId;     // e.g. "234N"
  uint32_t times[MAX_ARRIVALS];  // unix epoch seconds, sorted ascending
  char dest[MAX_ARRIVALS][8];    // terminal stop id per arrival (e.g. "401N")
  uint8_t count;
};

// Parse a complete GTFS-realtime FeedMessage held in memory.
// For every TripUpdate whose route_id matches an entry in `routes`, arrival
// times at that entry's stopId are appended (kept sorted, capped at
// MAX_ARRIVALS). Returns false only on malformed protobuf.
//
// If `entityCount` is non-null it receives the number of FeedEntity records
// seen. A live MTA feed always carries many; 0 means an empty/near-empty 200
// (CDN/proxy hiccup), and the caller should keep its last-good data rather than
// treat it as "no service". (A route with genuinely no service still arrives as
// a non-empty feed whose entities simply don't match, so this hides nothing.)
//
// `now` (unix seconds) drops stop times that have already passed. This matters
// for commuter rail: the LIRR and Metro-North feeds carry the whole service
// day, including trips that left hours ago, so without it the MAX_ARRIVALS cap
// fills with departed trains and the board reads "no service". The subway feed
// only publishes the near future, so it's unaffected either way. 0 keeps
// everything (host harnesses replaying a captured feed).
bool gtfsRtParse(const uint8_t* buf, size_t len, RouteArrivals* routes,
                 size_t nRoutes, size_t* entityCount = nullptr, uint32_t now = 0);

// One service-alert blurb per route (MTA's short header, first line, English).
struct RouteAlert {
  const char* route;   // e.g. "2"
  char text[120];      // empty when no active alert mentions the route
};

// Parse a GTFS-realtime service-alerts FeedMessage. For each entry in
// `alerts`, the header of the first alert that is active at `now` and lists
// that route in informed_entity is copied into text. Entries keep their
// existing text only if cleared by the caller first; clear before calling.
bool gtfsAlertsParse(const uint8_t* buf, size_t len, uint32_t now, RouteAlert* alerts, size_t nAlerts);
