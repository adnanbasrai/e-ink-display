#include "weather.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

namespace {

// Find `"key":` at or after `from` and return a pointer just past the colon.
const char* afterKey(const char* from, const char* key) {
  char pat[48];
  snprintf(pat, sizeof(pat), "\"%s\":", key);
  const char* p = strstr(from, pat);
  return p ? p + strlen(pat) : nullptr;
}

// Read up to `maxN` numbers from a JSON array starting at `p` (which must
// point at or just before '['). Returns count. null entries become -1.
int readNumArray(const char* p, float* out, int maxN) {
  p = strchr(p, '[');
  if (!p) return 0;
  p++;
  int n = 0;
  while (n < maxN) {
    while (*p == ' ' || *p == ',') p++;
    if (*p == ']' || *p == '\0') break;
    if (strncmp(p, "null", 4) == 0) {
      out[n++] = -1;
      p += 4;
    } else {
      char* end;
      float v = strtof(p, &end);
      if (end == p) break;
      out[n++] = v;
      p = end;
    }
  }
  return n;
}

bool isStormCode(int c) { return c == 95 || c == 96 || c == 99; }
bool isSnowCode(int c)  { return (c >= 71 && c <= 77) || c == 85 || c == 86; }
bool isRainCode(int c)  { return (c >= 51 && c <= 67) || (c >= 80 && c <= 82); }

}  // namespace

bool weatherParse(const char* json, int hourNow, WeatherInfo& out) {
  out.valid = false;
  out.cond = WX_NONE;
  out.prob = 0;

  // Anchor to the data objects -- the "*_units" objects repeat every key
  // with string values, so a whole-document key search hits those first.
  const char* cw = strstr(json, "\"current_weather\":");
  const char* hourly = strstr(json, "\"hourly\":");
  const char* daily = strstr(json, "\"daily\":");
  if (!cw || !daily) return false;

  const char* t = afterKey(cw, "temperature");
  if (!t) return false;
  out.curTemp = (int)lroundf(strtof(t, nullptr));

  const char* hi = afterKey(daily, "temperature_2m_max");
  const char* lo = afterKey(daily, "temperature_2m_min");
  if (!hi || !lo) return false;
  float hiv[1], lov[1];
  if (readNumArray(hi, hiv, 1) != 1 || readNumArray(lo, lov, 1) != 1) return false;
  out.hi = (int)lroundf(hiv[0]);
  out.lo = (int)lroundf(lov[0]);

  // Hourly arrays: index == local hour (forecast_days=1, NY timezone).
  float probs[24], codes[24];
  const char* pp = hourly ? afterKey(hourly, "precipitation_probability") : nullptr;
  const char* wc = hourly ? afterKey(hourly, "weathercode") : nullptr;
  int nProb = pp ? readNumArray(pp, probs, 24) : 0;
  int nCode = wc ? readNumArray(wc, codes, 24) : 0;

  // Classify the window from now through 10 PM: any storm hour wins, then
  // rain, then snow. Probability shown = max precip probability over the
  // window's hours (per-class when the class has hours with data).
  bool storm = false, rain = false, snow = false;
  int stormP = 0, rainP = 0, snowP = 0, anyP = 0;
  int from = hourNow < 0 ? 0 : hourNow;
  for (int h = from; h <= 22 && h < nCode; h++) {
    int c = (int)codes[h];
    int p = (h < nProb && probs[h] >= 0) ? (int)probs[h] : 0;
    if (p > anyP) anyP = p;
    if (isStormCode(c))     { storm = true; if (p > stormP) stormP = p; }
    else if (isRainCode(c)) { rain = true;  if (p > rainP)  rainP = p; }
    else if (isSnowCode(c)) { snow = true;  if (p > snowP)  snowP = p; }
  }

  if (storm)      { out.cond = WX_STORM; out.prob = stormP ? stormP : anyP; }
  else if (rain)  { out.cond = WX_RAIN;  out.prob = rainP ? rainP : anyP; }
  else if (snow)  { out.cond = WX_SNOW;  out.prob = snowP ? snowP : anyP; }
  else if (anyP >= 25) { out.cond = WX_RAIN; out.prob = anyP; }  // precip likely, code bland

  out.valid = true;
  return true;
}
