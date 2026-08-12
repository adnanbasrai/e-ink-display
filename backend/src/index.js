// SubwayBoard config Worker (Cloudflare Workers + D1).
//
// Surfaces:
//   Device:  GET  /api/config?device=<MAC>        -> device-ready JSON (+ display_id, pin)
//   Auth:    POST /api/login {display_id, pin}     -> edit session token
//   Write:   POST /api/devices/:id/config          -> resolve + store (session)
//   Preview: POST /api/preview {config}            -> PNG via the render service (session)
//   Catalog: GET  /api/catalog/stops?q=            -> station search (editor)
//            GET  /api/catalog/citibike?q=
//   Admin:   GET  /api/admin/devices               -> list boards (ADMIN_TOKEN)
//   Editor:  GET  /  and  /edit                    -> SPA (Phase 4)
//
// See backend/README.md for deploy + secrets.

import { makeDefaultConfig, makeDefaultEdit, resolveConfig } from "./config.js";
import { EDITOR_HTML } from "./editor.js";

// ---------- small helpers ----------

const nowSec = () => Math.floor(Date.now() / 1000);
const enc = new TextEncoder();

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization,If-None-Match",
};

function json(obj, status = 200, extra = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...CORS, ...extra },
  });
}
const err = (msg, status = 400) => json({ error: msg }, status);

