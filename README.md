# SubwayBoard

Live NYC subway arrivals on an ELECROW CrowPanel 5.79" e-paper display
(ESP32-S3, 792×272, dual SSD1683).

Five columns, all set in Helvetica (bitmap fonts generated from the Mac's
real Helvetica by `genfont.py`):

- **Weather + transit status** — big **feels-like** temperature, then rows
  for **wind gusts**, **rain** likelihood + the hour it happens (only when
  likely), **UV index** + Low/Med/High, and **Citi Bike e-bikes** at your
  nearest station. Weather from Open-Meteo; bikes from the Citi Bike GBFS
  feed — both need **no API key**. (The Citi Bike feed is ~960 KB, so
  `FEED_BUF_SIZE` in `board_main.cpp` is bumped to 1.5 MB of PSRAM and the
  station id is set in `config.h`.)
- **4/5** at Grand Central, uptown (`631N`)
- **4/5** at Grand Central, downtown (`631S`)
- **6** at Grand Central, downtown (`631S`)
- **7** at Grand Central, toward Hudson Yards (`723S`)

(Stops/routes/columns are all set in `config.h` — see Configuration below.)

Each train column: a **direction arrow** (N/S/E/W) left of the MTA-style bullet
— the true compass heading, inferred from the next train's terminal coordinates
vs the current station (the feed only encodes N/S, so this is the only way to
know the 7 goes *west*) — then the **destination of the next train** (where it's
headed — its terminal, pulled live from the feed and mapped to a station name
via `stopnames.h`), the next train in big digits, and the two
following trains, every time in minutes ("5 min"). Merged columns (e.g. `4/5`)
tag each time with its route, and the destination follows the soonest train. Columns
with no upcoming service show a dash + "no service" and a fallback label, and
the ticker line at the bottom cycles the MTA's own alert blurb explaining why.
Train data comes straight from the MTA's public GTFS-realtime feeds — **no API
key needed**.

The screen does a clean full refresh (factory OTP waveform — the panel's
"fast" waveform ghosts badly on this unit) aligned to every minute boundary:
fetching starts ~20 s before the minute, and the e-ink flip is held until
the minute ticks. A clear-to-white deep clean runs every 30th update. The
alerts feed (~430 KB) is only fetched every 5 minutes.

## Setup

1. **WiFi credentials are optional at flash time.** A freshly-flashed board
   with no `secrets.h` (or a blank one) boots straight into its own WiFi
   setup hotspot — see [WiFi setup](#wifi-setup) below. For your own dev
   board, copy `secrets.h.example` to `secrets.h` and fill in your SSID/
   password instead, as a shortcut so it auto-connects on every reflash
   (2.4 GHz only — the ESP32 has no 5 GHz radio).

2. Arduino IDE → Boards Manager → install **esp32 by Espressif Systems**.

3. Open `SubwayBoard.ino` and select board **ESP32S3 Dev Module** with:
   - **PSRAM: "OPI PSRAM"** (required — the feed buffer lives there)
   - Partition Scheme: **"Huge APP (3MB No OTA/1MB SPIFFS)"**
   - Flash Size: 8MB

4. Plug in the board (USB-C) and upload. If the upload doesn't start:
   hold **BOOT**, tap **RST**, release BOOT, then retry. If it's flaky at
   921600 baud, drop the upload speed to 460800 or 115200.

   Or from the terminal with arduino-cli:

   ```sh
   arduino-cli compile --fqbn "esp32:esp32:esp32s3:PSRAM=opi,PartitionScheme=huge_app,FlashSize=8M" .
   arduino-cli upload -p /dev/cu.usbmodem*  --fqbn "esp32:esp32:esp32s3:PSRAM=opi,PartitionScheme=huge_app,FlashSize=8M" .
   ```

The board boots, connects to WiFi, syncs time via NTP, then fetches and
draws arrivals every 60 seconds (partial refresh; every 10th update is a
full flashing refresh to clear ghosting).

## WiFi setup

The intended flow for giving a board to someone else: flash it once with no
WiFi credentials baked in, hand it over, they connect it to their own network
themselves. No laptop, no re-flash, nobody sees anybody else's password.

1. Power on a board with no saved network (a fresh flash, or after a re-setup
   — see below). The screen shows **"Set up your board: WiFi:
   SubwayBoard-XXXX"** and the board starts broadcasting that name as an open
   WiFi hotspot.
2. On a phone, join **"SubwayBoard-XXXX"**. A setup page should pop up
   automatically (standard captive-portal behavior); if not, open a browser
   and go to any `http://` address.
3. Pick your home network from the list (or type its name for a hidden
   network), enter the password, and tap **Connect**.
4. The board tests the network before saving anything — if the password's
   wrong, nothing is saved and you can try again. On success it saves the
   network and restarts onto it.

**To re-run setup later** (e.g. the WiFi password changed): hold the **BOOT**
button while powering the board on. That forgets the saved network and starts
the hotspot again. (On an enclosed board where BOOT isn't reachable, a
re-flash has the same effect — nothing else about the board's settings is
lost, since those live on the backend, not on the device.)

A board with a known network that's just temporarily unreachable (router
rebooting, etc.) does **not** drop into setup mode on its own — it retries the
saved network, so a brief outage doesn't strand the board in hotspot mode with
nobody around to reconnect it.

