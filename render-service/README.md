# SubwayBoard preview render service

Renders any board config to a PNG that is **pixel-identical to the panel**, by
reusing the emulator's renderer (`emulator/render.py`). The editor calls it (via
the Worker's `/api/preview`) to show "Now" vs "After your change".

```
POST /preview   { "config": <device-config> }   ->  image/png (792x272)
GET  /health                                     ->  ok
```

`<device-config>` is the same shape the board fetches (see `backend/README.md`).

## Run locally (Mac)

Python 3.9+ and Pillow (already needed by the emulator). Uses the Mac's system
fonts by default, so it just works:

```bash
cd render-service
python3 server.py            # http://127.0.0.1:8090
# test:
curl -s -X POST http://127.0.0.1:8090/preview \
  -H 'Content-Type: application/json' \
  -d '{"config": { ...device config... }}' -o preview.png
```

## How it reuses the emulator

`server.py` adds `../emulator` to the path and calls `board_data.BoardState`
with a per-request config object (built by `adapter.py` from the device-config
JSON). The emulator was refactored so `BoardState`/`render.render` accept a
config instead of importing `board_config.py`, so there is a single renderer.
Upstream feeds are cached ~30 s so a before+after pair doesn't double-download.

## Deploy (Fly.io, scale-to-zero)

Fonts: for exact parity, drop your Mac's `Helvetica.ttc` + `Apple Symbols.ttf`
into `fonts/` first (see `fonts/README.md`).

```bash
# from the repo root (build context needs emulator/ + iconlib.py):
fly launch --config render-service/fly.toml --no-deploy   # first time; pick a name
fly deploy --config render-service/fly.toml
```

Then set the Worker's `RENDER_SERVICE_URL` var to the deployed URL
(e.g. `https://subwayboard-render.fly.dev`) so the editor's preview renders:

```bash
cd ../backend && wrangler deploy   # after editing RENDER_SERVICE_URL in wrangler.toml
```

Railway/Render work too — point them at `render-service/Dockerfile` with the repo
root as build context.

## Font env vars

| Var | Default (macOS) | Purpose |
|---|---|---|
| `FONT_HELV` | `/System/Library/Fonts/Helvetica.ttc` | regular face |
| `FONT_HELV_INDEX` | `0` | face index within the file |
| `FONT_HELV_BOLD` | = `FONT_HELV` | bold face file |
| `FONT_HELV_BOLD_INDEX` | `1` | bold face index (macOS ttc) |
| `FONT_SYM` | `/System/Library/Fonts/Apple Symbols.ttf` | ☀/☂ symbols |
| `RENDER_HOST` / `PORT` | `127.0.0.1` / `8090` | bind (container sets `0.0.0.0`) |
