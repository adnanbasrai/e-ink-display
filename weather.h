#pragma once

// Parsed Open-Meteo forecast for the board's weather column: feels-like
// temperature, wind gusts, UV index (+ level), and the peak upcoming rain
// probability with the hour it happens.
struct WeatherInfo {
  bool valid;
  int feels;             // apparent (feels-like) temperature, °F
  int gusts;             // wind gusts, mph
  int uv;                // UV index, rounded
  const char* uvLevel;   // "Low" / "Med" / "High"
  int rainProb;          // peak precip probability over rest of day (%)
  int rainHour;          // local hour 0-23 of that peak, or -1 if below threshold
};

// Parse an Open-Meteo response (current=apparent_temperature,wind_gusts_10m,
// uv_index + hourly=precipitation_probability, forecast_days=1, NY timezone).
// `hourNow` is the current local hour 0-23; the rain window runs hourNow..23.
// Pure string scanning, no JSON library. Returns false if required fields miss.
bool weatherParse(const char* json, int hourNow, WeatherInfo& out);
