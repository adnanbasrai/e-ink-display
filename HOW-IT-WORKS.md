# How SubwayBoard Works — a plain-English guide

This guide explains what the emulator's code actually *does*, in everyday
language, without assuming you write software. If you can read a recipe, you can
follow this.

The emulator is the version of the board that runs on a computer (in the
`emulator/` folder). It's written in Python. It does exactly what the real e-ink
display does, just on your screen in a web browser instead of on the physical
panel — so we can use it to explain the whole system.

---

## The one-sentence version

> Every minute, the program phones a few free public websites to ask "when's the
> next train, what's the weather, and how many Citi Bikes are nearby?", then it
> draws that answer as a picture and shows it in your browser.

That's it. Everything below is just the detail of *how* it does those two
things: **get the data**, then **draw the picture**.

---

## The big picture

Think of the board as a tiny newspaper that reprints itself once a minute. Four
things have to happen for each edition:

```
   1. ASK          2. UNDERSTAND        3. DECIDE            4. DRAW
   the internet    the raw answer       what to show         the picture
   ───────────     ─────────────        ────────────         ──────────
   "next trains?"  turn the reply       pick the 3 soonest   place bullets,
   "weather?"      into plain numbers   trains per column,   numbers, icons
   "bikes?"        and station names    which way they go    onto a blank
                                                             792×272 canvas
```

Then it waits for the next minute and does it all again.

---

## Where each part of the code lives

The backend is split into small files, each with one job. Here's the whole cast,
in the order the data flows through them:

| File | Its job, in plain English |
|---|---|
| **`server.py`** | The **manager**. Runs the every-minute clock, hands out the finished picture to the browser, and handles the "Force refresh" button. This is what you start when you run the emulator. |
| **`board_config.py`** | The **settings sheet**. Which stations, which train lines, where the weather is, which Citi Bike dock. *This is the only file you'd edit to change what the board shows.* |
| **`board_data.py`** | The **fetcher**. Does the actual phoning-the-internet and remembers the last good answer so a hiccup doesn't blank the screen. |
| **`gtfs_rt.py`** | The **train-data translator**. The MTA sends train data in a dense computer format; this turns it into "the 6 train arrives in 4 minutes, headed to Brooklyn Bridge." |
| **`weather.py`** | The **weather translator**. Turns the raw forecast into: feels-like temp, wind, UV, and the chance of rain + when. |
| **`citibike.py`** | The **bike counter**. Finds the dock nearest you and counts available e-bikes. |
| **`stops.py`** | The **place-name book**. Trains identify stations by code numbers (like "631"); this looks up the human name ("Grand Central") and the map location. |
| **`render.py`** | The **artist**. Takes all the finished numbers and paints the actual black-and-white picture. |
| **`iconlib.py`** | The **rubber stamps**. Hand-drawn little pictures (wind, e-bike, direction arrows) used by the artist. |

> **Why so many files?** Same reason a kitchen has separate stations — prep,
> grill, plating. Each file does one thing well, so a change to the weather logic
> can't accidentally break the train logic.

---

## Step 1 — Asking the internet (the data sources)

The board talks to three free services. **None of them need a password or API
key** — that's a deliberate design choice so the devices "just work."

- **The MTA** (New York's transit agency) — for live train arrival times and
  service alerts. This is the official public feed; it only lists trains that are
  *actually running right now*.
- **Open-Meteo** — a free weather service — for the forecast.
- **Citi Bike** — for how many e-bikes are docked nearby.

`board_data.py` is what places these calls. Two important, friendly behaviors:

1. **It keeps the last good answer.** If the Wi-Fi blips or the MTA is briefly
   down, the board doesn't go blank — it keeps showing the most recent good data
   and quietly notes "data 4 min old" in the corner.
2. **It's on a schedule.** Trains are checked **every minute** (they change
   fast). Weather is only re-checked **every 30 minutes**, and service alerts
   **every 5 minutes** — because those barely change, and there's no point
   nagging those servers.

---

## Step 2 — Understanding the answer (parsing)

The MTA's train data doesn't arrive as friendly sentences. It arrives as a
tightly-packed stream of bytes (a format called "protobuf") designed to be small
and fast, not readable. `gtfs_rt.py` is a **hand-written reader** that walks
through that stream and plucks out only the four things we care about:

