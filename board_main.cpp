// NYC Subway arrivals board for the ELECROW CrowPanel 5.79" e-paper display
// (ESP32-S3, 792x272, dual SSD1683).
//
// Shows arrivals for the 4/5/6/7 at Grand Central-42 St plus a weather + Citi
// Bike column, refreshed every minute from the MTA's GTFS-realtime feeds
// (no API key required). Stops/routes/columns are configured in config.h.
//
// Board settings (Arduino IDE): "ESP32S3 Dev Module", PSRAM: "OPI PSRAM",
// Partition Scheme: "Huge APP". See README.md.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>

#include "config.h"
#include "config_fetch.h"
#include "gtfs_rt.h"
#include "display.h"
#include "weather.h"
#include "EPD.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copy secrets.h.example to secrets.h and fill in your WiFi credentials."
#endif

#define EPD_POWER_PIN 7      // panel power enable -- must be HIGH or screen stays blank
#define POWER_LED_PIN 41

#define FEED_BUF_SIZE (1536 * 1024)  // Citi Bike station_status is ~960 KB (PSRAM)
#define NYC_TZ "EST5EDT,M3.2.0/2,M11.1.0/2"

static const char* FEED_URLS[NUM_FEEDS] = { FEED_IRT, FEED_BDFM, FEED_NQRW, FEED_ACE };

uint8_t ImageBW[27200];          // (800/8) x 272 framebuffer
static uint8_t* feedBuf = nullptr;

// Last successful arrivals per route; kept when a fetch fails so the board
// degrades to slightly-stale times instead of blanking out.
static RouteArrivals arrivals[MAX_ROUTES];
static RouteAlert routeAlerts[MAX_ROUTES];
static uint32_t lastFetchOkMs[NUM_FEEDS] = {0};
static int refreshCount = 0;
static WeatherInfo weather = {};
static uint32_t lastWeatherMs = 0;
static int ebikes = -1;              // Citi Bike e-bikes at station (-1 = unknown)
static uint32_t lastCitibikeMs = 0;
static uint32_t lastConfigMs = 0;    // last remote-config fetch
static uint32_t appliedRev = 0;      // CONFIG_REV the arrivals arrays were built for

// ---------- e-paper push helpers ----------

static void pushFull() {
  EPD_FastMode1Init();
  EPD_Display_Clear();
  EPD_Update();
  EPD_FastMode1Init();
  EPD_Display(ImageBW);
  EPD_FastUpdate();
  EPD_WriteOldRAM(ImageBW);    // partials diff against this frame from now on
  EPD_DeepSleep();
}

// Two-pass anti-ghosting cycle. Pass 1 flushes the panel to white with a
// full inversion update (kills any residue). Pass 2 draws the frame using
// Elecrow's exact proven sequence (re-init + fast update -- the OTP full
// update never renders content on this panel, only the fast one does).
// Because the draw always starts from a freshly flushed white panel,
// the fast waveform has nothing to smear -- ghosting cannot accumulate.
static void pushClean() {
  uint32_t t = millis();
  EPD_FastMode1Init();
  EPD_Display_Clear();         // new RAM = white, old RAM = black (max drive)
  EPD_Update();
  Serial.printf("  clear+update %lu ms\n", millis() - t);

  t = millis();
  EPD_FastMode1Init();         // panel needs a re-init between two updates
  EPD_Display(ImageBW);
  EPD_FastUpdate();
  Serial.printf("  draw+update %lu ms\n", millis() - t);
  EPD_WriteOldRAM(ImageBW);
  EPD_DeepSleep();
}

static void splash(const char* line1, const char* line2) {
  Paint_Clear(WHITE);
  EPD_ShowString(24, 90, line1, 48, BLACK);
  if (line2) EPD_ShowString(24, 160, line2, 24, BLACK);
  pushFull();
}

// ---------- network ----------

static bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) delay(250);
  return WiFi.status() == WL_CONNECTED;
}

