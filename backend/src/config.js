// Config schema, defaults, and resolution for the destination-based editor.
//
// The editor works in friendly terms: a home station + per-column (line +
// destination). We resolve that to the DEVICE-READY config the firmware/emulator
// consume:
//   routes:  [{ route, stop_id, feed }]           // stop_id carries the N/S suffix
//   columns: [{ label, fallback, route_idx[], dest_filter[] }]

export const FEEDS = ["IRT", "BDFM", "NQRW", "ACE", "LIRR", "MNR"];

const LINE_TO_FEED = {
  "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "S": 0, "GS": 0,
  "B": 1, "D": 1, "F": 1, "M": 1,
  "N": 2, "Q": 2, "R": 2, "W": 2,
  "A": 3, "C": 3, "E": 3, "H": 3, "FS": 3,
};

export const LINES = Object.keys(LINE_TO_FEED).filter((l) => l.length === 1 || /^[0-9]$/.test(l));

export function feedForLine(line) {
  const f = LINE_TO_FEED[String(line).toUpperCase()];
  if (f === undefined) throw new Error(`unknown line "${line}"`);
  return f;
}

// ---- Commuter rail -------------------------------------------------------
// LIRR and Metro-North ride the same pipeline as the subway, with three
// differences the rest of this file has to account for:
//   1. Their route ids collide with the subway's (LIRR "1" is the Babylon
//      Branch), so a route is only ever matched against its own feed.
//   2. Their stop ids collide too, so they're namespaced with an agency letter
//      ("M1" = Metro-North Grand Central). See emulator/stops.py.
//   3. Their stop ids carry no N/S direction suffix -- and Metro-North's feed
//      omits direction_id entirely -- so direction can't come from the stop.
//      Instead we record the compass direction of the chosen destination and
//      filter arrivals by it (`dir_filter`), which is the same geographic
//      inference the subway already uses for its arrows.
//
// `short` is what goes on the board's bar, so it's kept to ~10 characters and
// set in the MTA's own abbreviated style. `color` is the official route_color
// from each agency's static GTFS, used by the website (the panel is 1-bit).
export const AGENCIES = [
  { id: "", name: "Subway" },
  { id: "L", name: "LIRR" },
  { id: "M", name: "Metro-North" },
];

export const RAIL_BRANCHES = {
  L: [
    { route: "1", name: "Babylon Branch", short: "BABYLON", color: "00985F" },
    { route: "2", name: "Hempstead Branch", short: "HEMPSTEAD", color: "CE8E00" },
    { route: "3", name: "Oyster Bay Branch", short: "OYSTER BAY", color: "00AF3F" },
    { route: "4", name: "Ronkonkoma Branch", short: "RONKONKOMA", color: "A626AA" },
    { route: "5", name: "Montauk Branch", short: "MONTAUK", color: "00B2A9" },
    { route: "6", name: "Long Beach Branch", short: "LONG BEACH", color: "FF6319" },
    { route: "7", name: "Far Rockaway Branch", short: "FAR ROCK", color: "6E3219" },
    { route: "8", name: "West Hempstead Branch", short: "W HEMPSTD", color: "00A1DE" },
    { route: "9", name: "Port Washington Branch", short: "PORT WASH", color: "C60C30" },
    { route: "10", name: "Port Jefferson Branch", short: "PORT JEFF", color: "006EC7" },
    { route: "11", name: "Belmont Park", short: "BELMONT", color: "60269E" },
    { route: "12", name: "City Terminal Zone", short: "CITY ZONE", color: "4D5357" },
    { route: "13", name: "Greenport Service", short: "GREENPORT", color: "A626AA" },
  ],
  M: [
    { route: "1", name: "Hudson Line", short: "HUDSON", color: "009B3A" },
    { route: "2", name: "Harlem Line", short: "HARLEM", color: "0039A6" },
    { route: "3", name: "New Haven Line", short: "NEW HAVEN", color: "EE0034" },
    { route: "4", name: "New Canaan Branch", short: "NEW CANAAN", color: "EE0034" },
    { route: "5", name: "Danbury Branch", short: "DANBURY", color: "EE0034" },
    { route: "6", name: "Waterbury Branch", short: "WATERBURY", color: "EE0034" },
  ],
};