function b64url(bytes) {
  let s = btoa(String.fromCharCode(...new Uint8Array(bytes)));
  return s.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
async function sha256Hex(str) {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(str));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const hashPin = (pin, displayId) => sha256Hex(`${pin}:${displayId}:subwayboard`);

function genPin() {
  const n = crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;
  return String(n).padStart(6, "0");
}
function genDisplayId() {
  const b = crypto.getRandomValues(new Uint8Array(2));
  const hex = [...b].map((x) => x.toString(16).padStart(2, "0")).join("").toUpperCase();
  return `SB-${hex}`;
}

// ---------- edit-session tokens (HMAC-signed) ----------

async function hmacKey(secret) {
  return crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}
async function signSession(env, deviceId, ttlSec = 2 * 3600) {
  const payload = b64url(enc.encode(JSON.stringify({ d: deviceId, exp: nowSec() + ttlSec })));
  const key = await hmacKey(env.SESSION_SECRET || "dev-insecure-secret");
  const sig = b64url(await crypto.subtle.sign("HMAC", key, enc.encode(payload)));
  return `${payload}.${sig}`;
}
async function verifySession(env, token) {
  if (!token || !token.includes(".")) return null;
  const [payload, sig] = token.split(".");
  const key = await hmacKey(env.SESSION_SECRET || "dev-insecure-secret");
  const ok = await crypto.subtle.verify(
    "HMAC", key, Uint8Array.from(atob(sig.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)),
    enc.encode(payload));
  if (!ok) return null;
  try {
    const obj = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    if (obj.exp < nowSec()) return null;
    return obj.d;
  } catch {
    return null;
  }
}
function bearer(request) {
  const h = request.headers.get("Authorization") || "";
  return h.startsWith("Bearer ") ? h.slice(7) : null;
}

// ---------- device row ----------

async function getOrCreateDevice(env, deviceId) {
  let row = await env.DB.prepare("SELECT * FROM devices WHERE device_id = ?")
    .bind(deviceId).first();
  if (row) return row;

  // Register a new board: unique display id, a PIN, and the default config.
  let displayId;
  for (let i = 0; i < 5; i++) {
    displayId = genDisplayId();
    const clash = await env.DB.prepare("SELECT 1 FROM devices WHERE display_id = ?")
      .bind(displayId).first();
    if (!clash) break;
  }
  const pin = genPin();
  const cfg = makeDefaultConfig();
  const edit = makeDefaultEdit();
  const t = nowSec();
  await env.DB.prepare(
    `INSERT INTO devices (device_id, display_id, pin_hash, pin_plain, claimed, name,
       config_json, edit_json, config_rev, created_at, last_seen_at)
     VALUES (?, ?, ?, ?, 0, NULL, ?, ?, ?, ?, ?)`
  ).bind(deviceId, displayId, await hashPin(pin, displayId), pin,
         JSON.stringify(cfg), JSON.stringify(edit), cfg.config_rev, t, t).run();
  return env.DB.prepare("SELECT * FROM devices WHERE device_id = ?").bind(deviceId).first();
}

// ---------- route handlers ----------

// Device pulls its config. Unknown MAC auto-registers. Echoes display_id + (until
// claimed) pin so the board can show them on its own screen for sign-in.
async function handleGetConfig(request, env, url) {
  const deviceId = (url.searchParams.get("device") || "").trim().toLowerCase();
  if (!/^[0-9a-f]{6,32}$/.test(deviceId)) return err("bad device id", 400);

  const dev = await getOrCreateDevice(env, deviceId);
  await env.DB.prepare("UPDATE devices SET last_seen_at = ? WHERE device_id = ?")
    .bind(nowSec(), deviceId).run();

  const etag = `"${dev.config_rev}"`;
  if (request.headers.get("If-None-Match") === etag) {
    return new Response(null, { status: 304, headers: { ETag: etag, ...CORS } });
  }
  const cfg = JSON.parse(dev.config_json);
  cfg.display_id = dev.display_id;
  cfg.pin = dev.claimed ? null : dev.pin_plain; // shown on-screen until first sign-in
  return json(cfg, 200, { ETag: etag });
}

async function handleLogin(request, env) {
  const { display_id, pin } = await request.json().catch(() => ({}));
  if (!display_id || !pin) return err("display_id and pin required");
  const dev = await env.DB.prepare("SELECT * FROM devices WHERE display_id = ?")
    .bind(String(display_id).toUpperCase()).first();
  if (!dev) return err("no such display", 404);
  if (dev.pin_hash !== (await hashPin(String(pin), dev.display_id)))
    return err("wrong PIN", 401);

  // First successful sign-in claims the board and hides the PIN from the panel.
  if (!dev.claimed) {
    await env.DB.prepare("UPDATE devices SET claimed = 1, pin_plain = NULL WHERE device_id = ?")
      .bind(dev.device_id).run();
  }
  return json({
    token: await signSession(env, dev.device_id),
    device_id: dev.device_id, display_id: dev.display_id, name: dev.name,
  });
}

async function handleWriteConfig(request, env, deviceId) {
  const sessionDevice = await verifySession(env, bearer(request));
  if (!sessionDevice || sessionDevice !== deviceId) return err("unauthorized", 401);

  const edit = await request.json().catch(() => null);
  const dev = await env.DB.prepare("SELECT config_rev FROM devices WHERE device_id = ?")
    .bind(deviceId).first();
  if (!dev) return err("no such device", 404);

  let cfg;
  try {
    cfg = resolveConfig(edit, dev.config_rev);
  } catch (e) {
    return err(`invalid config: ${e.message}`, 422);
  }
  await env.DB.prepare(
    "UPDATE devices SET config_json = ?, edit_json = ?, config_rev = ?, name = ? WHERE device_id = ?"
  ).bind(JSON.stringify(cfg), JSON.stringify(edit), cfg.config_rev, edit.name || null, deviceId).run();
  return json({ ok: true, config_rev: cfg.config_rev });
}

// The friendly editor payload, to repopulate the form on load.
async function handleGetEdit(request, env, deviceId) {
  const sessionDevice = await verifySession(env, bearer(request));
  if (!sessionDevice || sessionDevice !== deviceId) return err("unauthorized", 401);
  const dev = await env.DB.prepare("SELECT edit_json FROM devices WHERE device_id = ?")
    .bind(deviceId).first();
  if (!dev) return err("no such device", 404);
  const edit = dev.edit_json ? JSON.parse(dev.edit_json) : makeDefaultEdit();
  return json({ edit });
}

// Address -> lat/lon via Open-Meteo's key-free geocoder (proxied to avoid CORS).
async function handleGeocode(env, q) {
  if (!q || q.length < 2) return json({ results: [] });
  const u = "https://geocoding-api.open-meteo.com/v1/search?count=6&language=en&format=json&name="
    + encodeURIComponent(q);
  const r = await fetch(u);
  if (!r.ok) return json({ results: [] });
  const d = await r.json();
  const results = (d.results || []).map((x) => ({
    name: [x.name, x.admin1, x.country_code].filter(Boolean).join(", "),
    lat: x.latitude, lon: x.longitude, tz: x.timezone,
  }));
  return json({ results });
}

// Preview accepts either a friendly {edit} shape (resolved here, so the preview
// matches exactly what Save would produce) or a device-ready {config} (used for
// the "before"/current image). Proxies the device config to the render service.
async function handlePreview(request, env) {
  const sessionDevice = await verifySession(env, bearer(request));
  if (!sessionDevice) return err("unauthorized", 401);
  if (!env.RENDER_SERVICE_URL) return err("preview service not configured", 503);

  const body = await request.json().catch(() => null);
  let config;
  if (body && body.edit) {
    try { config = resolveConfig(body.edit, 0); }
    catch (e) { return err(`invalid config: ${e.message}`, 422); }
  } else if (body && body.config) {
    config = body.config;
  } else {
    return err("edit or config required", 400);
  }

  const upstream = await fetch(`${env.RENDER_SERVICE_URL.replace(/\/$/, "")}/preview`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("Content-Type") || "image/png", ...CORS },
  });
}