// Fetch one GTFS-rt feed into feedBuf. Returns payload length, 0 on failure.
static size_t fetchFeed(const char* url) {
  WiFiClientSecure client;
  client.setInsecure();        // MTA feed is public data; skip cert pinning
  client.setHandshakeTimeout(10);   // seconds; a wedged TLS handshake must not hang the board
  Serial.printf("GET %.60s\n", url);
  HTTPClient http;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(client, url)) return 0;
  int code = http.GET();
  Serial.printf("  -> %d, %d bytes\n", code, http.getSize());
  if (code != HTTP_CODE_OK) {
    http.end();
    return 0;
  }

  // Stop at Content-Length when known -- these servers use keep-alive, so
  // waiting for connection close would burn the full idle timeout per fetch.
  int expected = http.getSize();   // -1 when chunked/unknown
  WiFiClient* stream = http.getStreamPtr();
  size_t total = 0;
  uint32_t lastData = millis();
  while (http.connected() && millis() - lastData < (uint32_t)HTTP_TIMEOUT_MS) {
    if (expected > 0 && total >= (size_t)expected) break;
    size_t avail = stream->available();
    if (!avail) { delay(10); continue; }
    if (total + avail > FEED_BUF_SIZE) avail = FEED_BUF_SIZE - total;
    if (!avail) break;         // buffer full
    int n = stream->readBytes(feedBuf + total, avail);
    if (n <= 0) break;
    total += n;
    lastData = millis();
  }
  http.end();
  return total;
}

// Fetch + parse every feed, updating `arrivals` in place. A route's times are
// only replaced when its feed downloads and parses successfully.
// Fetch + parse the weather forecast into `weather` (kept on failure).
static void updateWeather() {
  size_t len = fetchFeed(WEATHER_URL);
  if (!len || len >= FEED_BUF_SIZE) {
    Serial.printf("weather fetch failed (len=%u)\n", (unsigned)len);
    return;
  }
  feedBuf[len] = '\0';
  time_t now = time(nullptr);
  struct tm tm_now;
  localtime_r(&now, &tm_now);
  WeatherInfo fresh;
  if (weatherParse((const char*)feedBuf, tm_now.tm_hour, fresh)) {
    weather = fresh;
    Serial.printf("weather: feels %dF, gust %dmph, UV %d(%s), rain %d%%@%dh\n",
                  weather.feels, weather.gusts, weather.uv, weather.uvLevel,
                  weather.rainProb, weather.rainHour);
  } else {
    Serial.println("weather parse failed");
  }
  lastWeatherMs = millis();
}

// Scan the GBFS station_status JSON for our station's e-bike count. Each object
// lists station_id first, so the first num_ebikes_available after our id is
// ours. Returns -1 if the station isn't found.
static int parseCitibikeEbikes(const char* json, const char* stationId) {
  const char* p = strstr(json, stationId);
  if (!p) return -1;
  const char* k = strstr(p, "\"num_ebikes_available\":");
  if (!k) return -1;
  return atoi(k + strlen("\"num_ebikes_available\":"));
}

static void updateCitibike() {
  if (!CITIBIKE_STATION_ID[0]) { ebikes = -1; return; }  // no station -> hide the row
  size_t len = fetchFeed(CITIBIKE_STATUS_URL);
  if (!len || len >= FEED_BUF_SIZE) {
    Serial.printf("citibike fetch failed (len=%u)\n", (unsigned)len);
    return;
  }
  feedBuf[len] = '\0';
  int e = parseCitibikeEbikes((const char*)feedBuf, CITIBIKE_STATION_ID);
  if (e >= 0) { ebikes = e; Serial.printf("citibike: %d e-bikes\n", ebikes); }
  else Serial.println("citibike: station not found");
  lastCitibikeMs = millis();
}

static void updateArrivals(bool withAlerts) {
  for (int f = 0; f < NUM_FEEDS; f++) {
    // Fresh scratch entries for the routes served by this feed.
    RouteArrivals fresh[MAX_ROUTES];
    size_t nFresh = 0;
    for (int r = 0; r < NUM_ROUTES; r++) {
      if (ROUTES[r].feedIndex != f) continue;
      fresh[nFresh].route = ROUTES[r].route;
      fresh[nFresh].stopId = ROUTES[r].stopId;
      fresh[nFresh].count = 0;
      nFresh++;
    }
    if (!nFresh) continue;

    size_t len = fetchFeed(FEED_URLS[f]);
    size_t nEntities = 0;
    if (!len || !gtfsRtParse(feedBuf, len, fresh, nFresh, &nEntities)) {
      Serial.printf("feed %d failed (len=%u)\n", f, (unsigned)len);
      continue;                // keep previous data for these routes
    }
    if (nEntities == 0) {
      // Empty/near-empty 200 (CDN or proxy hiccup): don't let it wipe the
      // last-good times to "no service". Keep stale data; the age counter and
      // the bottom-right "data N min old" line will surface the staleness.
      Serial.printf("feed %d empty body; keeping last-good\n", f);
      continue;
    }
    lastFetchOkMs[f] = millis();

    for (size_t i = 0; i < nFresh; i++)
      for (int r = 0; r < NUM_ROUTES; r++)
        if (arrivals[r].route == fresh[i].route && arrivals[r].stopId == fresh[i].stopId)
          arrivals[r] = fresh[i];
  }

  // Service alerts (the "why isn't it running" blurbs). The feed is ~430 KB,
  // so it's only fetched every few minutes; kept from the last good fetch
  // on failure, same as arrivals.
  if (!withAlerts) return;
  RouteAlert fresh[MAX_ROUTES];
  for (int r = 0; r < NUM_ROUTES; r++) {
    fresh[r].route = ROUTES[r].route;
    fresh[r].text[0] = '\0';
  }
  size_t len = fetchFeed(FEED_ALERTS);
  if (len && gtfsAlertsParse(feedBuf, len, (uint32_t)time(nullptr), fresh, NUM_ROUTES)) {
    memcpy(routeAlerts, fresh, sizeof(routeAlerts));
  } else {
    Serial.printf("alerts feed failed (len=%u)\n", (unsigned)len);
  }
}

