// Self-serve WiFi setup portal (see wifi_provision.h).
//
// Uses only libraries already bundled with the esp32 Arduino core -- WiFi,
// WebServer, DNSServer, Preferences -- so no extra library install is needed.
// The approach is the standard ESP32 captive-portal pattern (the same one
// WiFiManager-style libraries use): start a SoftAP, answer every DNS query
// with our own IP, and answer the OS's captive-portal probe URLs with our
// setup page so the phone auto-opens it instead of reporting "no internet".

#include "wifi_provision.h"

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <vector>
#include <algorithm>

#if __has_include("secrets.h")
#include "secrets.h"   // optional dev fallback: WIFI_SSID / WIFI_PASSWORD
#endif

namespace {

WebServer* gServer = nullptr;
String gApSsid;
volatile bool gSaved = false;

String htmlEscape(const String& s) {
  String out;
  out.reserve(s.length());
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    if (c == '&') out += "&amp;";
    else if (c == '<') out += "&lt;";
    else if (c == '>') out += "&gt;";
    else if (c == '"') out += "&quot;";
    else out += c;
  }
  return out;
}

const char* PAGE_HEAD =
  "<!doctype html><html><head><meta charset='utf-8'>"
  "<meta name='viewport' content='width=device-width,initial-scale=1'>"
  "<title>SubwayBoard setup</title><style>"
  "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
  "background:#14161a;color:#e6e9ee;margin:0;padding:24px 20px;max-width:420px}"
  "h1{font-size:18px;line-height:1.4}"
  "label{display:block;font-size:12px;color:#8a909a;margin:14px 0 4px}"
  "select,input[type=text],input[type=password]{width:100%;padding:11px;"
  "border-radius:8px;border:1px solid #333;background:#0f1114;color:#eee;"
  "font-size:16px;box-sizing:border-box}"
  "button{width:100%;padding:13px;margin-top:18px;border-radius:8px;border:0;"
  "background:#2d6;color:#08130a;font-weight:700;font-size:16px}"
  "p.hint{color:#7d8590;font-size:12.5px}"
  "a{color:#5af}</style></head><body>";

void sendPage(const String& body) {
  String html = String(PAGE_HEAD) + body + "</body></html>";
  gServer->send(200, "text/html; charset=utf-8", html);
}

// GET / (and every unmatched/captive-probe path): scan + show the setup form.
void sendRoot() {
  int n = WiFi.scanNetworks(false /*async*/, false /*hidden*/);
  struct Net { String ssid; int rssi; };
  std::vector<Net> nets;
  for (int i = 0; i < n; i++) {
    String s = WiFi.SSID(i);
    if (!s.length()) continue;
    bool dup = false;
    for (auto& x : nets) {
      if (x.ssid == s) { dup = true; if (WiFi.RSSI(i) > x.rssi) x.rssi = WiFi.RSSI(i); break; }
    }
    if (!dup) nets.push_back({s, WiFi.RSSI(i)});
  }
  std::sort(nets.begin(), nets.end(), [](const Net& a, const Net& b) { return a.rssi > b.rssi; });

  String body = "<h1>Connect &ldquo;" + htmlEscape(gApSsid) + "&rdquo; to your WiFi</h1>";
  body += "<form method='POST' action='/save'>";
  body += "<label>Network</label><select id='ssidSel'><option value=''>-- choose --</option>";
  for (auto& x : nets)
    body += "<option value='" + htmlEscape(x.ssid) + "'>" + htmlEscape(x.ssid) + "</option>";
  body += "</select>";
  body += "<label>Or type the network name (for hidden networks)</label>"
          "<input type='text' id='ssidManual' name='ssid' autocomplete='off' autocapitalize='off'>";
  body += "<label>Password</label><input type='password' name='pass' autocomplete='off'>";
  body += "<button type='submit'>Connect</button></form>";
  body += "<p class='hint'>Your board will restart and join this network. "
          "2.4&thinsp;GHz only -- the board has no 5&thinsp;GHz radio.</p>";
  body += "<script>document.getElementById('ssidSel').addEventListener('change',function(){"
          "document.getElementById('ssidManual').value=this.value;});</script>";
  sendPage(body);
}

void sendResult(bool ok, const String& msg) {
  String body = "<h1>" + String(ok ? "Connected" : "Couldn&rsquo;t connect") + "</h1><p>" + msg + "</p>";
  if (!ok) body += "<p><a href='/'>&larr; Try again</a></p>";
  sendPage(body);
}

// POST /save: test the given network before saving anything, so a typo'd
// password can't brick the board into an unreachable "saved" state.
void handleSave() {
  String ssid = gServer->arg("ssid");
  String pass = gServer->arg("pass");
  ssid.trim();
  if (!ssid.length()) { sendResult(false, "Pick or type a network name."); return; }

  Serial.printf("wifi portal: trying \"%s\"\n", ssid.c_str());
  WiFi.begin(ssid.c_str(), pass.c_str());
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(200);

  if (WiFi.status() == WL_CONNECTED) {
    Preferences p;
    if (p.begin("wifi", false)) {
      p.putString("ssid", ssid);
      p.putString("pass", pass);
      p.end();
    }
    sendResult(true, "Your board will restart and join &ldquo;" + htmlEscape(ssid) + "&rdquo; now.");
    gSaved = true;   // lets the loop in wifiRunPortal() fall through and reboot
  } else {
    WiFi.disconnect();
    sendResult(false, "Wrong password, or that network wasn't reachable. Nothing was saved.");
  }
}

}  // namespace