async function handleCatalog(env, table, q) {
  const like = `%${(q || "").replace(/[%_]/g, "")}%`;
  if (table === "stops") {
    // Group a station's stops into one row per complex, with all its lines, so
    // "Grand Central" appears once as "4 5 6 7 S" rather than three times.
    const { results } = await env.DB.prepare(
      `SELECT complex_id, name, AVG(lat) lat, AVG(lon) lon,
              GROUP_CONCAT(routes, ' ') routes
         FROM stops WHERE name LIKE ?
        GROUP BY complex_id, name ORDER BY name LIMIT 25`).bind(like).all();
    return json({ results: results || [] });
  }
  const { results } = await env.DB.prepare(
    "SELECT station_id, name, lat, lon FROM citibike_stations WHERE name LIKE ? ORDER BY name LIMIT 25")
    .bind(like).all();
  return json({ results: results || [] });
}

// All stops in a station complex, so the editor can map each line to its stop id
// (e.g. complex 610 -> {631:"4 5 6", 723:"7", 901:"S"}).
async function handleComplex(env, complexId) {
  const { results } = await env.DB.prepare(
    "SELECT stop_id, name, lat, lon, routes FROM stops WHERE complex_id = ?")
    .bind(complexId || "").all();
  return json({ results: results || [] });
}

async function handleAdminDevices(request, env) {
  if (bearer(request) !== env.ADMIN_TOKEN || !env.ADMIN_TOKEN) return err("forbidden", 403);
  const { results } = await env.DB.prepare(
    `SELECT device_id, display_id, name, claimed, config_rev, created_at, last_seen_at
       FROM devices ORDER BY created_at DESC`).all();
  return json({ devices: results || [] });
}

// ---------- router ----------

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

    try {
      if (pathname === "/" || pathname === "/edit") {
        return new Response(EDITOR_HTML, { headers: { "Content-Type": "text/html; charset=utf-8" } });
      }
      if (pathname === "/api/config" && request.method === "GET")
        return handleGetConfig(request, env, url);
      if (pathname === "/api/login" && request.method === "POST")
        return handleLogin(request, env);
      if (pathname === "/api/preview" && request.method === "POST")
        return handlePreview(request, env);
      if (pathname === "/api/catalog/stops" && request.method === "GET")
        return handleCatalog(env, "stops", url.searchParams.get("q"));
      if (pathname === "/api/catalog/citibike" && request.method === "GET")
        return handleCatalog(env, "citibike", url.searchParams.get("q"));
      if (pathname === "/api/catalog/complex" && request.method === "GET")
        return handleComplex(env, url.searchParams.get("id"));
      if (pathname === "/api/geocode" && request.method === "GET")
        return handleGeocode(env, url.searchParams.get("q"));
      if (pathname === "/api/admin/devices" && request.method === "GET")
        return handleAdminDevices(request, env);

      const m = pathname.match(/^\/api\/devices\/([^/]+)\/config$/);
      if (m && request.method === "POST")
        return handleWriteConfig(request, env, decodeURIComponent(m[1]).toLowerCase());

      const me = pathname.match(/^\/api\/devices\/([^/]+)\/edit$/);
      if (me && request.method === "GET")
        return handleGetEdit(request, env, decodeURIComponent(me[1]).toLowerCase());

      return err("not found", 404);
    } catch (e) {
      return err(`server error: ${e.message}`, 500);
    }
  },
};
