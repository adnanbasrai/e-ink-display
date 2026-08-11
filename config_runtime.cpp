// Runtime board configuration: the globals declared in config.h, populated from
// the backend's JSON (same shape the emulator/board_config.py + backend serve),
// with a baked Grand Central default and an NVS cache for offline reboots.

#include "config.h"
#include "config_fetch.h"

#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <string.h>
#include <stdio.h>

// ---- the runtime config globals ----
RouteConfig  ROUTES[MAX_ROUTES];
uint8_t      NUM_ROUTES = 0;
ColumnConfig COLUMNS[MAX_COLS];
uint8_t      NUM_TRAIN_COLS = 0;
char         WEATHER_URL[280];
char         CITIBIKE_STATION_ID[40];
char         DISPLAY_ID[16] = "";
char         DEVICE_PIN[12] = "";
uint32_t     CONFIG_REV = 0;

// Stable per-board id: the WiFi MAC, colons stripped, lowercase (e.g. 1cdbd455da5c).
String deviceId() {
  String m = WiFi.macAddress();
  m.replace(":", "");
  m.toLowerCase();
  return m;
}

// Build the Open-Meteo URL from a config's location (the tz '/' is percent-encoded).
static void buildWeatherUrl(double lat, double lon, const char* tz) {
  char tzenc[48];
  size_t j = 0;
  for (size_t i = 0; tz[i] && j < sizeof(tzenc) - 3; i++) {
    if (tz[i] == '/') { tzenc[j++] = '%'; tzenc[j++] = '2'; tzenc[j++] = 'F'; }
    else tzenc[j++] = tz[i];
  }
  tzenc[j] = '\0';
  snprintf(WEATHER_URL, sizeof(WEATHER_URL),
    "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
    "&current=apparent_temperature,wind_gusts_10m,uv_index"
    "&hourly=precipitation_probability"
    "&temperature_unit=fahrenheit&wind_speed_unit=mph"
    "&timezone=%s&forecast_days=1", lat, lon, tzenc);
}

// Parse the device-ready config JSON into the globals. Returns false on malformed
// JSON or an empty route/column set (so the caller keeps the previous config).
bool configParse(const char* json) {
  JsonDocument doc;
  if (deserializeJson(doc, json)) return false;

  uint8_t nr = 0;
  for (JsonObject r : doc["routes"].as<JsonArray>()) {
    if (nr >= MAX_ROUTES) break;
    strlcpy(ROUTES[nr].route, r["route"] | "", sizeof(ROUTES[nr].route));
    strlcpy(ROUTES[nr].stopId, r["stop_id"] | "", sizeof(ROUTES[nr].stopId));
    ROUTES[nr].feedIndex = r["feed"] | 0;
    nr++;
  }

  uint8_t nc = 0;
  for (JsonObject c : doc["columns"].as<JsonArray>()) {
    if (nc >= MAX_COLS) break;
    ColumnConfig& cc = COLUMNS[nc];
    strlcpy(cc.label, c["label"] | "", sizeof(cc.label));
    strlcpy(cc.station, c["fallback"] | "", sizeof(cc.station));
    cc.nRoutes = 0;
    for (int v : c["route_idx"].as<JsonArray>())
      if (cc.nRoutes < MAX_MERGE && v >= 0 && v < nr) cc.routeIdx[cc.nRoutes++] = (uint8_t)v;
    cc.nFilter = 0;
    for (const char* d : c["dest_filter"].as<JsonArray>())
      if (cc.nFilter < MAX_FILTER) strlcpy(cc.destFilter[cc.nFilter++], d ? d : "", 40);
    nc++;
  }

  if (nr == 0 || nc == 0) return false;   // treat as no real config; keep previous
  NUM_ROUTES = nr;
  NUM_TRAIN_COLS = nc;

  buildWeatherUrl(doc["weather"]["lat"] | 40.7527,
                  doc["weather"]["lon"] | -73.9772,
                  doc["weather"]["tz"] | "America/New_York");
  strlcpy(CITIBIKE_STATION_ID, doc["citibike"]["station_id"] | "", sizeof(CITIBIKE_STATION_ID));
  strlcpy(DISPLAY_ID, doc["display_id"] | "", sizeof(DISPLAY_ID));
  strlcpy(DEVICE_PIN, doc["pin"] | "", sizeof(DEVICE_PIN));   // null (claimed) -> ""
  CONFIG_REV = doc["config_rev"] | 0;
  return true;
}

// The current Grand Central board, used when the server and NVS are both
// unavailable so a fresh/offline board still shows something.
void configLoadDefault() {
  static const char* DEFAULT_JSON =
    "{\"config_rev\":0,"
    "\"weather\":{\"lat\":40.7527,\"lon\":-73.9772,\"tz\":\"America/New_York\"},"
    "\"citibike\":{\"station_id\":\"66dea8ff-0aca-11e7-82f6-3863bb44ef7c\"},"
    "\"routes\":["
      "{\"route\":\"4\",\"stop_id\":\"631N\",\"feed\":0},"
      "{\"route\":\"4\",\"stop_id\":\"631S\",\"feed\":0},"
      "{\"route\":\"5\",\"stop_id\":\"631S\",\"feed\":0},"
      "{\"route\":\"6\",\"stop_id\":\"631S\",\"feed\":0},"
      "{\"route\":\"7\",\"stop_id\":\"723S\",\"feed\":0}],"
    "\"columns\":["
      "{\"label\":\"4\",\"fallback\":\"Woodlawn\",\"route_idx\":[0],\"dest_filter\":[\"Woodlawn\"]},"
      "{\"label\":\"4/5\",\"fallback\":\"Brooklyn\",\"route_idx\":[1,2],\"dest_filter\":[]},"
      "{\"label\":\"6\",\"fallback\":\"Bklyn Bridge\",\"route_idx\":[3],\"dest_filter\":[]},"
      "{\"label\":\"7\",\"fallback\":\"34 St-Hudson Yds\",\"route_idx\":[4],\"dest_filter\":[]}]}";
  configParse(DEFAULT_JSON);
}

void configSaveRaw(const char* json) {
  Preferences p;
  if (p.begin("subwayboard", false)) { p.putString("cfg", json); p.end(); }
}

bool configLoadNVS() {
  Preferences p;
  if (!p.begin("subwayboard", true)) return false;
  String s = p.getString("cfg", "");
  p.end();
  return s.length() && configParse(s.c_str());
}
