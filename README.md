# SubwayBoard

Live NYC subway arrivals on an ELECROW CrowPanel 5.79" e-paper display
(ESP32-S3, 792×272, dual SSD1683).

Five columns, all set in Helvetica (bitmap fonts generated from the Mac's
real Helvetica by `genfont.py`):

- **Weather** — current temp, high/low, and a symbol for today's coming
  weather (now → 10 PM): storm (cloud + bolt) > rain (umbrella) > snow
  (snowflake), with the precip probability beneath. Data from Open-Meteo,
  no API key.
- **2/3** at Nevins St (`234N`)
- **4/5** at Nevins St (`234N`)
- **A** at Hoyt-Schermerhorn (`A42N`)
- **B/Q** at DeKalb Av (`R30N`)

Each train column: MTA-style bullet, station name, next train in big digits,
then the three following trains (plain minutes, no unit). Columns with no
upcoming service show a dash + "no service", and the ticker line at the
bottom cycles the MTA's own alert blurb explaining why (or a fallback for
scheduled gaps like the weekend B). Train data comes straight from the MTA's
public GTFS-realtime feeds — **no API key needed**.

The screen does a clean full refresh (factory OTP waveform — the panel's
"fast" waveform ghosts badly on this unit) aligned to every minute boundary:
fetching starts ~20 s before the minute, and the e-ink flip is held until
the minute ticks. A clear-to-white deep clean runs every 30th update. The
alerts feed (~430 KB) is only fetched every 5 minutes.

## Setup

1. Copy `secrets.h.example` to `secrets.h` and fill in your WiFi SSID and
   password (2.4 GHz networks only — the ESP32 has no 5 GHz radio).

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
| `gtfs_rt.{h,cpp}` | Hand-rolled GTFS-realtime protobuf reader (trips + alerts) |
| `weather.{h,cpp}` | Open-Meteo JSON parse + storm/rain/snow priority logic |
| `display.{h,cpp}` | Board layout: bullets, station names, weather, ticker |
| `helvfont.h` | Generated Helvetica bitmaps + weather symbols |
| `genfont.py` | Regenerates `helvfont.h` (needs Pillow, macOS fonts) |
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
