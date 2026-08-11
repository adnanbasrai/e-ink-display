// The editor SPA (served at / and /edit). Sign in with the board's display ID +
// PIN, then set everything with friendly controls: an address for the weather
// location, searchable home + destination stations, a Citi Bike station, alerts
// frequency, and up to 4 trains (line + where it's heading). Saves the friendly
// shape; the Worker resolves it to the device config and can render a preview.

export const EDITOR_HTML = `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SubwayBoard — editor</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; background:#14161a; color:#c9ced6;
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    display:flex; flex-direction:column; align-items:center; padding:24px; gap:16px; }
  h1 { font-size:16px; font-weight:600; margin:0; color:#e6e9ee; }
  h1 span { color:#7d8590; font-weight:400; }
  .card { background:#1b1e24; border:1px solid #2a2f37; border-radius:12px;
    padding:18px 20px; width:min(760px,94vw); }
  .sec { padding:12px 0; border-top:1px solid #23272f; }
  .sec:first-of-type { border-top:0; }
  .lab { font-size:12px; font-weight:600; color:#8a909a; text-transform:uppercase;
    letter-spacing:.04em; margin-bottom:6px; }
  .hint { font-size:12px; color:#6e747d; margin-top:3px; }
  input, select { width:100%; background:#0f1114; color:#e6e9ee; border:1px solid #2a2f37;
    border-radius:8px; padding:9px 11px; font:inherit; }
  .pick { color:#3fb950; font-size:12.5px; margin-top:5px; min-height:16px; }
  .ac { position:relative; }
  .ac-list { position:absolute; z-index:5; left:0; right:0; top:calc(100% + 2px);
    background:#0f1114; border:1px solid #2a2f37; border-radius:8px; overflow:hidden;
    max-height:220px; overflow-y:auto; box-shadow:0 12px 30px rgba(0,0,0,.5); }
  .ac-list div { padding:8px 11px; cursor:pointer; font-size:13px; }
  .ac-list div:hover { background:#21262d; }
  .row { display:flex; gap:10px; align-items:center; }
  .row > * { min-width:0; }
  .trainrow { display:flex; gap:10px; align-items:flex-start; margin-bottom:10px; }
  .trainrow .line { flex:0 0 92px; }
  .trainrow .dest { flex:1; }
  button { appearance:none; border:1px solid #3a3f47; border-radius:8px; background:#21262d;
    color:#e6e9ee; font:inherit; font-weight:600; padding:9px 15px; cursor:pointer; }
  button:hover { background:#2b3138; } button:disabled { opacity:.5; cursor:default; }
  button.primary { background:#2d6; border-color:#2d6; color:#08130a; }
  button.link { background:none; border:none; color:#7d8590; padding:6px; font-weight:400; }
  button.x { flex:0 0 auto; background:none; border:none; color:#f85149; font-size:18px; padding:4px 8px; }
  .msg { font-size:13px; min-height:18px; }
  .msg.ok { color:#3fb950; } .msg.err { color:#f85149; }
  .previews { display:flex; gap:16px; flex-wrap:wrap; margin-top:8px; }
  .previews figure { margin:0; flex:1 1 340px; }
  .previews figcaption { font-size:12px; color:#8a909a; margin-bottom:6px; }
  .panel { background:#fff; border-radius:4px; padding:5px; min-height:60px; }
  .panel img { display:block; width:100%; height:auto; image-rendering:pixelated; }
  .hidden { display:none; }
  small { color:#7d8590; }
</style></head>
<body>
  <h1>SubwayBoard <span>editor</span></h1>

  <div class="card" id="loginCard">
    <div class="lab">Display ID <small>(on your board's screen, e.g. SB-4F2A)</small></div>
    <input id="displayId" placeholder="SB-XXXX" autocomplete="off">
    <div class="lab" style="margin-top:10px">PIN <small>(on your board's screen)</small></div>
    <input id="pin" placeholder="6 digits" autocomplete="off" inputmode="numeric">
    <div class="row" style="margin-top:14px">
      <button class="primary" id="loginBtn">Sign in</button>
      <span class="msg" id="loginMsg"></span>
    </div>
  </div>

  <div class="card hidden" id="editCard">
    <div class="row" style="justify-content:space-between">
      <div>Editing <b id="who"></b> <small id="rev"></small></div>
      <button class="link" id="logoutBtn">Sign out</button>
    </div>

    <div class="sec">
      <div class="lab">Board name</div>
      <input id="name" placeholder="My Board">
    </div>

    <div class="sec">
      <div class="lab">Weather location</div>
      <div class="ac"><input id="addr" placeholder="Search an address or place…" autocomplete="off">
        <div class="ac-list hidden" id="addrList"></div></div>
      <div class="pick" id="addrPick"></div>
    </div>

    <div class="sec">
      <div class="lab">Home station <small>(where the board reads train times)</small></div>
      <div class="ac"><input id="home" placeholder="Search a subway station…" autocomplete="off">
        <div class="ac-list hidden" id="homeList"></div></div>
      <div class="pick" id="homePick"></div>
    </div>

    <div class="sec">
      <div class="lab">Trains <small>(pick a line and where it's heading)</small></div>
      <div id="trains"></div>
      <button class="link" id="addTrain">+ Add train</button>
    </div>

    <div class="sec">
      <div class="lab">Citi Bike station <small>(e-bike count; optional)</small></div>
      <div class="ac"><input id="cb" placeholder="Search a Citi Bike station…" autocomplete="off">
        <div class="ac-list hidden" id="cbList"></div></div>
      <div class="row"><div class="pick" id="cbPick" style="flex:1"></div>
        <button class="link" id="cbClear">clear</button></div>
    </div>

    <div class="sec">
      <div class="lab">Service alerts</div>
      <select id="alerts">
        <option value="5">Check every 5 minutes</option>
        <option value="10">Check every 10 minutes</option>
        <option value="15">Check every 15 minutes</option>
        <option value="30">Check every 30 minutes</option>
      </select>
    </div>

    <div class="sec">
      <div class="row">
        <button id="previewBtn">Preview</button>
        <button class="primary" id="saveBtn">Save</button>
        <span class="msg" id="editMsg"></span>
      </div>
      <div class="previews">
        <figure><figcaption>Now (on your board)</figcaption>
          <div class="panel"><img id="beforeImg" alt=""></div></figure>
        <figure><figcaption>After your change</figcaption>
          <div class="panel"><img id="afterImg" alt=""></div></figure>
      </div>
    </div>
  </div>

<script>
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("sb_token");
let deviceId = sessionStorage.getItem("sb_device");
let edit = null;
const LINES = ["1","2","3","4","5","6","7","A","C","E","B","D","F","M","N","Q","R","W","G","J","Z","L","S"];

function setMsg(el, text, ok) { el.textContent = text; el.className = "msg " + (ok ? "ok" : "err"); }
const debounce = (fn, ms=250) => { let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; };

// ---- login ----
async function login() {
  setMsg($("loginMsg"), "", true);
  const r = await fetch("/api/login", { method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ display_id: $("displayId").value.trim(), pin: $("pin").value.trim() }) });
  const j = await r.json();
  if (!r.ok) return setMsg($("loginMsg"), j.error || "sign in failed", false);
  token = j.token; deviceId = j.device_id;
  sessionStorage.setItem("sb_token", token); sessionStorage.setItem("sb_device", deviceId);
  await startEditor(j.display_id, j.name);
}
function logout() { token=deviceId=null; sessionStorage.clear();
  $("editCard").classList.add("hidden"); $("loginCard").classList.remove("hidden"); }

// ---- autocomplete helper ----
function autocomplete(input, list, endpoint, mapItem, onSelect) {
  const run = debounce(async () => {
    const q = input.value.trim();
    if (q.length < 2) { list.classList.add("hidden"); return; }
    let res = [];
    try { res = (await (await fetch(endpoint + encodeURIComponent(q))).json()).results || []; } catch {}
    list.innerHTML = "";
    res.forEach(item => {
      const d = document.createElement("div");
      d.textContent = mapItem(item);
      d.onclick = () => { onSelect(item); list.classList.add("hidden"); };
      list.appendChild(d);
    });
    list.classList.toggle("hidden", res.length === 0);
  });
  input.addEventListener("input", run);
  input.addEventListener("blur", () => setTimeout(() => list.classList.add("hidden"), 180));
}

// ---- editor ----
async function startEditor(displayName, name) {
  $("loginCard").classList.add("hidden"); $("editCard").classList.remove("hidden");
  $("who").textContent = name || displayName || deviceId;
  const r = await fetch("/api/devices/" + encodeURIComponent(deviceId) + "/edit",
    { headers: { "Authorization": "Bearer " + token } });
  edit = (await r.json()).edit;
  edit.columns = edit.columns || [];
  fillForm();
  renderBefore();
}

function fillForm() {
  $("name").value = edit.name || "";
  $("addrPick").textContent = edit.weather ? ("✓ " + (edit.weather.lat).toFixed(4) + ", " + (edit.weather.lon).toFixed(4)) : "";
  $("homePick").textContent = edit.home && edit.home.name ? ("✓ " + edit.home.name) : "";
  $("cbPick").textContent = edit.citibike && edit.citibike.name ? ("✓ " + edit.citibike.name)
                          : (edit.citibike && edit.citibike.station_id ? "✓ station set" : "");
  $("alerts").value = String((edit.cadence && edit.cadence.alerts_every_min) || 5);
  renderTrains();
}

function renderTrains() {
  const box = $("trains"); box.innerHTML = "";
  edit.columns.forEach((col, i) => {
    const row = document.createElement("div"); row.className = "trainrow";

    const sel = document.createElement("select"); sel.className = "line";
    LINES.forEach(l => { const o=document.createElement("option"); o.value=l; o.textContent=l;
      if (l===col.line) o.selected=true; sel.appendChild(o); });
    sel.onchange = () => { col.line = sel.value; };

    const wrap = document.createElement("div"); wrap.className = "dest ac";
    const inp = document.createElement("input");
    inp.placeholder = "heading to… (destination station)";
    inp.value = (col.dest && col.dest.name) || "";
    const lst = document.createElement("div"); lst.className = "ac-list hidden";
    wrap.appendChild(inp); wrap.appendChild(lst);
    autocomplete(inp, lst, "/api/catalog/stops?q=",
      s => s.name + " — " + (s.routes || "").trim(), s => {
      col.dest = { name: s.name, lat: s.lat, lon: s.lon };  // lat/lon drive direction
      inp.value = s.name;
    });

    const x = document.createElement("button"); x.className = "x"; x.textContent = "×";
    x.title = "remove"; x.onclick = () => { edit.columns.splice(i,1); renderTrains(); };

    row.appendChild(sel); row.appendChild(wrap); row.appendChild(x);
    box.appendChild(row);
  });
  $("addTrain").style.display = edit.columns.length >= 4 ? "none" : "";
}

function collect() {
  edit.name = $("name").value;
  edit.cadence = edit.cadence || {};
  edit.cadence.alerts_every_min = parseInt($("alerts").value, 10);
  return edit;
}

async function renderBefore() {
  const r = await fetch("/api/config?device=" + encodeURIComponent(deviceId));
  if (!r.ok) return;
  const cfg = await r.json();
  $("rev").textContent = "(rev " + cfg.config_rev + ")";
  preview($("beforeImg"), { config: cfg });
}
async function preview(imgEl, payload) {
  const r = await fetch("/api/preview", { method:"POST",
    headers:{ "Content-Type":"application/json", "Authorization":"Bearer "+token },
    body: JSON.stringify(payload) });
  if (!r.ok) { const j=await r.json().catch(()=>({})); setMsg($("editMsg"), "preview: "+(j.error||r.status), false); return; }
  imgEl.src = URL.createObjectURL(await r.blob());
}
async function doPreview() { setMsg($("editMsg"),"rendering…",true); await preview($("afterImg"), { edit: collect() }); setMsg($("editMsg"),"",true); }
async function save() {
  const r = await fetch("/api/devices/" + encodeURIComponent(deviceId) + "/config", {
    method:"POST", headers:{ "Content-Type":"application/json", "Authorization":"Bearer "+token },
    body: JSON.stringify(collect()) });
  const j = await r.json();
  if (!r.ok) return setMsg($("editMsg"), j.error || "save failed", false);
  setMsg($("editMsg"), "Saved — your board updates within ~5 min (rev " + j.config_rev + ")", true);
  renderBefore();
}

// wire static controls
autocomplete($("addr"), $("addrList"), "/api/geocode?q=", g => g.name, g => {
  edit.weather = { lat: g.lat, lon: g.lon, tz: g.tz || (edit.weather && edit.weather.tz) || "America/New_York" };
  $("addr").value = g.name; $("addrPick").textContent = "✓ " + g.name;
});
autocomplete($("home"), $("homeList"), "/api/catalog/stops?q=",
  s => s.name + " — " + (s.routes || "").trim(), async s => {
  // Pull every stop in the complex to map each line to its own stop id.
  const rows = (await (await fetch("/api/catalog/complex?id=" + encodeURIComponent(s.complex_id))).json()).results || [];
  const stops = {}; let stopId = null;
  rows.forEach(r => (r.routes || "").split(/\\s+/).forEach(l => {
    if (l) { stops[l] = r.stop_id; if (!stopId) stopId = r.stop_id; } }));
  edit.home = { complex_id: s.complex_id, name: s.name, lat: s.lat, lon: s.lon, stop_id: stopId, stops };
  $("home").value = ""; $("homePick").textContent = "✓ " + s.name + " (" + (s.routes || "").trim() + ")";
});
autocomplete($("cb"), $("cbList"), "/api/catalog/citibike?q=", s => s.name, s => {
  edit.citibike = { station_id: s.station_id, name: s.name };
  $("cb").value = ""; $("cbPick").textContent = "✓ " + s.name;
});
$("cbClear").onclick = () => { edit.citibike = { station_id: null }; $("cbPick").textContent = ""; };
$("addTrain").onclick = () => { if (edit.columns.length < 4) { edit.columns.push({ line:"6", dest:null }); renderTrains(); } };
$("loginBtn").onclick = login;
$("logoutBtn").onclick = logout;
$("previewBtn").onclick = doPreview;
$("saveBtn").onclick = save;
$("pin").addEventListener("keydown", e => { if (e.key === "Enter") login(); });

if (token && deviceId) startEditor();
</script>
</body></html>`;
