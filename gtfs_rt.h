#pragma once
#include <stdint.h>
#include <stddef.h>

// Collected arrivals for one route at one stop.
#define MAX_ARRIVALS 12

struct RouteArrivals {
  const char* route;      // e.g. "2"
  const char* stopId;     // e.g. "234N"
  uint32_t times[MAX_ARRIVALS];  // unix epoch seconds, sorted ascending
  uint8_t count;
};

// Parse a complete GTFS-realtime FeedMessage held in memory.
// For every TripUpdate whose route_id matches an entry in `routes`, arrival
// times at that entry's stopId are appended (kept sorted, capped at
// MAX_ARRIVALS). Returns false only on malformed protobuf.
bool gtfsRtParse(const uint8_t* buf, size_t len, RouteArrivals* routes, size_t nRoutes);

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
