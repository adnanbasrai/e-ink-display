# SubwayBoard — Code Audit & Fleet Roadmap

_Full audit of the firmware (C++) and emulator (Python), plus an architecture
plan for the goal of manufacturing multiple displays and a sign-in website where
owners edit their own board by device ID._

Severity: **HIGH** = visible/reliability bug, **MEDIUM** = bites under specific
conditions, **LOW** = quality/robustness. Line numbers reflect the code at audit
time.

---

## Fixes already applied in this pass

These four were fixed immediately (see the parity note — each was mirrored into
both halves where relevant):

| Fix | Files | What changed |
|---|---|---|
| **Firmware always "waiting for data"** | `board_main.cpp` `renderBoard()` | Freshness was min()'d across all 4 feed slots, but only feed 0 (IRT) is ever fetched, so the oldest-OK was permanently 0 → board stuck on "waiting for data" and the "data N min old" staleness warning could never show. Now min()'s only over feeds that have actually succeeded, matching the emulator. |
| **Empty 200 wipes last-good arrivals** | `gtfs_rt.{h,cpp}`, `board_main.cpp`, `emulator/gtfs_rt.py`, `emulator/board_data.py` | A zero-byte/near-empty 200 "parsed" as success and swapped in empty data → every column flashed to "no service". The parser now reports the FeedEntity count; a count of 0 means keep last-good data instead of wiping. |
| **Weather rounding parity break** | `emulator/weather.py` | Python's `round()` is banker's rounding; the firmware uses `lroundf()` (half away from zero). At `.5` boundaries they disagreed — including a UV of 2.5 flipping the Low/Med **label**. Emulator now uses a matching `_lround()`. |
| **Boot freezes forever on no-WiFi / no-PSRAM** | `board_main.cpp` `setup()` | Two `while(true)` traps meant a unit powered on while the router was rebooting stayed bricked until a human pressed RST. Now shows the error briefly then `ESP.restart()`s to self-recover. |