## Configuration

Everything tunable is in `config.h`:

- `ROUTES[]` — routes/stops fetched. Stop IDs are the MTA's GTFS ids with a
  direction suffix (`N` = Manhattan-bound at these stations). Find other
  stations' ids in the MTA static GTFS `stops.txt`.
- `COLUMNS[]` — the four train columns: bullet label, station name, and
  which ROUTES entries merge into the column.
- `WEATHER_URL` — Open-Meteo query (location is downtown Brooklyn).
- `UPDATE_INTERVAL_MS` — refresh cadence (default 60 s)
- `FULL_REFRESH_EVERY` — full-refresh interval, in updates (default 30)
- `WEATHER_INTERVAL_MS` — weather re-fetch interval (default 30 min)
- `ARRIVALS_SHOWN` — arrivals listed per column (default 4)

## Files

| File | What |
|---|---|
| `SubwayBoard.ino` | Stub (Arduino IDE requires it); logic is in `board_main.cpp` |
| `board_main.cpp` | WiFi + NTP + fetch/parse/render loop |
| `config.h` | Routes, columns, stops, feeds, weather URL, cadence |
| `gtfs_rt.{h,cpp}` | Hand-rolled GTFS-realtime protobuf reader (trips + alerts); also captures each trip's terminal for the destination label |
| `weather.{h,cpp}` | Open-Meteo parse: feels-like temp, wind gusts, UV, peak rain prob + hour |
| `iconlib.py` | Shared hand-drawn 1-bit icons (wind) for both the panel and the emulator |
| `display.{h,cpp}` | Board layout: bullets, destinations, weather, ticker |
| `helvfont.h` | Generated Helvetica bitmaps (incl. small `helv11`) + weather symbols |
| `genfont.py` | Regenerates `helvfont.h` (needs Pillow, macOS fonts) |
| `stopnames.h` | Generated stop-id → station-name table (destination labels) |
| `genstops.py` | Regenerates `stopnames.h` from the MTA static GTFS |
| `emulator/` | Runs the whole board on your computer in a browser (see `emulator/README.md`) |
| `EPD*.{h,cpp}`, `spi.{h,cpp}` | Elecrow's CrowPanel 5.79" panel driver (dual SSD1683, bit-banged SPI) + `EPD_WriteOldRAM` ghosting fix |
| `secrets.h.example` | Template for WiFi credentials |

## Hardware notes

- Panel power is gated by **GPIO 7** — it must be driven HIGH or the screen
  stays blank (the sketch does this in `setup()`).
- The 792×272 panel is two cascaded SSD1683 controllers with an 8-column
  dead zone at the seam; Elecrow's driver hides this (framebuffer is 800×272).
- Empty columns ≠ bug: the B doesn't run on weekends, and weekend service
  changes regularly remove the 2/3 from Brooklyn. The MTA feeds only carry
  trains that are actually running.