- which **train line** it is (4, 5, 6, 7…),
- which **station** it's stopping at,
- **when** it arrives, and
- its **final stop** (so we can say where it's headed).

> **A neat trick worth knowing:** the MTA feed only ever says a train is going
> "North" or "South" — it never says East or West. But the 7 train to Hudson
> Yards actually runs *west*. So the code figures out the true direction itself:
> it looks at the map coordinates of where the train is now versus where it's
> ending up, and works out the real compass direction (N/E/S/W). That's why the
> board can correctly show a **← West** arrow for the 7. (This lives in
> `stops.py`, in the part called `direction4`.)

`weather.py` and `citibike.py` do the same kind of translating for their data,
just from a simpler format (JSON, which is closer to plain text).

---

## Step 3 — Deciding what to show (the display logic)

This is the interesting judgment part, and it happens inside `render.py` as it
prepares each column. For every train column on the board:

1. **Gather all upcoming trains** for that column. Some columns combine two
   lines — the "4/5" column pulls in both the 4 and the 5 — so their arrivals get
   merged into one list.
2. **Sort by soonest** and **keep only the first three.** The nearest one is
   printed big; the next two are smaller rows beneath it.
3. **Filter out the ones you don't want.** For example, the uptown 4 column is set
   to only show trains going all the way to Woodlawn, and ignore the short-turn
   trains that stop early at 149th Street. (These rules are the last column in the
   settings sheet, `board_config.py`.)
4. **Label where it's going.** The destination under each bullet (e.g.
   "Woodlawn") is *not* typed in by hand — it's read live from the next train's
   final stop. If service changes and trains start terminating somewhere else, the
   label follows automatically.
5. **If no trains are coming,** the column shows a dash and "no service," and the
   scrolling line at the bottom explains why — usually by showing the MTA's own
   official alert text (e.g. weekend construction).

The weather column follows its own little rule: it always shows the feels-like
temperature big, then fills the space below with only the rows that have
something to say — wind, rain (*only* if rain is actually likely), UV, and the
bike count.

---

## Step 4 — Drawing the picture (rendering)

`render.py` starts with a **blank white canvas exactly 792×272 dots** — the exact
size of the real e-ink screen — and stamps everything onto it in black:

- the round **train bullets** (like the ones in a real subway map),
- the big **arrival numbers** and their little "min" labels,
- the **weather icons and readings**,
- the **direction arrows**, and
- the thin **dividing lines** between columns.

A few deliberate craftsmanship details:

- **The fonts are the Mac's real Helvetica**, so the board looks like proper
  transit signage rather than generic computer text.
- **Some icons don't exist as normal symbols** — there's no plain black wind or
  bicycle character in any font — so those are **hand-drawn dot-by-dot** in
  `iconlib.py`. The single up-arrow is simply rotated to point N/E/S/W.
- **Destination names auto-size.** All the little station labels are drawn at one
  shared size — the biggest size that lets the *longest* name still fit — so they
  look like a tidy set rather than a jumble. Anything still too long is trimmed.

The finished canvas is saved as a PNG image and handed back to `server.py`.

---

## How the browser shows it (`server.py`)

`server.py` is a tiny built-in web server. When you open
`http://127.0.0.1:8080`, here's the loop:

1. In the background, the manager runs the every-minute cycle described above and
   keeps the **latest finished picture** ready.
2. Your browser page quietly checks in every few seconds and asks "is there a
   newer edition?" When there is, it swaps in the new picture with a brief grey
   **flash** — mimicking the way real e-ink screens flicker when they refresh.
3. The **"Force refresh"** button just tells the manager "don't wait for the
   minute — fetch and redraw right now."

The timing is intentionally synced to the wall clock: it starts fetching about
20 seconds before each minute and holds the new picture until the minute actually
ticks over, so the numbers flip cleanly on the :00 — exactly like the real
panel.

---

## The one rule that ties it all together

There are **two** copies of this whole system: the Python emulator you just read
about, and the C++ "firmware" that runs on the physical e-ink device (the files
in the main folder, like `board_main.cpp` and `display.cpp`).

**They are kept deliberately identical.** The golden rule of this project is:
*every change is made in both, and they must draw the exact same picture, dot for
dot.* The emulator exists so you can see and perfect a change on your computer in
seconds, instead of re-flashing a physical device every time. If the emulator
looks right, the real board will too.

---

## If you only remember three things

1. **`board_config.py` is the settings sheet** — stations, lines, weather
   location, bike dock. It's the one file to touch to change what a board shows.
2. **Data flows one way:** ask the internet → translate the answer → decide what
   matters → draw it. Each file owns one of those steps.
3. **The emulator is a faithful twin of the real device** — what you see in the
   browser is what the e-ink panel will display.
