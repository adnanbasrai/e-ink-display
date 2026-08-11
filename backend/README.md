# SubwayBoard config backend (Cloudflare Worker + D1)

Stores each board's settings and serves the device a ready-to-use config JSON.
The board fetches `GET /api/config?device=<MAC>`; owners edit via a web page after
signing in with the **display ID + PIN** shown on the board's screen.

## Files

| File | What |
|---|---|
| `wrangler.toml` | Worker + D1 binding + vars |
| `schema.sql` | D1 tables: `devices`, `stops`, `citibike_stations` |
| `src/index.js` | Router + all endpoints |
| `src/config.js` | Default config, line→feed map, friendly→device resolution |
| `src/editor.js` | The editor web page (interim JSON editor; pickers land in Phase 4) |

## One-time setup

Requires **Node 18+**. Install Wrangler and log in to your (free) Cloudflare account:

```bash
npm install -g wrangler
wrangler login
```

Create the database, then paste the printed `database_id` into `wrangler.toml`:

```bash
cd backend
wrangler d1 create subwayboard
```

Apply the schema (local dev copy and production):

```bash
wrangler d1 execute subwayboard --file=schema.sql
wrangler d1 execute subwayboard --remote --file=schema.sql
```

Set secrets:

```bash
wrangler secret put SESSION_SECRET   # any long random string (signs edit sessions)
wrangler secret put ADMIN_TOKEN      # any long random string (guards /api/admin/*)
```

## Run locally

```bash
wrangler dev
# then, in another shell:
curl "http://127.0.0.1:8787/api/config?device=1cdbd455da5c"
# -> default config JSON, plus a fresh display_id + pin (the board would show these)
```

`--remote` note: `wrangler dev` uses a **local** D1 by default; add `--remote` to hit
the deployed database. Seed the same DB you test against.

## Deploy

```bash
wrangler deploy
# note the printed URL, e.g. https://subwayboard.<you>.workers.dev
```

Point the firmware's `WORKER_BASE` at that URL (Phase 2), and set
`RENDER_SERVICE_URL` in `wrangler.toml` once the preview service is deployed
(Phase 3) so the editor's preview renders.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/config?device=<MAC>` | none | Device pulls config; auto-registers unknown MACs; `If-None-Match: "<rev>"` → 304 |
| POST | `/api/login` | none | `{display_id, pin}` → edit session token |
| POST | `/api/devices/:id/config` | session | Resolve `{edit}` → store; bumps `config_rev` |
| POST | `/api/preview` | session | `{edit}` or `{config}` → PNG via the render service |
| GET | `/api/catalog/stops?q=` | none | Station search (needs seeding — Phase 4) |
| GET | `/api/catalog/citibike?q=` | none | CitiBike station search |
| GET | `/api/admin/devices` | admin | List boards + status |
| GET | `/` or `/edit` | — | Editor page |

## Config shapes

**Device-ready** (what the board fetches — same shape as `emulator/board_config.py`):

```json
{
  "config_rev": 3,
  "weather": { "lat": 40.7527, "lon": -73.9772, "tz": "America/New_York" },
  "citibike": { "station_id": "66dea8ff-..." },
  "cadence": { "alerts_every_min": 5, "weather_every_min": 30, "citibike_every_min": 2 },
  "routes":  [ { "route": "4", "stop_id": "631N", "feed": 0 }, ... ],
  "columns": [ { "label": "4", "fallback": "Woodlawn", "route_idx": [0], "dest_filter": ["Woodlawn"] }, ... ],
  "display_id": "SB-4F2A",
  "pin": "123456"
}
```

**Friendly edit** (what the editor POSTs — the Worker resolves it to the above):

```json
{
  "name": "My Board",
  "weather": { "lat": 40.7527, "lon": -73.9772, "tz": "America/New_York" },
  "citibike": { "station_id": "66dea8ff-..." },
  "cadence": { "alerts_every_min": 5, "weather_every_min": 30, "citibike_every_min": 2 },
  "columns": [
    { "label": "4", "fallback": "Woodlawn",
      "trains": [ { "line": "4", "stop_id": "631", "direction": "N" } ],
      "dest_filter": ["Woodlawn"] }
  ]
}
```

Limits mirror the firmware (`src/config.js` `LIMITS`): ≤12 distinct routes (the
alert parser caps at 16), ≤4 columns, ≤2 merged lines per column.

## Security notes (MVP)

- PIN is possession-based (read off the board's screen) and nulled after first
  sign-in. `POST /api/login` should be rate-limited before any public exposure.
- The device config fetch is public by MAC (config isn't secret); writes require a
  signed session. Pin the Cloudflare cert on-device later.
