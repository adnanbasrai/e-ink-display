#pragma once
#include <Arduino.h>

// Runtime config helpers (config_runtime.cpp). The actual HTTP GET lives in
// board_main.cpp (fetchConfig) so it can reuse fetchFeed()/feedBuf; these are
// the pieces around it: identity, JSON parsing into the config globals, the
// baked default, and the NVS cache.

String deviceId();                     // stable per-board id from the WiFi MAC
bool   configParse(const char* json);  // JSON -> ROUTES/COLUMNS/... globals
void   configLoadDefault();            // Grand Central fallback
void   configSaveRaw(const char* json);// cache the raw config JSON in NVS
bool   configLoadNVS();                // load + parse the cached JSON (if any)
