# CLAUDE.md — project context for Claude Code

Auto-loaded each session. Captures how this project is built and the non-obvious
decisions behind it, so a fresh session (e.g. on another computer) has the
context. User-facing details live in `README.md` and `emulator/README.md`.

## What this is

An NYC **subway + weather e-ink door display**: firmware for an ELECROW
CrowPanel 5.79″ e-paper panel (ESP32-S3, 792×272, dual SSD1683), **plus** a
pixel-faithful **browser emulator** (in `emulator/`) that runs the same board on
a computer so changes can be seen before flashing hardware. No API keys anywhere.

## Two halves, kept in lock-step

1. **Firmware** — Arduino/C++ in the repo root (`board_main.cpp`, `display.cpp`,
   `gtfs_rt.cpp`, `weather.cpp`, `EPD*`, plus generated `helvfont.h` /
   `stopnames.h`).
2. **Emulator** — Python in `emulator/` (`server.py`, `render.py`, `board_data.py`,
   `weather.py`, `gtfs_rt.py`, `stops.py`, `citibike.py`, `board_config.py`). A
   faithful port of the firmware that serves the board at http://127.0.0.1:8080.

**Discipline: every display/behavior change goes into BOTH, and they must render
identically.** `iconlib.py` (repo root) is shared — the emulator draws its icons
live and `genfont.py` bakes the *same* drawings into the firmware, so they match
byte-for-byte.

## Generated files — rerun the generators after changing inputs

- `genfont.py` → **`helvfont.h`** (Helvetica bitmap fonts + all icons). Rerun
  after changing any font size or icon. Needs Pillow + **macOS system fonts**.
- `genstops.py` → **`stopnames.h`** (stop id → name **and lat/lon**, sorted for
  binary search). Rerun after changing the stop set. Reads
  `emulator/stops_cache.csv` or downloads the MTA static GTFS.

Both `helvfont.h` and `stopnames.h` are committed (the Arduino build needs them);
the emulator runtime caches (`stops_cache.csv`, `citibike_station.json`) are
gitignored and regenerate on first run.

## Run it

- **Emulator:** `cd emulator && python3 server.py` → open http://127.0.0.1:8080.
  Needs Pillow. **Reads macOS font paths** (`/System/Library/Fonts/Helvetica.ttc`,
  `Apple Symbols.ttf`) in `render.py`/`iconlib.py`, so it renders as-is on a Mac;
  on Windows/Linux repoint those paths.
- **Device:** flash as-is (no `secrets.h` needed) and it boots into a self-serve
  WiFi setup hotspot — see "WiFi setup" in `README.md`. `secrets.h.example` →
  `secrets.h` is only a dev shortcut so your own board auto-connects on every
  reflash. Arduino IDE "ESP32S3 Dev Module" + OPI PSRAM + Huge APP.

## Data sources (all key-free)

- **MTA GTFS-realtime** — subway trip updates + service alerts (hand-rolled
  protobuf reader, no library).
- **Open-Meteo** — weather (feels-like, wind gusts, UV, hourly precip).
- **Citi Bike GBFS** — e-bikes at the nearest station.

## Key decisions & gotchas (the load-bearing knowledge)

- **Direction is inferred from geography, not the feed.** The feed only encodes
  binary **N/S** (stop-id suffix + NYCT extension) — never true E/W. We compute
  the real N/S/E/W by the dominant axis of the bearing from the current stop to
  the next train's terminal, using stop coordinates. That's *why* `stopnames.h`
  carries lat/lon. The arrow left of each bullet comes from this (e.g. the 7 →
  Hudson Yards correctly shows **W**).
- **Destinations are live.** Each column's sub-label is the next train's terminal
  (last `stop_time_update`), mapped to a name. Merged columns follow the soonest
  train. Per-column `destFilter` keeps only chosen destinations (e.g. the uptown
  4 to Woodlawn but not its 149 St short-turns).
- **Destination label sizing:** one **uniform** size across all columns (the
  largest that fits every label), floored at **15px** (`helv15`), names capped to
  **3 words**, over-wide labels truncated.
- **Icons:** Apple Symbols has ☀ ⚡ ☂ but **no wind or bicycle glyph** (those are
  color-emoji only). So wind, the e-bike (bike + bolt), and the direction arrows
  are **hand-drawn in `iconlib.py`** and shared. Arrows are one up-arrow rotated
  90°/180°/270° (pixel-clean).
- **Citi Bike on the device:** GBFS has no per-station endpoint; `station_status`
  is ~**960 KB**. The device fetches the whole feed and scans for a **hardcoded**
  `CITIBIKE_STATION_ID` (station_id is the first field in each object, so the
  first `num_ebikes_available` after it is the right one). This required bumping
  `FEED_BUF_SIZE` to **1.5 MB** (lives in PSRAM). The emulator instead finds the
  nearest station by lat/lon and caches the id.
- **`min`** is rendered in a smaller face (`helv18`) beside each arrival number.
- **Arrivals:** 3 per column (1 big + 2 rows).

## Verifying firmware changes without the Arduino toolchain

`display.cpp` / `board_main.cpp` can't compile off-device (Arduino deps). The
pattern used here: compile the **Arduino-free** parts with host `c++`
(`gtfs_rt.cpp`, `config.h`, `weather.cpp`), and write small **host harnesses**
that `#include "helvfont.h"`/`"stopnames.h"` to confirm the firmware produces the
**same** results as the emulator — text widths, chosen font sizes, `travelDir`
directions, and icon bytes. Keep that parity as the definition of "done".

## Current configuration (all in `config.h` / `board_config.py`)

- Grand Central: **4 → Woodlawn** only (`631N`, filtered), **4/5 downtown**
  (`631S`), **6 downtown** (`631S`), **7 → 34 St-Hudson Yards** (`723S`).
- Weather at Grand Central; Citi Bike station **E 44 St & 2 Ave**
  (`66dea8ff-...`).
- Repo is public: `github.com/adnanbasrai/e-ink-display`. `upstream` remote is
  the original `pzelle/NYC-front-door-hub`.