// ---------- remote config ----------

// Point the per-route arrival/alert buffers at the current ROUTES[]. Called
// after the config is (re)loaded, since a config change can alter the route set.
static void initArrivals() {
  for (int r = 0; r < NUM_ROUTES; r++) {
    arrivals[r].route = ROUTES[r].route;
    arrivals[r].stopId = ROUTES[r].stopId;
    arrivals[r].count = 0;
    routeAlerts[r].route = ROUTES[r].route;
    routeAlerts[r].text[0] = '\0';
  }
}

// Pull this board's settings from the backend (keyed by its MAC) and parse them
// into the config globals. Caches the raw JSON in NVS on success. Returns false
// on any failure so the caller can keep the previous settings.
static bool fetchConfig() {
  String url = String(WORKER_BASE) + "/api/config?device=" + deviceId();
  size_t len = fetchFeed(url.c_str());
  if (!len || len >= FEED_BUF_SIZE) {
    Serial.printf("config fetch failed (len=%u)\n", (unsigned)len);
    return false;
  }
  feedBuf[len] = '\0';
  if (!configParse((const char*)feedBuf)) {
    Serial.println("config parse failed");
    return false;
  }
  configSaveRaw((const char*)feedBuf);
  Serial.printf("config rev %u: %u routes / %u cols, id=%s pin=%s\n",
                (unsigned)CONFIG_REV, NUM_ROUTES, NUM_TRAIN_COLS, DISPLAY_ID, DEVICE_PIN);
  return true;
}

// ---------- rendering ----------

static void renderBoard() {
  time_t now = time(nullptr);
  struct tm tm_now;
  localtime_r(&now, &tm_now);

  // Age is measured only across feeds that have actually fetched OK. A feed
  // with no matching route is never fetched (its slot stays 0), so including
  // all NUM_FEEDS slots here made oldestOk permanently 0 -> the board was stuck
  // on "waiting for data" even while IRT updated fine, and the "data N min old"
  // staleness warning could never appear. Mirror the emulator: min() over the
  // feeds with a non-zero timestamp; if none have succeeded yet, "waiting".
  uint32_t oldestOk = 0;
  for (int f = 0; f < NUM_FEEDS; f++) {
    uint32_t ok = lastFetchOkMs[f];
    if (!ok) continue;                       // never fetched (or unused) -> skip
    if (!oldestOk || ok < oldestOk) oldestOk = ok;
  }

  char clockBuf[16], bottomRight[40];
  strftime(clockBuf, sizeof(clockBuf), "%l:%M %p", &tm_now);
  const char* clockTrim = clockBuf[0] == ' ' ? clockBuf + 1 : clockBuf;
  uint32_t ageMin = oldestOk ? (millis() - oldestOk) / 60000UL : 0;
  if (!oldestOk)
    snprintf(bottomRight, sizeof(bottomRight), "waiting for data  %s", clockTrim);
  else if (ageMin >= 3)
    snprintf(bottomRight, sizeof(bottomRight), "data %lu min old  %s",
             (unsigned long)ageMin, clockTrim);
  else
    snprintf(bottomRight, sizeof(bottomRight), "%s", clockTrim);

  displayRender(arrivals, NUM_ROUTES, now, routeAlerts, weather, refreshCount, bottomRight, ebikes);

  uint32_t t0 = millis();
  pushClean();                 // white-flush + redraw, every minute
  Serial.printf("refresh #%d took %lu ms\n", refreshCount, millis() - t0);
  refreshCount++;
}