const RAIL_FEED = { L: 4, M: 5 };

export function isRailAgency(a) {
  return a === "L" || a === "M";
}

export function railBranch(agency, route) {
  const list = RAIL_BRANCHES[agency] || [];
  return list.find((b) => b.route === String(route)) || null;
}

export const LIMITS = { MAX_ROUTES: 12, MAX_COLS: 4, MAX_MERGE: 2, MAX_FILTER: 2 };

// Board styles the renderer can draw. Keep these keys in sync with
// emulator/render.py's LAYOUTS dict.
export const LAYOUTS = [
  { id: "R", name: "Refined Signage", blurb: "Classic five-column board, framed and tightened" },
  { id: "H", name: "Hero Digit", blurb: "One huge number per line, readable across a room" },
  { id: "P", name: "Platform Cards", blurb: "Each line on its own bordered card" },
];
const LAYOUT_IDS = LAYOUTS.map((l) => l.id);

// GTFS direction suffix (N/S) for a train at `home` heading toward a destination.
// The MTA labels every line N/S even when it runs E-W (the 7, L, ...), so we pick
// the dominant axis of the bearing and map East->N, West->S (which matches the
// MTA's crosstown convention, e.g. 7 to Hudson Yards = West = "S").
export function directionSuffix(homeLat, homeLon, destLat, destLon) {
  const d = direction4(homeLat, homeLon, destLat, destLon);
  return d === "N" || d === "E" ? "N" : "S";
}

// True compass direction, snapped to the dominant axis. This is the same
// calculation the board uses to pick each column's arrow, and -- for commuter
// rail, whose stop ids have no direction in them -- to tell which way a train
// at a mid-line station is actually going.
export function direction4(fromLat, fromLon, toLat, toLon) {
  const dN = toLat - fromLat;
  const mid = ((fromLat + toLat) / 2) * Math.PI / 180;
  const dE = (toLon - fromLon) * Math.cos(mid);
  if (Math.abs(dN) >= Math.abs(dE)) return dN >= 0 ? "N" : "S";
  return dE >= 0 ? "E" : "W";
}

function firstWords(s, n) {
  return String(s || "").split(/\s+/).slice(0, n).join(" ");
}

