// Config schema, defaults, and resolution for the destination-based editor.
//
// The editor works in friendly terms: a home station + per-column (line +
// destination). We resolve that to the DEVICE-READY config the firmware/emulator
// consume:
//   routes:  [{ route, stop_id, feed }]           // stop_id carries the N/S suffix
//   columns: [{ label, fallback, route_idx[], dest_filter[] }]

export const FEEDS = ["IRT", "BDFM", "NQRW", "ACE"];

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

export const LIMITS = { MAX_ROUTES: 12, MAX_COLS: 4, MAX_MERGE: 2, MAX_FILTER: 2 };

// GTFS direction suffix (N/S) for a train at `home` heading toward a destination.
// The MTA labels every line N/S even when it runs E-W (the 7, L, ...), so we pick
// the dominant axis of the bearing and map East->N, West->S (which matches the
// MTA's crosstown convention, e.g. 7 to Hudson Yards = West = "S").
export function directionSuffix(homeLat, homeLon, destLat, destLon) {
  const dN = destLat - homeLat;
  const mid = ((homeLat + destLat) / 2) * Math.PI / 180;
  const dE = (destLon - homeLon) * Math.cos(mid);
  if (Math.abs(dN) >= Math.abs(dE)) return dN >= 0 ? "N" : "S";
  return dE >= 0 ? "N" : "S";
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
  if (!home.stop_id) throw new Error("pick your home station");
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
    const line = String(c.line || "").toUpperCase();
    if (!line) throw new Error("each train needs a line");
    const dest = c.dest || {};
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
    };
  });

  return {
    config_rev: prevRev + 1,
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