// ---------- arduino entry points ----------

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("SubwayBoard boot");

  pinMode(EPD_POWER_PIN, OUTPUT);
  digitalWrite(EPD_POWER_PIN, HIGH);
  pinMode(POWER_LED_PIN, OUTPUT);
  digitalWrite(POWER_LED_PIN, HIGH);

  EPD_GPIOInit();
  Paint_NewImage(ImageBW, EPD_W, EPD_H, Rotation, WHITE);
  Paint_Clear(WHITE);

  feedBuf = (uint8_t*)ps_malloc(FEED_BUF_SIZE);
  if (!feedBuf) feedBuf = (uint8_t*)malloc(FEED_BUF_SIZE);
  if (!feedBuf) {
    // Almost always a mis-set build (OPI PSRAM off). Show it, then reboot and
    // retry rather than sitting bricked -- a power-cycle can't be assumed when
    // the unit lives at a friend's house.
    splash("ERROR", "Feed buffer alloc failed - enable OPI PSRAM");
    delay(60000);
    ESP.restart();
  }

  splash("NYC Subway", "Connecting to WiFi...");

  if (!ensureWiFi()) {
    // The router may just be rebooting when the display powers on. Don't wedge
    // forever waiting for a human to press RST -- reboot and try again. The
    // loop() path already tolerates later WiFi drops via ensureWiFi().
    splash("No WiFi", "Retrying shortly...");
    delay(15000);
    ESP.restart();
  }
  Serial.printf("WiFi up: %s\n", WiFi.localIP().toString().c_str());

  // NTP -- arrival math needs real epoch time.
  configTzTime(NYC_TZ, "pool.ntp.org", "time.nist.gov");
  uint32_t start = millis();
  while (time(nullptr) < 1600000000 && millis() - start < 30000) delay(200);
  Serial.printf("ntp: %ld\n", (long)time(nullptr));

  // Load settings: try the backend, fall back to the NVS cache, then the baked
  // default, so the board always has something to show.
  splash("NYC Subway", "Loading settings...");
  if (!fetchConfig()) {
    if (configLoadNVS()) Serial.println("config: using cached settings");
    else { configLoadDefault(); Serial.println("config: using built-in default"); }
  }
  // Until the board is claimed on the website, show its sign-in ID + PIN so the
  // owner can read them off the screen.
  if (DEVICE_PIN[0]) {
    char l2[40];
    snprintf(l2, sizeof(l2), "ID %s  PIN %s", DISPLAY_ID, DEVICE_PIN);
    splash("Set up online:", l2);
    delay(5000);
  }
  initArrivals();
  appliedRev = CONFIG_REV;

  updateWeather();
  updateCitibike();
  updateArrivals(true);
  refreshCount = 0;            // first paint is a full refresh
  renderBoard();
}

// Each cycle is aligned to the wall clock: fetching starts ~20 s before the
// next minute boundary, then the e-ink refresh is held until the minute
// ticks -- so the screen flips exactly as the displayed time changes, once
// every 60 seconds.
void loop() {
  time_t now = time(nullptr);
  time_t target = (now / 60 + 1) * 60;
  bool withAlerts = ((target / 60) % ALERTS_EVERY_MIN) == 0;
  bool withWeather = millis() - lastWeatherMs >= WEATHER_INTERVAL_MS;
  bool withCitibike = millis() - lastCitibikeMs >= (uint32_t)CITIBIKE_EVERY_MIN * 60000UL;
  bool withConfig = millis() - lastConfigMs >= CONFIG_REFETCH_MS;
  int prefetch = 20 + (withAlerts ? 20 : 0) + (withWeather ? 5 : 0)
                    + (withCitibike ? 15 : 0) + (withConfig ? 5 : 0);

  while (time(nullptr) < target - prefetch) delay(200);

  uint32_t t0 = millis();
  if (!ensureWiFi()) {
    Serial.println("WiFi reconnect failed; showing stale data");
  } else {
    // Re-pull settings first; if they changed on the website, rebuild the
    // per-route buffers before fetching arrivals into them.
    if (withConfig) {
      if (fetchConfig() && CONFIG_REV != appliedRev) { initArrivals(); appliedRev = CONFIG_REV; }
      lastConfigMs = millis();
    }
    if (withWeather) updateWeather();
    if (withCitibike) updateCitibike();
    updateArrivals(withAlerts);
  }
  Serial.printf("fetch took %lu ms (alerts=%d)\n", millis() - t0, withAlerts);

  while (time(nullptr) < target) delay(50);
  renderBoard();
}