Verified: emulator unit checks (rounding boundaries, empty/malformed feed) pass;
live emulator re-renders correctly; firmware parser edits pass a host
`-fsyntax-only` compile. **The firmware changes still need an on-device flash to
confirm** (they can't be fully compiled off the Arduino toolchain).

---

## Parity note (important before touching either half)

The project's golden rule is that the firmware and emulator render **identically,
dot for dot**. Several things that _look_ like bugs are faithful shared ports and
must be changed on **both** sides together or not at all:

- Merge/sort of arrivals is by whole **minute**, not seconds (`display.cpp`
  ↔ `render.py`) — same stable tie-break.
- `minutesUntil` / `minutes_until` — identical, including the 45-second
  "just-departed = 0" grace.
- `travelDir` / `direction4` — identical direction inference, including the
  cos-latitude correction and the `>=` tie-to-N/S.
- Direction/destination pick the **soonest** train globally and use
  `route_idxs[0]`'s stop — identical on both sides.

---

## Firmware audit (C++)

### High
1. **Always "waiting for data"** — _fixed._ (see above)
2. **No self-recovery.** Boot traps froze forever (_fixed_). ~~WiFi credentials
   live in `secrets.h` at compile time~~ — _fixed_: `wifi_provision.{h,cpp}`
   adds a self-serve captive-portal setup (a fresh board broadcasts its own
   hotspot with a setup page; hold BOOT to re-provision), so handing a unit to
   a friend no longer needs a per-household re-flash. There is still no
   watchdog to reboot a wedged state during normal operation.

### Medium
3. **Wrong destination/arrow for trips with >24 remaining stops.**
   `gtfs_rt.cpp:138,160-171` buffers stops into `pending[MAX_ARRIVALS*2]` (24) and
   treats `pending[last]` as the terminal. A station early in a long route can
   exceed 24, making the 24th stop masquerade as the terminal — feeding a wrong
   destination label _and_ possibly a wrong N/E/S/W arrow. Latent for Grand
   Central. Fix: track the terminal as the highest stop_sequence seen (or the
   last streamed) without capping; cap only the match buffer.
4. **Worst-case fetch (~105 s) overruns the 60 s cycle.** `HTTP_TIMEOUT_MS=15000`
   × up to 7 sequential TLS fetches. On bad WiFi the minute-aligned refresh falls
   behind. Fix: 5–8 s per-fetch timeout and/or an overall fetch budget; reuse the
   TLS connection to the shared MTA host.
5. **Citi Bike parse is order-dependent and truncates silently.**
   `board_main.cpp:171-177` takes the first `num_ebikes_available` after the
   station id (GBFS doesn't guarantee key order); `fetchFeed` silently caps at
   `FEED_BUF_SIZE` (the ~960 KB feed is growing toward 1.5 MB). Fix: parse within
   the station's `{…}` object; flag truncation explicitly.
6. **One bad protobuf record discards the whole feed.** `gtfs_rt.cpp:322` aborts
   the entire message on any malformed entity. Safe (keeps stale) but
   all-or-nothing. Fix: skip to the next FeedEntity and continue.
7. **Per-fetch `WiFiClientSecure` churns TLS buffers → heap fragmentation** with
   no reboot on sustained failure. `board_main.cpp:107`. Fix: log free heap;
   `ESP.restart()` after N consecutive failures / below a heap floor.
8. **TLS verification disabled** (`setInsecure()`, `board_main.cpp:108`). Public
   data, but alert text is rendered verbatim, so a local MITM could inject fake
   alerts. Fix: pin the root CA, or document the accepted risk.

### Low
9. No bounds check in `Paint_SetPixel` (`EPD.cpp:66`) — over-wide text could
   corrupt `ImageBW`. Add an early-out clamp.
10. Route matching by `const char*` pointer equality (`board_main.cpp:215`) —
    works only because both point at the same literal. Use `strcmp`.
11. Dead code / duplication: `FULL_REFRESH_EVERY` unused; `EPD_WhiteScreen_ALL_Fast`
    unused; `EPD_Display`/`EPD_WriteOldRAM` near-duplicate; weather/citibike
    fetch-guard copy-pasted; destFilter computed twice per column.
12. Magic numbers: `1600000000` NTP sanity, timeout literals, panel seam offsets,
    the `16`-alert cap.

### Verified correct (don't re-audit)
Protobuf bounds-checking; `insertSorted` eviction; framebuffer addressing exactly
fills `ImageBW[27200]`; DST via `configTzTime`; bounded 10 s panel busy-wait;
weather hourly-index alignment.

---

## Emulator audit (Python)

### High
- **H1 — empty 200 wipes last-good arrivals** — _fixed._
- **H2 — TLS verification disabled + no response-size cap.** `board_data.py:29-31`,
  `stops.py:24-26`, `citibike.py:17-19`; `_fetch` does `r.read()` with no ceiling.
  The firmware's stale-cert justification doesn't apply on macOS. Fix: use a
  verified context in the emulator (gate any skip behind an explicit flag), and
  cap reads (e.g. 4 MB) treating overflow as failure.
- **H3 — weather rounding divergence** — _fixed._

### Medium
- **M1 — module-level macOS font paths crash off-macOS.** `render.py:43-44,110`.
  `import render` raises on Linux/Windows with a raw traceback. Fix: read font
  paths from config/env with macOS defaults; fail with a one-line message.
- **M2 — timezone fallback silently uses host local time.** `board_data.py:21-24`,
  `weather.py:44-53`. Off-NY host → wrong clock and a mis-picked peak-rain hour.
  Fix: bundle `tzdata` or warn loudly.
- **M3 — a startup Citi Bike failure disables e-bikes for the whole session.**
  `board_data.py:67-72`. Fix: retry the station lookup lazily in
  `update_citibike`.
- **M4 — `/refresh` does blocking, unauthenticated network I/O under the shared
  lock.** `server.py:49-60,284-295`. Fine on localhost; a DoS amplifier in any
  hosted future. Fix (hosted): rate-limit, coalesce concurrent presses, add
  deadlines.

### Low
- **L1** direction uses the column's first-route stop, not the soonest train's
  (shared with firmware — fix both together). `render.py:288`.
- **L2** nearest-station uses uncorrected lat/lon distance (no cos-lat term).
  `citibike.py:41`.
- **L3** arrival dedup by exact second can drop two distinct trips. `gtfs_rt.py:38`.
- **L4** non-ASCII station chars (en-dash, accents) are silently dropped from
  labels. `render.py:59`.
- **L6** importing the parser transitively loads fonts → blocks headless tests;
  add table-driven tests for `gtfs_rt_parse` / `weather_parse`.
- **L7** duplication (12-hour clock ×3), dead `STATION_Y`, no direction arrows
  when names came from the bundled fallback (no coords), no port validation.

---

## Architecture roadmap — hardware fleet + sign-in website

**The decisive move: invert the topology.** Build a small backend that does all
fetching, parsing, and rendering — keyed by device ID — and turn each ESP32 into
a thin client that pulls one compact per-device payload and draws it.

**Why:**
- The Python emulator (`board_data.py` + `render.py`) **is** the backend
  renderer — reuse it, don't rewrite it.
- Today each device pulls ~1–2 MB/min (mostly the 960 KB Citi Bike feed) to make
  a 27 KB image. A backend fetches each upstream feed **once** and fans out to
  the whole fleet; per-device traffic drops ~100×.
- The 1.5 MB PSRAM requirement exists only to hold that raw feed on-device —
  remove on-device parsing and future boards get cheaper.
- One place to fix parsing, retries, certs, and schema changes for all units.
- The "keep two halves in lock-step" burden largely dissolves — one renderer.

**Payload:** have the backend render to the existing **27,200-byte 1-bit
framebuffer** (compresses to single-digit KB); the device just blits it and runs
the e-ink waveform. Keep a device-side "last good frame" cache + an on-screen
"offline / data N min old" indicator so the display degrades gracefully when the
backend is unreachable (the backend becomes a hard dependency — the main risk).

**Config / identity / provisioning:**
- Config moves from `config.h` into a `device_config` row whose JSON is _exactly_
  the `board_config.py` shape — don't invent a second schema.
- Each board gets a device ID + secret in NVS; show a short **claim code** on the
  e-ink screen at first boot; the owner enters it in the portal to bind
  device ↔ account. Pin the backend cert (replace `setInsecure()`).
- WiFi via **captive-portal** provisioning (WiFiManager-style) — no re-flash per
  friend. _Done: `wifi_provision.{h,cpp}` (self-serve hotspot + setup page)._

**Stack:** FastAPI wrapping the existing Pillow renderer + Postgres (SQLite to
start), one small VM. The portal is a **picker over a station catalog** (built
from `stopnames.h` / GBFS) with a **live PNG preview from the same renderer**.

**Data model:** `users`, `devices(id, secret_hash, panel_profile, user_id,
claim_code, last_seen, fw_version)`, `device_config(device_id, json, config_rev)`,
plus read-only `stops` / `citibike_stations` catalogs.

### Phased roadmap
| Phase | What | Payoff |
|---|---|---|
| **0** | Move config out of `config.h` into a JSON file the device fetches from a URL | Re-point a friend's board without re-flashing — proves the pattern, zero infra |
| **1** | Wrap the emulator as a backend; serve `frame.bin` per device; fetch feeds once | ~100× less device traffic; retires firmware issues #4–8. **Do before anything user-facing.** |
| **2** | Thin the firmware to fetch + blit; delete on-device parsing/fonts | New boards trivial and identical |
| **3** | Device identity + secret, cert pinning, captive-portal WiFi, claim-code screen | "Give to friends" works hands-off |
| **4** | Web portal: accounts, claim flow, station picker, live preview | The visible product |
| **5** | OTA (switch off the "No OTA" partition scheme) + signed images + health dashboard | Fleet maintenance |

**Don't over-engineer:** one small VM with an in-process feed cache is plenty for
a handful of friends — no Redis/k8s; no battery optimization until a battery
variant exists; reuse the emulator config schema; keep the emulator as the local
dev renderer.
