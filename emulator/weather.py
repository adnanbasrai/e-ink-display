"""Open-Meteo forecast parsing for the redesigned weather column.

Pulls the fields the board now shows: feels-like temperature, wind gusts, UV
index (+ Low/Med/High), and the peak upcoming rain probability and the hour it
happens. Key-free, same API. Mirrored by the firmware's weather.cpp.
"""

RAIN_THRESHOLD = 25   # only surface a rain row at or above this probability (%)


class WeatherInfo:
    def __init__(self):
        self.valid = False
        self.feels = 0        # apparent (feels-like) temperature, F
        self.gusts = 0        # wind gusts, mph
        self.uv = 0           # UV index, rounded
        self.uv_level = ""    # "Low" / "Med" / "High"
        self.rain_prob = 0    # peak precip probability over the rest of the day (%)
        self.rain_hour = -1   # local hour (0-23) of that peak, or -1 if below threshold


def _uv_level(uv):
    if uv < 3:
        return "Low"
    if uv < 6:
        return "Med"
    return "High"


def weather_parse(data, hour_now):
    """data = parsed JSON from the Open-Meteo forecast endpoint."""
    out = WeatherInfo()
    cur = data.get("current") or {}
    try:
        out.feels = round(float(cur["apparent_temperature"]))
        out.gusts = round(float(cur["wind_gusts_10m"]))
        out.uv = round(float(cur.get("uv_index", 0)))
    except (KeyError, TypeError, ValueError):
        return out
    out.uv_level = _uv_level(out.uv)

    hourly = data.get("hourly", {}) or {}
    probs = hourly.get("precipitation_probability", []) or []
    start = 0 if hour_now < 0 else hour_now
    best_p, best_h = 0, -1
    for h in range(start, min(24, len(probs))):
        p = probs[h]
        if p is None:
            continue
        if int(p) > best_p:
            best_p, best_h = int(p), h
    if best_p >= RAIN_THRESHOLD:
        out.rain_prob, out.rain_hour = best_p, best_h

    out.valid = True
    return out
