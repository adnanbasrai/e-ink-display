-- SubwayBoard D1 schema. Apply with:
--   wrangler d1 execute subwayboard --file=schema.sql            (local)
--   wrangler d1 execute subwayboard --remote --file=schema.sql   (production)

-- One row per physical board.
CREATE TABLE IF NOT EXISTS devices (
  device_id    TEXT PRIMARY KEY,        -- MAC hex the firmware sends (stable id)
  display_id   TEXT UNIQUE NOT NULL,    -- short human code shown on screen, e.g. "SB-4F2A"
  pin_hash     TEXT NOT NULL,           -- SHA-256(pin + display_id); PIN itself is shown on the panel
  pin_plain    TEXT,                    -- shown to the device until claimed, then nulled (see note)
  claimed      INTEGER NOT NULL DEFAULT 0,
  name         TEXT,
  config_json  TEXT NOT NULL,           -- device-ready config (the JSON the board fetches)
  edit_json    TEXT,                    -- friendly editor payload (to reload the form)
  config_rev   INTEGER NOT NULL DEFAULT 1,
  created_at   INTEGER NOT NULL,
  last_seen_at INTEGER
);

-- Read-only catalog the editor searches (seeded from the MTA static GTFS).
CREATE TABLE IF NOT EXISTS stops (
  stop_id    TEXT PRIMARY KEY,  -- GTFS stop id, no N/S suffix (e.g. "631")
  name       TEXT NOT NULL,
  lat        REAL,
  lon        REAL,
  routes     TEXT,              -- space-separated lines at this stop, e.g. "4 5 6"
  complex_id TEXT               -- groups a station's stops (631/723/901 share one)
);
CREATE INDEX IF NOT EXISTS idx_stops_name ON stops(name);
CREATE INDEX IF NOT EXISTS idx_stops_complex ON stops(complex_id);

-- Read-only catalog for the weather/e-bike station picker (seeded from GBFS).
CREATE TABLE IF NOT EXISTS citibike_stations (
  station_id TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  lat        REAL,
  lon        REAL
);
CREATE INDEX IF NOT EXISTS idx_cb_name ON citibike_stations(name);

-- NOTE on pin_plain: the PIN is meant to be read off the board's own screen. We
-- keep it in cleartext ONLY so the device's /api/config response can echo it back
-- to draw on the panel, until the owner first signs in (claimed=1), after which it
-- is nulled. pin_hash is what /api/login checks. For a hobby fleet this is an
-- acceptable trade; a stricter design would have the device generate its own PIN.
