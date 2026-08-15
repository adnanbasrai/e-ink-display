// Minimal hand-rolled GTFS-realtime (protobuf wire format) reader.
// We only descend into the handful of fields we care about and skip
// everything else, so no generated code or protobuf library is needed.
//
// Field numbers (gtfs-realtime.proto):
//   FeedMessage.entity            = 2  (len)
//   FeedEntity.trip_update        = 3  (len)
//   TripUpdate.trip               = 1  (len, TripDescriptor)
//   TripUpdate.stop_time_update   = 2  (len, repeated StopTimeUpdate)
//   TripDescriptor.route_id       = 5  (len, string)
//   StopTimeUpdate.arrival        = 2  (len, StopTimeEvent)
//   StopTimeUpdate.departure      = 3  (len, StopTimeEvent)
//   StopTimeUpdate.stop_id        = 4  (len, string)
//   StopTimeEvent.time            = 2  (varint, unix epoch seconds)

#include "gtfs_rt.h"
#include <string.h>

namespace {

struct Cursor {
  const uint8_t* p;
  const uint8_t* end;
};

bool readVarint(Cursor& c, uint64_t& out) {
  out = 0;
  for (int shift = 0; shift < 64; shift += 7) {
    if (c.p >= c.end) return false;
    uint8_t b = *c.p++;
    out |= (uint64_t)(b & 0x7F) << shift;
    if (!(b & 0x80)) return true;
  }
  return false;  // varint too long
}

// Skip a field of the given wire type. Returns false on malformed input.
bool skipField(Cursor& c, uint32_t wireType) {
  uint64_t v;
  switch (wireType) {
    case 0: return readVarint(c, v);                       // varint
    case 1: if (c.end - c.p < 8) return false; c.p += 8;  return true;  // 64-bit
    case 2:                                                // length-delimited
      if (!readVarint(c, v) || (uint64_t)(c.end - c.p) < v) return false;
      c.p += v;
      return true;
    case 5: if (c.end - c.p < 4) return false; c.p += 4;  return true;  // 32-bit
    default: return false;  // groups (3/4) never appear in GTFS-rt
  }
}

// Enter a length-delimited submessage: returns a Cursor bounded to it and
// advances the parent cursor past it.
bool enterMessage(Cursor& c, Cursor& sub) {
  uint64_t len;
  if (!readVarint(c, len) || (uint64_t)(c.end - c.p) < len) return false;
  sub.p = c.p;
  sub.end = c.p + len;
  c.p += len;
  return true;
}

bool readString(Cursor& c, char* out, size_t outSize) {
  uint64_t len;
  if (!readVarint(c, len) || (uint64_t)(c.end - c.p) < len) return false;
  size_t n = (len < outSize - 1) ? (size_t)len : outSize - 1;
  memcpy(out, c.p, n);
  out[n] = '\0';
  c.p += len;
  return true;
}

void insertSorted(RouteArrivals& r, uint32_t t, const char* dest) {
  // Ignore duplicates (a trip occasionally appears twice in a feed).
  for (uint8_t i = 0; i < r.count; i++)
    if (r.times[i] == t) return;
  if (r.count < MAX_ARRIVALS) r.count++;
  else if (t >= r.times[r.count - 1]) return;  // later than everything kept
  int i = r.count - 1;
  while (i > 0 && r.times[i - 1] > t) {
    r.times[i] = r.times[i - 1];
    memcpy(r.dest[i], r.dest[i - 1], sizeof(r.dest[0]));
    i--;
  }
  r.times[i] = t;
  size_t n = 0;
  if (dest) { n = strlen(dest); if (n >= sizeof(r.dest[0])) n = sizeof(r.dest[0]) - 1; }
  memcpy(r.dest[i], dest ? dest : "", n);
  r.dest[i][n] = '\0';
}

// StopTimeEvent -> epoch seconds (0 if absent)
uint32_t parseStopTimeEvent(Cursor c) {
  uint64_t tag, v;
  uint32_t t = 0;
  while (c.p < c.end && readVarint(c, tag)) {
    if ((tag >> 3) == 2 && (tag & 7) == 0) {       // time
      if (!readVarint(c, v)) return t;
      t = (uint32_t)v;
    } else if (!skipField(c, tag & 7)) {
      return t;
    }
  }
  return t;
}

struct StopTime {
  char stopId[16];
  uint32_t arrival;
  uint32_t departure;
};

bool parseStopTimeUpdate(Cursor c, StopTime& st) {
  st.stopId[0] = '\0';
  st.arrival = st.departure = 0;
  uint64_t tag;
  while (c.p < c.end) {
    if (!readVarint(c, tag)) return false;
    uint32_t field = tag >> 3, wire = tag & 7;
    if (field == 4 && wire == 2) {
      if (!readString(c, st.stopId, sizeof(st.stopId))) return false;
    } else if ((field == 2 || field == 3) && wire == 2) {
      Cursor sub;
      if (!enterMessage(c, sub)) return false;
      uint32_t t = parseStopTimeEvent(sub);
      if (field == 2) st.arrival = t; else st.departure = t;
    } else if (!skipField(c, wire)) {
      return false;
    }
  }
  return true;
}

bool parseTripUpdate(Cursor c, RouteArrivals* routes, size_t nRoutes,
                     uint32_t minTime) {
  char routeId[8] = "";
  // Stop-time updates can precede the trip descriptor in theory, so collect
  // candidates and assign once the route is known. Only stops that some
  // configured route actually watches are buffered -- a trip can call at fifty
  // stations, and keeping just the interesting ones bounds this array by the
  // config rather than by the length of the trip.
  StopTime pending[MAX_ARRIVALS * 2];
  size_t nPending = 0;
  // The terminal is tracked separately, on EVERY stop, because it must be the
  // genuine last stop of the trip. Reading it out of `pending` instead would
  // silently return the last *buffered* stop, which for a long trip is some
  // arbitrary station in the middle -- and that is both the destination shown
  // on screen and, for rail, the thing direction is inferred from.
  char terminal[16] = "";

  uint64_t tag;
  while (c.p < c.end) {
    if (!readVarint(c, tag)) return false;
    uint32_t field = tag >> 3, wire = tag & 7;
    if (field == 1 && wire == 2) {                 // TripDescriptor
      Cursor td;
      if (!enterMessage(c, td)) return false;
      uint64_t t2;
      while (td.p < td.end && readVarint(td, t2)) {
        if ((t2 >> 3) == 5 && (t2 & 7) == 2) {
          if (!readString(td, routeId, sizeof(routeId))) return false;
        } else if (!skipField(td, t2 & 7)) {
          break;
        }
      }
    } else if (field == 2 && wire == 2) {          // StopTimeUpdate
      Cursor su;
      if (!enterMessage(c, su)) return false;
      StopTime st;
      if (!parseStopTimeUpdate(su, st) || !st.stopId[0]) continue;
      memcpy(terminal, st.stopId, sizeof(terminal));
      bool watched = false;
      for (size_t r = 0; r < nRoutes && !watched; r++) {
        const char* cfgStop = routes[r].stopId;
        if (agencyPrefix(cfgStop)) cfgStop++;
        if (strcmp(st.stopId, cfgStop) == 0) watched = true;
      }
      if (watched && nPending < sizeof(pending) / sizeof(pending[0]))
        pending[nPending++] = st;
    } else if (!skipField(c, wire)) {
      return false;
    }
  }

  if (!routeId[0]) return true;
  // Stop-time updates run in stop order, so the last one is the terminal --
  // where this train is going. This is also what gives commuter rail a
  // direction: Metro-North's feed omits direction_id entirely, so the only
  // signal for which way a train is headed is where it ends up.
  for (size_t r = 0; r < nRoutes; r++) {
    if (strcmp(routes[r].route, routeId) != 0) continue;
    // A configured rail stop is namespaced ("L237"); the feed carries it bare
    // ("237"). Match against the bare id, then re-apply the prefix to the
    // terminal so it resolves in the shared stop table. See config.h.
    const char* cfgStop = routes[r].stopId;
    char prefix = agencyPrefix(cfgStop);
    if (prefix) cfgStop++;
    // A train that ENDS at our stop can't be boarded there, so it isn't a
    // departure. Terminals make this obvious -- at Grand Central, half of
    // Metro-North's trips terminate at Grand Central -- but it's equally true
    // of a subway train ending its run at your station.
    if (terminal[0] && strcmp(terminal, cfgStop) == 0) continue;
    for (size_t i = 0; i < nPending; i++) {
      if (strcmp(pending[i].stopId, cfgStop) != 0) continue;
      uint32_t t = pending[i].arrival ? pending[i].arrival : pending[i].departure;
      if (!t || t < minTime) continue;
      char dest[8];
      size_t di = 0;
      if (prefix) dest[di++] = prefix;
      for (const char* s = terminal; *s && di < sizeof(dest) - 1; s++) dest[di++] = *s;
      dest[di] = '\0';
      insertSorted(routes[r], t, dest);
    }
  }
  return true;
}

// ---- Service alerts ----
// Field numbers (gtfs-realtime.proto):
//   FeedEntity.alert           = 5  (len)
//   Alert.active_period        = 1  (len, repeated TimeRange)
//   Alert.informed_entity      = 5  (len, repeated EntitySelector)
//   Alert.header_text          = 10 (len, TranslatedString)
//   TimeRange.start / .end     = 1 / 2 (varint)
//   EntitySelector.route_id    = 2  (len, string)
//   TranslatedString.translation = 1 (len); Translation.text = 1, .language = 2

// Pick the English translation (or the first one) out of a TranslatedString.
bool parseTranslated(Cursor c, char* out, size_t outSize) {
  bool have = false;
  uint64_t tag;
  while (c.p < c.end) {
    if (!readVarint(c, tag)) return have;
    if ((tag >> 3) == 1 && (tag & 7) == 2) {
      Cursor tr;
      if (!enterMessage(c, tr)) return have;
      char txt[120] = "", lang[8] = "";
      uint64_t t2;
      while (tr.p < tr.end && readVarint(tr, t2)) {
        if ((t2 >> 3) == 1 && (t2 & 7) == 2) {
          if (!readString(tr, txt, sizeof(txt))) break;
        } else if ((t2 >> 3) == 2 && (t2 & 7) == 2) {
          if (!readString(tr, lang, sizeof(lang))) break;
        } else if (!skipField(tr, t2 & 7)) {
          break;
        }
      }
      if (txt[0] && (!have || strcmp(lang, "en") == 0)) {
        strncpy(out, txt, outSize - 1);
        out[outSize - 1] = '\0';
        have = true;
        if (strcmp(lang, "en") == 0) return true;
      }
    } else if (!skipField(c, tag & 7)) {
      return have;
    }
  }
  return have;
}

void parseAlert(Cursor c, uint32_t now, RouteAlert* alerts, size_t nAlerts) {
  bool matched[16] = {false};
  bool active = false, anyPeriod = false;
  char header[120] = "";

  uint64_t tag;
  while (c.p < c.end) {
    if (!readVarint(c, tag)) return;
    uint32_t field = tag >> 3, wire = tag & 7;
    if (field == 1 && wire == 2) {                 // TimeRange
      anyPeriod = true;
      Cursor tr;
      if (!enterMessage(c, tr)) return;
      uint64_t t2, start = 0, end = 0;
      while (tr.p < tr.end && readVarint(tr, t2)) {
        if ((t2 >> 3) == 1 && (t2 & 7) == 0) { if (!readVarint(tr, start)) break; }
        else if ((t2 >> 3) == 2 && (t2 & 7) == 0) { if (!readVarint(tr, end)) break; }
        else if (!skipField(tr, t2 & 7)) break;
      }
      if ((!start || start <= now) && (!end || end >= now)) active = true;
    } else if (field == 5 && wire == 2) {          // EntitySelector
      Cursor es;
      if (!enterMessage(c, es)) return;
      uint64_t t2;
      while (es.p < es.end && readVarint(es, t2)) {
        if ((t2 >> 3) == 2 && (t2 & 7) == 2) {
          char routeId[8];
          if (!readString(es, routeId, sizeof(routeId))) break;
          for (size_t i = 0; i < nAlerts && i < 16; i++)
            if (strcmp(alerts[i].route, routeId) == 0) matched[i] = true;
        } else if (!skipField(es, t2 & 7)) {
          break;
        }
      }
    } else if (field == 10 && wire == 2) {         // header_text
      Cursor hd;
      if (!enterMessage(c, hd)) return;
      parseTranslated(hd, header, sizeof(header));
    } else if (!skipField(c, wire)) {
      return;
    }
  }

  if (!header[0] || (anyPeriod && !active)) return;
  // Keep only the first line of multi-line headers.
  for (char* p = header; *p; p++)
    if (*p == '\n' || *p == '\r') { *p = '\0'; break; }
  for (size_t i = 0; i < nAlerts && i < 16; i++)
    if (matched[i] && !alerts[i].text[0])
      strcpy(alerts[i].text, header);
}

}  // namespace

