# PRINCIPLES.md — design principles for SubwayBoard

These govern design and build decisions for this project. They are **rank
ordered**: when two of them pull in opposite directions, the lower-numbered one
wins. The ordering is the operative part — the principles rarely conflict in
the abstract and constantly conflict in practice.

Read this before proposing a design, not after. If a decision trades one
principle against another, say so explicitly and name which one you let win.

---

## 1. Simplicity for the end customer

**Never move effort or technical work onto the end user.** If something is hard,
it is our job to absorb it — in the backend, in the firmware, in the setup flow.

In this project that means the owner never sees a terminal, a config file, an
API key, a firmware flash, or a JSON payload. Their entire experience is: plug
it in, join a hotspot from their phone, pick their network, and afterwards edit
the board on a website. Everything else is ours.

**Test:** could a friend's parent do this without phoning you? If a step needs
explaining, that is a bug in the product, not a gap in the user.

**Tripwires:**
- Any instruction to the user containing "then just…" — the word *just* is doing
  work that the software should be doing.
- Any feature whose setup requires knowing what a feed, a stop id, a route, or a
  rev number is.
- Anything that requires physical access to the device to fix, since that
  competes directly with principle 6.

**Precedent:** configuration moved out of `config.h` and onto the web portal so
that changing a station never means reflashing. WiFi is a captive portal rather
than a compiled-in credential. The editor speaks in "which line, heading where"
rather than stop ids and direction suffixes.

## 2. Privacy

**This device sits on someone's private home network.** Treat that position as
borrowed, not granted.

- Collect nothing that isn't needed to render the board or serve its config.
- No analytics, no usage tracking, no third-party scripts, fonts or beacons in
  the portal. (The editor deliberately inlines its own assets.)
- The device makes **outbound** requests only. It should listen on no port and
  accept no inbound connection — except the provisioning portal, which exists
  only until a network is saved and must shut down after.
- Never send the home network's contents anywhere: no SSID lists, no LAN
  addresses, no scan results, no neighbouring device names.
- Prefer key-free public data sources. They keep us from brokering credentials
  and from being a party to anyone's request logs.

**Test:** if a single row of our database leaked, would its owner mind? Design
so the honest answer is no.

## 3. Efficiency

**This runs on an ESP32 with hard limits.** Design against the real numbers:

| Budget | Current |
|---|---|
| Flash (huge_app) | ~38% of 3.1 MB |
| RAM | ~24% of 320 KB |
| Feed buffer | 1.5 MB, in PSRAM |
| Framebuffer | 27,200 B (792×272, 1-bit) |

Prefer fixed-size buffers over dynamic allocation; scanning and streaming over
parsing a whole document; and — most importantly — **doing the work on the
server whenever that saves the device from doing it.**

Also budget things that aren't memory: e-ink refresh time and panel wear, wake
cadence, request count per refresh, and NVS write frequency (flash wear).

**Test:** does this add a cost paid on *every* refresh, and does that cost grow
with the feature set? Per-refresh costs compound across hundreds of devices.

**Precedent:** the systemwide MTA bus feed is 1.9 MB — larger than the entire
feed buffer's comfortable working set and re-fetched every cycle. The right
design is for the backend to filter it to one stop and hand the device a few
hundred bytes. Note this is principle 1 and 3 agreeing: the server absorbs the
work, and both the user and the device are spared.

## 4. The one sanctioned privacy trade

**Privacy may be traded only to take burden off the user — never for our own
insight.** The motivating case: capturing a snapshot of a device's settings and
what it is currently rendering, so a problem can be triaged without asking the
owner to debug anything.

That is legitimate, because it converts "describe what your screen says and read
me the serial log" into "we already know." To keep it principled:

- **Minimum necessary** — settings and rendered state, not the network around it.
- **Tied to a support need**, not collected continuously by default.
- **Visible to the owner** — they should be able to see that it exists.
- **Time-bounded** — it should expire rather than accumulate.

**Not covered by this clause:** general analytics, engagement metrics, feature
usage, "product insight." Those help us, not the user, and principle 2 governs
them.

**Test:** does this remove work from the user *right now*? If the honest answer
is "no, but it would be useful to know," it fails.

## 5. Malleability

**We are in testing and feedback mode.** The feature set will keep changing, so
optimise for the cost of changing our minds.

- **A reflash is the most expensive change we can make.** It needs physical
  access, which collides with principle 1 and becomes untenable under principle
  6. Push changeable behaviour to where it can be changed remotely.
- Keep the device a **thin renderer** and let the backend resolver hold the
  semantics. The device should receive decisions, not make them.
- **Configs must be version-tolerant in both directions:** unknown fields
  ignored, absent fields defaulted. New firmware must cope with an old config
  and old firmware with a new one. This is already how `layout` and `dir_filter`
  behave — treat it as policy, not accident.
- Respect the **parity rule** (`CLAUDE.md`): display changes go into both the
  firmware and the emulator, identically. But note it doubles the cost of
  display work — which is another reason to keep changeable logic on the server
  side of that line.

**Test:** if we change our mind in two weeks, does it require a reflash? If yes,
look for a design where it doesn't.

## 6. Assume scale: hundreds of devices, homes *and* hotel rooms

Design for a fleet, not for one board on one wall.

**Hotel rooms break assumptions that homes don't:**
- There is no owner present. Nobody reads a PIN off the panel.
- Units are managed in bulk by staff, and are near-identical to each other.
- Guests are transient and must not be able to see or change anything.
- A failed unit is swapped, not debugged — a replacement must work without
  re-teaching anyone anything.

**Implications:**
- Provisioning must work in bulk, with fleet-wide templates and per-unit
  overrides.
- The backend must not assume one human per device. The current display-ID + PIN
  model assumes an owner reading the screen; that does not survive contact with
  a hotel.
- **Per-device running cost must stay ~$0.** Key-free feeds, scale-to-zero
  render, D1 — this architecture is right. Anything per-device metered, or any
  paid API key, is suspect at 300 units.
- Anything requiring manual per-device work does not scale. Count the human
  minutes per unit and multiply by 300.

**Test:** does this still work at 300 units with nobody touching them
individually?

---

## When principles collide

| Tension | Resolution |
|---|---|
| Simplicity (1) vs efficiency (3) | Move the work to the server. The user never pays; the device rarely should. |
| Privacy (2) vs telemetry (4) | Only if it removes user burden *now*. Curiosity is not a burden. |
| Efficiency (3) vs malleability (5) | While testing, favour changeability — but never ship a board that can't render. Efficiency is a constraint, not a goal to maximise. |
| Simplicity for homes (1) vs hotel needs (6) | Don't make the home owner absorb hotel complexity. Additive, not intrusive. |
| Malleability (5) vs parity rule | Parity is non-negotiable for what's drawn. Put logic that may change on the server, where parity doesn't apply. |

## Standing debts against these principles

An honest inventory, to be paid down rather than rediscovered:

- **A claimed board's PIN is unrecoverable** (violates 1, and becomes a support
  load under 6). `pin_plain` is nulled on claim, leaving only a one-way hash, so
  a user who loses their PIN cannot get back in without direct database access.
- **Firmware-level features still need a reflash** (1, 5) — e.g. adding a feed.
- **No bulk or fleet provisioning** (6). Every device is set up by hand today.
- **No D1 backup routine** (6). Device rows, configs and credentials live in one
  database with no export. Worth fixing before boards leave the building.
- **`secrets.h` holds a plaintext WiFi password** (2). It is a development
  shortcut only and must never be part of what ships.
- **No owner-visible record** of what we've captured about their device (2, 4) —
  required before principle 4 is exercised in earnest.
