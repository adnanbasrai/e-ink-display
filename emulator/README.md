# SubwayBoard e-ink emulator

Runs the SubwayBoard firmware's logic on your computer and draws the exact
792×272 board in a browser, so you can see live NYC subway arrivals + weather
before flashing the real ELECROW CrowPanel 5.79″ e-paper display.

It is a faithful Python port of the device code:

| Emulator file | Ports from firmware |
|---|---|
| `gtfs_rt.py` | `gtfs_rt.cpp` — hand-rolled GTFS-realtime protobuf reader (trips + alerts) |
| `weather.py` | `weather.cpp` — Open-Meteo parse + storm/rain/snow priority |
| `render.py` | `display.cpp` — the whole board layout, same fonts + geometry |
| `board_config.py` | `config.h` — routes, stops, columns, feeds, weather URL, cadence |
| `board_data.py` | `board_main.cpp` — fetch loop, keep-last-good, clock/age line |
| `server.py` | the Arduino `loop()` — minute-aligned refresh + a web "device" |
| `stops.py` | *(emulator-only)* MTA `stops.txt` → station names for destinations |
| `citibike.py` | Citi Bike GBFS: nearest station + its e-bike count (no key) |
| `../iconlib.py` | Shared hand-drawn wind icon (also baked into the firmware) |

### Destination labels

The label under each bullet is the **destination of the next train**, derived
live from the feed: each trip's last stop is its terminal, mapped to a station
name via the MTA static `stops.txt` (downloaded once, cached to
`stops_cache.csv`). Change a stop or route in `board_config.py` and the
destination follows automatically — nothing to relabel. For a merged column
(e.g. `4/5`) it shows where the *soonest* train is headed, so it can flip
between terminals as the routes alternate; the `(4)`/`(5)` tags on each row
show which route each time belongs to. A column with no upcoming train shows
its `fallback` label instead.

The **device does this too** now: the firmware parses each trip's terminal
(`gtfs_rt.cpp`) and looks the name up in a baked table (`stopnames.h`, generated
by `genstops.py`), drawing it in a small font (`helv11`) so long names fit. The
emulator and the panel show the same destinations.

The renderer uses the same faces the device does (macOS **Helvetica** regular +
bold at 18/28/40 px and **Apple Symbols** for the weather glyphs — the exact
fonts `genfont.py` bakes into `helvfont.h`), thresholded the same way, so the
pixels match the panel.

## Run it

Requires macOS (for the fonts), Python 3.9+, and Pillow. Nothing else — no
API keys, no pip packages beyond Pillow.

```sh
python3 -m pip install --user Pillow      # once, if you don't have it
cd emulator
python3 server.py                         # http://127.0.0.1:8080
python3 server.py 9000                    # or a custom port
```

Open **http://127.0.0.1:8080** and leave it up. The board fetches on the same
schedule as the device — every minute (aligned to the wall clock), service
alerts every 5 min, weather every 30 min — and the page flips with a little
e-ink "flash" each time, just like the panel.

## Change what it shows

Edit `board_config.py` exactly as you would edit the firmware's `config.h`
(stops, routes, columns, weather lat/long). The emulator and the device read
the same configuration, so anything you dial in here will match on hardware.

## Notes

- TLS verification is skipped for the public MTA feeds (the firmware does the
  same), so a stale system cert bundle can't block fetches.
- Empty columns are not a bug — the MTA feeds only carry trains actually
  running (e.g. the B doesn't run on weekends). The ticker explains why.