bool gtfsAlertsParse(const uint8_t* buf, size_t len, uint32_t now, RouteAlert* alerts, size_t nAlerts) {
  Cursor c{buf, buf + len};
  uint64_t tag;
  while (c.p < c.end) {
    if (!readVarint(c, tag)) return false;
    uint32_t field = tag >> 3, wire = tag & 7;
    if (field == 2 && wire == 2) {                 // FeedEntity
      Cursor entity;
      if (!enterMessage(c, entity)) return false;
      uint64_t t2;
      while (entity.p < entity.end) {
        if (!readVarint(entity, t2)) return false;
        if ((t2 >> 3) == 5 && (t2 & 7) == 2) {     // alert
          Cursor al;
          if (!enterMessage(entity, al)) return false;
          parseAlert(al, now, alerts, nAlerts);
        } else if (!skipField(entity, t2 & 7)) {
          return false;
        }
      }
    } else if (!skipField(c, wire)) {
      return false;
    }
  }
  return true;
}

bool gtfsRtParse(const uint8_t* buf, size_t len, RouteArrivals* routes,
                 size_t nRoutes, size_t* entityCount, uint32_t now) {
  if (entityCount) *entityCount = 0;
  // 60s of slack so a train arriving right now isn't dropped mid-render.
  const uint32_t minTime = now ? now - 60 : 0;
  Cursor c{buf, buf + len};
  uint64_t tag;
  while (c.p < c.end) {
    if (!readVarint(c, tag)) return false;
    uint32_t field = tag >> 3, wire = tag & 7;
    if (field == 2 && wire == 2) {                 // FeedEntity
      Cursor entity;
      if (!enterMessage(c, entity)) return false;
      if (entityCount) (*entityCount)++;
      uint64_t t2;
      while (entity.p < entity.end) {
        if (!readVarint(entity, t2)) return false;
        if ((t2 >> 3) == 3 && (t2 & 7) == 2) {     // trip_update
          Cursor tu;
          if (!enterMessage(entity, tu)) return false;
          if (!parseTripUpdate(tu, routes, nRoutes, minTime)) return false;
        } else if (!skipField(entity, t2 & 7)) {
          return false;
        }
      }
    } else if (!skipField(c, wire)) {
      return false;
    }
  }
  return true;
}