// Friendly edit shape -> device-ready config.
// edit = {
//   name, weather:{lat,lon,tz}, citibike:{station_id,name?}, cadence:{...},
//   home: { stop_id, name, lat, lon },
//   columns: [ { line, dest: { stop_id, name, lat, lon } } ]   // 1..MAX_COLS
// }
export function resolveConfig(edit, prevRev = 0) {
  if (!edit || !Array.isArray(edit.columns)) throw new Error("columns required");
  if (edit.columns.length === 0) throw new Error("add at least one train");
  if (edit.columns.length > LIMITS.MAX_COLS)
    throw new Error(`at most ${LIMITS.MAX_COLS} trains`);
  const home = edit.home || {};
  // Rail columns bring their own origin station, so a board showing only
  // commuter rail needs no subway home at all.
  const anySubway = edit.columns.some((c) => !isRailAgency(String(c.agency || "").toUpperCase()));
  if (anySubway && !home.stop_id) throw new Error("pick your home station");
  const homeLat = Number(home.lat), homeLon = Number(home.lon);

  const routes = [];
  const keyToIdx = new Map();
  const routeIdx = (line, stopId, feed) => {
    const key = `${line}|${stopId}|${feed}`;
    if (keyToIdx.has(key)) return keyToIdx.get(key);
    if (routes.length >= LIMITS.MAX_ROUTES) throw new Error("too many distinct trains");
    const idx = routes.length;
    routes.push({ route: String(line).toUpperCase(), stop_id: stopId, feed });
    keyToIdx.set(key, idx);
    return idx;
  };

  const columns = edit.columns.map((c) => {
    const agency = String(c.agency || "").toUpperCase();
    const dest = c.dest || {};

    if (isRailAgency(agency)) {
      const branch = railBranch(agency, c.line);
      if (!branch) throw new Error(`unknown ${agency === "L" ? "LIRR" : "Metro-North"} branch`);
      // Rail columns carry their own origin: someone's Metro-North station is
      // rarely the subway stop outside their door.
      const origin = c.origin || {};
      if (!origin.stop_id) throw new Error(`pick a station for the ${branch.name}`);
      if (dest.lat === undefined || dest.lon === undefined)
        throw new Error(`pick a destination for the ${branch.name}`);
      const idx = routeIdx(branch.route, agency + origin.stop_id, RAIL_FEED[agency]);
      return {
        label: branch.short.slice(0, 12),
        fallback: firstWords(dest.name, 3).slice(0, 40),
        route_idx: [idx],
        dest_filter: [],
        // Rail stop ids carry no N/S, so this is the only thing separating
        // inbound from outbound at a station in the middle of a line.
        dir_filter: direction4(Number(origin.lat), Number(origin.lon),
                               Number(dest.lat), Number(dest.lon)),
      };
    }

    const line = String(c.line || "").toUpperCase();
    if (!line) throw new Error("each train needs a line");
    if (dest.lat === undefined || dest.lon === undefined)
      throw new Error(`pick a destination for the ${line} train`);
    // Each line sits at its own stop within the station complex (e.g. the 7 is at
    // 723, the 4/5/6 at 631). home.stops maps line -> base stop id.
    const base = (home.stops && home.stops[line]) || home.stop_id;
    if (!base) throw new Error(`the ${line} train doesn't stop at ${home.name || "your station"}`);
    const dir = directionSuffix(homeLat, homeLon, Number(dest.lat), Number(dest.lon));
    const feed = feedForLine(line);
    const idx = routeIdx(line, base + dir, feed);
    return {
      label: line.slice(0, 8),
      fallback: firstWords(dest.name, 3).slice(0, 40),
      route_idx: [idx],
      dest_filter: [],   // destination sets direction; we don't hard-filter (robust)
      dir_filter: "",    // the N/S stop suffix already picked the direction
    };
  });

  const layout = LAYOUT_IDS.includes(String(edit.layout || "").toUpperCase())
    ? String(edit.layout).toUpperCase() : "R";

  return {
    config_rev: prevRev + 1,
    layout,
    weather: {
      lat: Number(edit.weather?.lat), lon: Number(edit.weather?.lon),
      tz: edit.weather?.tz || "America/New_York",
    },
    citibike: { station_id: edit.citibike?.station_id || null },
    cadence: {
      alerts_every_min: Number(edit.cadence?.alerts_every_min ?? 5),
      weather_every_min: Number(edit.cadence?.weather_every_min ?? 30),
      citibike_every_min: Number(edit.cadence?.citibike_every_min ?? 2),
    },
    home: { stop_id: home.stop_id, name: home.name || "", complex_id: home.complex_id,
            stops: home.stops || null },
    routes, columns,
  };
}

// Default FRIENDLY config for a freshly-registered board (Grand Central).
export function makeDefaultEdit() {
  return {
    name: "My Board",
    layout: "R",
    weather: { lat: 40.7527, lon: -73.9772, tz: "America/New_York" },
    citibike: { station_id: "66dea8ff-0aca-11e7-82f6-3863bb44ef7c", name: "E 44 St & 2 Ave" },
    cadence: { alerts_every_min: 5, weather_every_min: 30, citibike_every_min: 2 },
    home: { stop_id: "631", complex_id: "610", name: "Grand Central-42 St",
            lat: 40.7527, lon: -73.9772,
            stops: { "4": "631", "5": "631", "6": "631", "7": "723", "S": "901" } },
    columns: [
      { line: "4", dest: { stop_id: "401", name: "Woodlawn", lat: 40.886037, lon: -73.878751 } },
      { line: "5", dest: { stop_id: "247", name: "Flatbush Av-Brooklyn College", lat: 40.632836, lon: -73.947642 } },
      { line: "6", dest: { stop_id: "640", name: "Brooklyn Bridge-City Hall", lat: 40.713065, lon: -74.004131 } },
      { line: "7", dest: { stop_id: "726", name: "34 St-Hudson Yards", lat: 40.755882, lon: -74.00191 } },
    ],
  };
}

export function makeDefaultConfig() {
  return resolveConfig(makeDefaultEdit(), 0);
}
