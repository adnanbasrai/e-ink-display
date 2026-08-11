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

// Read up to `maxN` numbers from a JSON array starting at/just before '['.
// null entries become -1. Returns count.
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

const char* uvLevel(int uv) { return uv < 3 ? "Low" : uv < 6 ? "Med" : "High"; }

}  // namespace

bool weatherParse(const char* json, int hourNow, WeatherInfo& out) {
  out.valid = false;
  out.rainProb = 0;
  out.rainHour = -1;
  out.uvLevel = "Low";

  // Anchor to the data objects. "current_units"/"hourly_units" don't match
  // these patterns (they end in `_units":`, not `":`), so we hit the real ones.
  const char* cur = strstr(json, "\"current\":");
  const char* hourly = strstr(json, "\"hourly\":");
  if (!cur) return false;

  const char* t = afterKey(cur, "apparent_temperature");
  const char* g = afterKey(cur, "wind_gusts_10m");
  const char* u = afterKey(cur, "uv_index");
  if (!t || !g) return false;
  out.feels = (int)lroundf(strtof(t, nullptr));
  out.gusts = (int)lroundf(strtof(g, nullptr));
  out.uv = u ? (int)lroundf(strtof(u, nullptr)) : 0;
  out.uvLevel = uvLevel(out.uv);

  // Peak precipitation probability from the current hour through 11 PM.
  const char* pp = hourly ? afterKey(hourly, "precipitation_probability") : nullptr;
  float probs[24];
  int nProb = pp ? readNumArray(pp, probs, 24) : 0;
  int from = hourNow < 0 ? 0 : hourNow;
  int bestP = 0, bestH = -1;
  for (int h = from; h < 24 && h < nProb; h++) {
    if (probs[h] < 0) continue;
    int p = (int)probs[h];
    if (p > bestP) { bestP = p; bestH = h; }
  }
  if (bestP >= 25) { out.rainProb = bestP; out.rainHour = bestH; }

  out.valid = true;
  return true;
}
