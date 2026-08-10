#pragma once

// Parsed Open-Meteo forecast for the board's weather column.
enum WeatherCond : unsigned char {
  WX_NONE = 0,
  WX_STORM,   // thundercloud + bolt symbol
  WX_RAIN,    // umbrella symbol
  WX_SNOW,    // snowflake symbol
};

struct WeatherInfo {
  bool valid;
  int curTemp;      // °F, rounded
  int hi, lo;       // today's forecast high/low, °F
  WeatherCond cond; // dominant coming condition, now -> 10 PM (storm > rain > snow)
  int prob;         // precipitation probability (%) backing `cond`
};

// Parse an Open-Meteo JSON response (current_weather + hourly
// precipitation_probability/weathercode + daily max/min, forecast_days=1,
// NY timezone). `hourNow` is the current local hour 0-23; the condition
// window runs from hourNow through 22:00. Pure string scanning, no JSON
// library. Returns false if required fields are missing.
bool weatherParse(const char* json, int hourNow, WeatherInfo& out);