String wifiApSsid() {
  // Deliberately NOT WiFi.macAddress(): that only returns real data once the
  // WiFi driver has been fully started (mode-set alone isn't enough, and
  // there's a startup delay), so on a truly fresh board -- no saved network,
  // no secrets.h fallback -- it silently reads back all zeros before the
  // driver's ever been used, giving a useless "SubwayBoard-0000" for every
  // board. ESP.getEfuseMac() reads the factory-burned MAC straight from
  // efuse, valid from the very first instruction, no WiFi driver involved.
  uint64_t mac = ESP.getEfuseMac();
  char suffix[5];
  snprintf(suffix, sizeof(suffix), "%04X", (unsigned)(mac & 0xFFFF));
  return "SubwayBoard-" + String(suffix);
}

bool wifiHasStoredCreds() {
  bool has = false;
  Preferences p;
  if (p.begin("wifi", true)) {
    has = p.getString("ssid", "").length() > 0;
    p.end();
  }
#if defined(WIFI_SSID)
  if (!has && WIFI_SSID[0]) has = true;   // dev fallback (secrets.h), optional
#endif
  return has;
}

bool wifiTryStored(uint32_t timeoutMs) {
  // Bring the radio up unconditionally, even if we end up with no SSID to try:
  // WiFi.macAddress() (used to name the setup hotspot for a truly fresh board,
  // in wifiApSsid()) only reads real efuse data once the driver has been
  // initialized at least once -- otherwise it silently returns all zeros.
  WiFi.mode(WIFI_STA);

  String ssid, pass;
  Preferences p;
  if (p.begin("wifi", true)) {
    ssid = p.getString("ssid", "");
    pass = p.getString("pass", "");
    p.end();
  }
#if defined(WIFI_SSID)
  if (!ssid.length() && WIFI_SSID[0]) { ssid = WIFI_SSID; pass = WIFI_PASSWORD; }
#endif
  if (!ssid.length()) return false;

  WiFi.begin(ssid.c_str(), pass.c_str());
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) delay(250);
  return WiFi.status() == WL_CONNECTED;
}

void wifiForget() {
  Preferences p;
  if (p.begin("wifi", false)) { p.clear(); p.end(); }
}

// GPIO0 ("BOOT") -- owned entirely by this module now; see the big warning in
// wifi_provision.h about why it must never be sampled at boot/reset time.
#define WIFI_BOOT_BTN_PIN 0
#define WIFI_HOLD_MS 3000   // how long a press must be held to count

// The reprovision flag lives in ITS OWN namespace, separate from "wifi" --
// wifiForget() clears the whole "wifi" namespace, and if the flag lived
// there too it would erase itself before the next boot ever saw it.
bool wifiConsumeReprovisionFlag() {
  Preferences p;
  bool set = false;
  if (p.begin("boot", false)) {
    set = p.getUChar("reprov", 0) != 0;
    if (set) p.putUChar("reprov", 0);
    p.end();
  }
  return set;
}

namespace {
void markReprovision() {
  Preferences p;
  if (p.begin("boot", false)) { p.putUChar("reprov", 1); p.end(); }
}
}  // namespace

void wifiPollReprovisionButton(WifiStatusFn onStatus) {
  static bool pinReady = false;
  static uint32_t heldSince = 0;
  if (!pinReady) { pinMode(WIFI_BOOT_BTN_PIN, INPUT_PULLUP); pinReady = true; }

  bool held = (digitalRead(WIFI_BOOT_BTN_PIN) == LOW);
  if (!held) { heldSince = 0; return; }
  if (!heldSince) { heldSince = millis(); return; }
  if (millis() - heldSince < WIFI_HOLD_MS) return;

  Serial.println("BOOT held during normal operation -> WiFi setup requested");
  if (onStatus) onStatus("Release the button now", "to reset WiFi setup...");
  // Wait for release BEFORE restarting -- restarting while GPIO0 is still
  // held would strand the chip in the flashing bootloader (see the header).
  while (digitalRead(WIFI_BOOT_BTN_PIN) == LOW) delay(50);

  markReprovision();
  wifiForget();
  if (onStatus) onStatus("WiFi setup requested", "Restarting...");
  delay(500);
  ESP.restart();   // does not return
}

void wifiRunPortal(WifiStatusFn onStatus) {
  gApSsid = wifiApSsid();
  gSaved = false;

  // AP_STA (not just AP) so handleSave() can test-connect the station radio
  // to the friend's network while the hotspot they're browsing on stays up.
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(gApSsid.c_str());   // open network -- local + temporary, see README
  delay(200);
  IPAddress apIP = WiFi.softAPIP();

  static DNSServer dns;
  dns.start(53, "*", apIP);       // every DNS lookup resolves to us

  static WebServer server(80);
  gServer = &server;
  server.on("/", HTTP_GET, sendRoot);
  server.on("/save", HTTP_POST, handleSave);
  // OS captive-portal probe URLs: answering these (instead of 404ing) is what
  // makes the phone auto-pop the setup page instead of just saying "no internet".
  static const char* PROBES[] = {
    "/generate_204", "/gen_204", "/hotspot-detect.html",
    "/library/test/success.html", "/ncsi.txt", "/connecttest.txt",
  };
  for (auto path : PROBES) server.on(path, HTTP_GET, sendRoot);
  server.onNotFound(sendRoot);
  server.begin();

  Serial.printf("wifi portal: join \"%s\" (open) from a phone to set up\n", gApSsid.c_str());
  if (onStatus) {
    char l2[40];
    snprintf(l2, sizeof(l2), "WiFi: %s", gApSsid.c_str());
    onStatus("Set up your board:", l2);
  }

  while (!gSaved) {
    dns.processNextRequest();
    server.handleClient();
    delay(2);
  }

  server.stop();
  dns.stop();
  WiFi.softAPdisconnect(true);
  if (onStatus) onStatus("Connected!", "Restarting...");
  delay(1200);
  ESP.restart();   // boot cleanly into normal station-mode operation
}
