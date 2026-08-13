"""Pixel-faithful port of the firmware's display.cpp.

Renders the 792x272 board into a 1-bit (black-on-white) PIL image using the
exact same fonts the device uses: Apple's Helvetica (regular + bold) at 18/28/40
px and Apple Symbols for the weather glyphs -- the same faces genfont.py bakes
into helvfont.h. Layout constants, centering math, the column merge, and the
"no service" / ticker behaviour all match display.cpp line-for-line, so what you
see here is what the panel will draw.
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

import board_config as cfg
import stops
import weather as wx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import iconlib  # noqa: E402  (shared hand-drawn icons, repo root)

# ---- geometry (display.cpp) ----
SCREEN_W = 792
SCREEN_H = 272
NUM_COLS = len(cfg.COLUMNS) + 1          # + weather
COL_W = SCREEN_W // NUM_COLS             # 158

BULLET_CY = 40
BULLET_R = 31
STATION_Y = 76
BIG_Y = 102
ROW_Y = [150, 180, 210]
RULE_Y = 244
BOTTOM_Y = 250

BLACK = 0
WHITE = 255

DEG = "°"

# ---- font paths (same as genfont.py) ----
# Default to the macOS system fonts (so the emulator renders as-is on a Mac);
# override with env vars on Linux/Windows or in the render-service container.
# macOS ships regular + bold in one Helvetica.ttc (faces 0 and 1); other systems
# ship them as separate files, so bold has its own path + index (defaulting to
# the same .ttc face 1, i.e. current Mac behaviour).
HELV = os.environ.get("FONT_HELV", "/System/Library/Fonts/Helvetica.ttc")
HELV_IDX = int(os.environ.get("FONT_HELV_INDEX", "0"))
HELV_BOLD = os.environ.get("FONT_HELV_BOLD", HELV)
HELV_BOLD_IDX = int(os.environ.get("FONT_HELV_BOLD_INDEX", "1"))
SYM = os.environ.get("FONT_SYM", "/System/Library/Fonts/Apple Symbols.ttf")

_ASCII = "".join(chr(c) for c in range(32, 127))


class HelvFont:
    """Mirror of a genfont.py HelvFont: advance widths + 110-threshold glyphs."""

    def __init__(self, path, index, px, charset):
        self.font = ImageFont.truetype(path, px, index=index)
        asc, desc = self.font.getmetrics()
        self.height = asc + desc
        self.charset = set(charset)
        self._cache = {}

    def char_w(self, ch):
        if ch not in self.charset:
            return 0
        return max(1, round(self.font.getlength(ch)))

    def text_w(self, s):
        return sum(self.char_w(c) for c in s)

    def _glyph(self, ch):
        g = self._cache.get(ch)
        if g is None:
            adv = self.char_w(ch)
            if adv == 0:
                g = (0, None)
            else:
                img = Image.new("L", (adv + 8, self.height), 0)
                ImageDraw.Draw(img).text((0, 0), ch, font=self.font, fill=255)
                img = img.crop((0, 0, adv, self.height))
                mask = img.point(lambda v: 255 if v >= 110 else 0)
                g = (adv, mask)
            self._cache[ch] = g
        return g

    def draw(self, fb, x, y, s, color):
        for ch in s:
            adv, mask = self._glyph(ch)
            if mask is not None:
                fb.paste(color, (x, y), mask)
            x += adv
        return x

    def centered(self, fb, cx, y, s, color):
        self.draw(fb, cx - self.text_w(s) // 2, y, s, color)


class Symbol:
    """Mirror of a genfont.py SymBitmap (Apple Symbols glyph, 110-threshold)."""

    def __init__(self, ch, px):
        font = ImageFont.truetype(SYM, px)
        bbox = font.getbbox(ch)
        self.w, self.h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        img = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(img).text((-bbox[0], -bbox[1]), ch, font=font, fill=255)
        self.mask = img.point(lambda v: 255 if v >= 110 else 0)

    def draw(self, fb, x, y, color):
        fb.paste(color, (x, y), self.mask)


# Built once at import (matches genfont.py's fonts + three symbols).
helv18 = HelvFont(HELV, HELV_IDX, 18, _ASCII + DEG)
helv28b = HelvFont(HELV_BOLD, HELV_BOLD_IDX, 28, _ASCII + DEG)
helv40b = HelvFont(HELV_BOLD, HELV_BOLD_IDX, 40, "0123456789/" + DEG)

# Extra sizes used by the Hero Digit / Platform Cards layouts. Built on first
# use so the default layout doesn't pay for faces it never draws. (On the
# device these would need baking into helvfont.h via genfont.py; in Python we
# load the real TrueType face directly, so any size is free.)
_font_cache = {}


def _font(px, bold=False):
    key = (px, bold)
    f = _font_cache.get(key)
    if f is None:
        path = HELV_BOLD if bold else HELV
        idx = HELV_BOLD_IDX if bold else HELV_IDX
        f = HelvFont(path, idx, px, _ASCII + DEG)
        _font_cache[key] = f
    return f

# Small unit face for the "min" label (~65% of the bold arrival number).
# Drop to helv15 for a ~50% look.
MIN_FONT = helv18

# Destination line: an auto-fit ladder (matches genfont.py's baked sizes). The
# largest that fits the column width + the vertical band is used, so short
# names (Woodlawn) render big and long ones (Brooklyn Bridge-City Hall) shrink.
STATION_SIZES = [11, 15, 19, 23]
STATION_FONTS = [HelvFont(HELV, HELV_IDX, px, _ASCII + DEG) for px in STATION_SIZES]
STATION_MIN_PX = 15     # hard floor: never render the destination smaller
STATION_TOP = 72        # just below the bullet
STATION_BOT = 101       # just above the big digits (BIG_Y)


def _three_words(s):
    """Keep at most the first three (space-separated) words."""
    return " ".join(s.split()[:3])


def _station_max_size(text, max_w):
    """Index of the largest ladder font that fits text in width + band."""
    band = STATION_BOT - STATION_TOP
    idx = 0
    for i, f in enumerate(STATION_FONTS):     # ascending
        if f.height <= band and f.text_w(text) <= max_w:
            idx = i
    return idx


def _uniform_station_font(labels, max_w):
    """One size for every column: the largest that fits all labels, but never
    below STATION_MIN_PX. Labels still too wide at the floor are truncated at
    draw time, so the size can't drop further."""
    best = len(STATION_FONTS) - 1
    for text in labels:
        best = min(best, _station_max_size(text, max_w))
    floor = next((i for i, px in enumerate(STATION_SIZES) if px >= STATION_MIN_PX), 0)
    return STATION_FONTS[max(best, floor)]

class DrawnIcon:
    """A hand-drawn icon (from iconlib) with the same interface as Symbol."""

    def __init__(self, img):
        self.w, self.h = img.size
        self.mask = img.point(lambda v: 255 if v >= 110 else 0)

    def draw(self, fb, x, y, color):
        fb.paste(color, (x, y), self.mask)


# Weather-column icons (row height ~20px). Sun/bolt/umbrella from Apple Symbols;
# wind is hand-drawn (iconlib) since Apple Symbols has no monochrome wind glyph.
sym_sun = Symbol("☀", 30)        # UV
sym_rain = Symbol("☂", 30)       # rain likelihood
icon_wind = DrawnIcon(iconlib.draw_wind(20))
icon_ebike = DrawnIcon(iconlib.draw_ebike(22))   # bike + bolt (Citi Bike e-bike)

# Direction arrows (left of each bullet): one up arrow rotated to N/E/S/W.
def _arrow_set(px):
    up = iconlib.draw_arrow(px)
    return {
        "N": DrawnIcon(up),
        "E": DrawnIcon(up.transpose(Image.ROTATE_270)),
        "S": DrawnIcon(up.transpose(Image.ROTATE_180)),
        "W": DrawnIcon(up.transpose(Image.ROTATE_90)),
    }


ARROWS = _arrow_set(26)        # Refined: full-size, left of the bullet
ARROWS_SM = _arrow_set(15)     # Hero/Cards: small, in the column header


def minutes_until(t, now):
    """Minutes until epoch t; negative means already gone. (display.cpp)"""
    if t <= now:
        return 0 if t >= now - 45 else -1
    return (t - now) // 60


def _hour12(h):
    ampm = "AM" if h < 12 else "PM"
    return "%d%s" % (((h + 11) % 12) + 1, ampm)


def _icon_row(fb, cx, cy, icon, text, font, gap=5):
    """Icon + text, centered as a unit and vertically centered on cy."""
    tw = font.text_w(text)
    x0 = cx - (icon.w + gap + tw) // 2
    icon.draw(fb, x0, cy - icon.h // 2, BLACK)
    font.draw(fb, x0 + icon.w + gap, cy - font.height // 2, text, BLACK)


def _draw_weather(fb, cx, w, ebikes):
    if not w.valid:
        helv28b.centered(fb, cx, 30, "--", BLACK)
        return

    # Feels-like temperature, big.
    helv40b.centered(fb, cx, 16, "%d%s" % (w.feels, DEG), BLACK)

    # Info rows below it: wind gusts, rain (if likely), UV, e-bikes. Only the
    # rows that have data are shown, spread evenly in the space below the temp.
    rows = [(icon_wind, "%d mph" % w.gusts)]
    if w.rain_hour >= 0:
        rows.append((sym_rain, "%d%% %s" % (w.rain_prob, _hour12(w.rain_hour))))
    rows.append((sym_sun, "%d %s" % (w.uv, w.uv_level)))
    if ebikes is not None:
        rows.append((icon_ebike, "%d" % ebikes))

    top, bot = 66, RULE_Y - 12       # 66 .. 232
    for i, (icon, text) in enumerate(rows):
        cy = round(top + (bot - top) * (i + 0.5) / len(rows))
        _icon_row(fb, cx, cy, icon, text, helv18)


def _prepare_columns(arrivals, alerts, now, stop_names, stop_coords, cfg):
    """Shared per-column data prep, identical for every layout.

    Merges each column's routes into one minute-sorted arrival list (the same
    stable ordering display.cpp uses), resolves the live destination label and
    the true N/E/S/W travel direction, and collects ticker blurbs for columns
    that ended up with no service. Only the DRAWING differs between layouts --
    the data shown is always computed here, once.
    """
    cols, blurbs = [], []
    for label, fallback, route_idxs, dest_filter in cfg.COLUMNS:
        merged = []
        for ri in route_idxs:
            route = cfg.ROUTES[ri][0]
            ra = arrivals.get(ri)
            if not ra:
                continue
            for t, dest in zip(ra.times, ra.dests):
                m = minutes_until(t, now)
                if m < 0 or m > 99:
                    continue
                dname = stops.dest_name(dest, stop_names)
                if dest_filter and dname not in dest_filter:
                    continue
                merged.append((m, route, dname, dest))
        merged.sort(key=lambda mr: mr[0])   # stable
        merged = merged[:cfg.ARRIVALS_SHOWN]
        n = len(merged)

        station = (merged[0][2] or fallback) if n else fallback
        direction = None
        if n:
            direction = stops.direction4(
                cfg.ROUTES[route_idxs[0]][1], merged[0][3], stop_coords)

        if n == 0:
            blurb = None
            for ri in route_idxs:
                a = alerts.get(cfg.ROUTES[ri][0])
                if a and a.text:
                    blurb = a.text
                    break
            if not blurb:
                blurb = "No [%s] trains scheduled right now" % label
            if blurb not in blurbs:
                blurbs.append(blurb)

        cols.append({
            "label": label,
            "station": _three_words(station),
            "direction": direction,
            "arrivals": merged,
            "tag": len(route_idxs) > 1,   # merged column -> tag each time
        })
    return cols, blurbs


def _ticker_text(blurbs, rotation):
    """The alert line for the bottom bar: one blurb, cycled per refresh."""
    if not blurbs:
        return ""
    line = blurbs[rotation % len(blurbs)]
    if len(blurbs) > 1:
        line += " (%d/%d)" % (rotation % len(blurbs) + 1, len(blurbs))
    return line


def _fit(font, text, max_w):
    """Truncate text until it fits max_w at this size."""
    while text and font.text_w(text) > max_w:
        text = text[:-1]
    return text


# ---------------------------------------------------------------- layout: R

def _render_refined(fb, draw, cols, blurbs, weather_info, ebikes, rotation,
                    clock12, date_str, cfg):
    """Refined Signage -- the classic five-slice board, tightened: a drawn
    outer frame, semibold destinations, and a doubled footer rule."""
    num_cols = len(cfg.COLUMNS) + 1
    col_w = SCREEN_W // num_cols

    draw.rectangle([2, 2, SCREEN_W - 3, SCREEN_H - 3], outline=BLACK, width=3)
    _draw_weather(fb, col_w // 2, weather_info, ebikes)

    station_labels = []
    for i, c in enumerate(cols):
        cx = (i + 1) * col_w + col_w // 2

        draw.ellipse([cx - BULLET_R, BULLET_CY - BULLET_R,
                      cx + BULLET_R, BULLET_CY + BULLET_R], fill=BLACK)
        helv28b.centered(fb, cx, BULLET_CY - helv28b.height // 2, c["label"], WHITE)

        station_labels.append((cx, c["station"]))

        arrow = ARROWS.get(c["direction"])
        if arrow:
            arrow.draw(fb, cx - BULLET_R - 6 - arrow.w,
                       BULLET_CY - arrow.h // 2, BLACK)

        merged = c["arrivals"]
        if not merged:
            draw.rectangle([cx - 16, BIG_Y + 18, cx + 16, BIG_Y + 22], fill=BLACK)
            helv18.centered(fb, cx, ROW_Y[0] + 4, "no service", BLACK)
            continue

        def draw_arrival(mins_val, who, y, num_font, gap):
            nums = "%d" % mins_val
            suf = "min (%s)" % who if c["tag"] else "min"
            wn, ws = num_font.text_w(nums), MIN_FONT.text_w(suf)
            xx = cx - (wn + gap + ws) // 2
            num_font.draw(fb, xx, y, nums, BLACK)
            MIN_FONT.draw(fb, xx + wn + gap,
                          y + (num_font.height - MIN_FONT.height), suf, BLACK)

        draw_arrival(merged[0][0], merged[0][1], BIG_Y, helv40b, 6)
        for i2 in range(1, len(merged)):
            draw_arrival(merged[i2][0], merged[i2][1], ROW_Y[i2 - 1], helv28b, 4)

    # One uniform destination size across all columns, so they read as a set.
    sfont = _uniform_station_font([t for _, t in station_labels], col_w - 8)
    sy = STATION_TOP + ((STATION_BOT - STATION_TOP) - sfont.height) // 2
    for scx, stext in station_labels:
        sfont.centered(fb, scx, sy, _fit(sfont, stext, col_w - 8), BLACK)

    for c2 in range(1, num_cols):
        draw.line([c2 * col_w, 14, c2 * col_w, RULE_Y - 8], fill=BLACK, width=1)
    draw.line([12, RULE_Y, SCREEN_W - 13, RULE_Y], fill=BLACK, width=1)
    draw.line([12, RULE_Y + 3, SCREEN_W - 13, RULE_Y + 3], fill=BLACK, width=1)

    # Bottom bar: ticker left, date + clock right.
    right = ("%s  %s" % (date_str, clock12)) if date_str else clock12
    rw = helv18.text_w(right) if right else 0
    if right:
        helv18.draw(fb, SCREEN_W - rw - 14, BOTTOM_Y, right, BLACK)
    line = _ticker_text(blurbs, rotation)
    if line:
        helv18.draw(fb, 14, BOTTOM_Y, _fit(helv18, line, SCREEN_W - rw - 40), BLACK)


# ---------------------------------------------------------------- layout: H

def _render_hero(fb, draw, cols, blurbs, weather_info, ebikes, rotation,
                 clock12, date_str, cfg):
    """Hero Digit -- weather compressed to one strip, then one oversized
    minutes number per column, legible from across the room."""
    n_cols = max(1, len(cols))
    col_w = SCREEN_W // n_cols

    f_temp = _font(32, bold=True)
    f_small = _font(13, bold=True)
    f_clock = _font(19, bold=True)
    f_date = _font(12, bold=True)
    f_hero = _font(74, bold=True)
    f_unit = _font(13, bold=True)
    f_also = _font(15, bold=True)
    f_dest = _font(12, bold=True)
    f_tick = _font(14)

    # Weather strip across the top.
    if weather_info.valid:
        f_temp.draw(fb, 14, 6, "%d%s" % (weather_info.feels, DEG), BLACK)
        bits = ["%d MPH" % weather_info.gusts]
        if weather_info.rain_hour >= 0:
            bits.append("%d%% @ %s" % (weather_info.rain_prob,
                                       _hour12(weather_info.rain_hour)))
        bits.append("UV %d" % weather_info.uv)
        if ebikes is not None:
            bits.append("%d E-BIKES" % ebikes)
        x = 14 + f_temp.text_w("%d%s" % (weather_info.feels, DEG)) + 22
        for b in bits:
            f_small.draw(fb, x, 18, b, BLACK)
            x += f_small.text_w(b) + 20

    right = clock12 or ""
    rw = f_clock.text_w(right)
    f_clock.draw(fb, SCREEN_W - rw - 14, 14, right, BLACK)
    if date_str:
        dw = f_date.text_w(date_str)
        f_date.draw(fb, SCREEN_W - rw - dw - 24, 18, date_str, BLACK)

    draw.rectangle([0, 56, SCREEN_W - 1, 60], fill=BLACK)

    for i, c in enumerate(cols):
        x0 = i * col_w
        cx = x0 + col_w // 2

        # Header: arrow, bullet chip, destination -- laid out left to right so
        # the arrow never lands under the bullet.
        hy = 82
        r = 13
        arrow = ARROWS_SM.get(c["direction"])
        ax = x0 + 8
        aw = arrow.w if arrow else 0
        if arrow:
            arrow.draw(fb, ax, hy - arrow.h // 2, BLACK)
        bx = ax + aw + (7 if aw else 0) + r
        draw.ellipse([bx - r, hy - r, bx + r, hy + r], fill=BLACK)
        lab = _font(12 if len(c["label"]) > 2 else 14, bold=True)
        lab.centered(fb, bx, hy - lab.height // 2, c["label"], WHITE)
        dx = bx + r + 6
        f_dest.draw(fb, dx, hy - f_dest.height // 2,
                    _fit(f_dest, c["station"].upper(), x0 + col_w - dx - 8), BLACK)

        merged = c["arrivals"]
        if not merged:
            draw.rectangle([cx - 18, 150, cx + 18, 155], fill=BLACK)
            f_also.centered(fb, cx, 170, "no service", BLACK)
            continue

        # The hero: minutes to the next train.
        hero = "%d" % merged[0][0]
        f_hero.centered(fb, cx, 104, hero, BLACK)
        unit = "MIN (%s)" % merged[0][1] if c["tag"] else "MIN"
        f_unit.centered(fb, cx, 190, unit, BLACK)

        if len(merged) > 1:
            # NB: separator must stay inside the baked charset (ASCII + degree)
            # -- a middle dot would silently render as nothing.
            rest = ", ".join(
                ("%d (%s)" % (m, w)) if c["tag"] else ("%d" % m)
                for m, w, _, _ in merged[1:])
            f_also.centered(fb, cx, 210, _fit(f_also, "then " + rest, col_w - 10), BLACK)

    draw.line([0, 240, SCREEN_W - 1, 240], fill=BLACK, width=1)
    line = _ticker_text(blurbs, rotation)
    if line:
        f_tick.draw(fb, 14, 248, _fit(f_tick, line, SCREEN_W - 28), BLACK)


# ---------------------------------------------------------------- layout: P

def _render_cards(fb, draw, cols, blurbs, weather_info, ebikes, rotation,
                  clock12, date_str, cfg):
    """Platform Cards -- each line on its own bordered plate, with a header
    chip and left-aligned numbers; the footer is its own strip below."""
    n = len(cols) + 1                       # + weather card
    gap = 10
    margin = 14
    card_w = (SCREEN_W - margin * 2 - gap * (n - 1)) // n
    card_top, card_bot = 14, 222

    f_date = _font(13, bold=True)
    f_temp = _font(32, bold=True)
    f_row = _font(12, bold=True)
    f_hdr = _font(12, bold=True)
    f_big = _font(48, bold=True)
    f_unit = _font(12, bold=True)
    f_chip = _font(13, bold=True)
    f_foot = _font(13)

    def card(x):
        draw.rounded_rectangle([x, card_top, x + card_w, card_bot],
                               radius=6, outline=BLACK, width=2)

    # ---- weather card ----
    x = margin
    card(x)
    f_date.draw(fb, x + 10, card_top + 8, (date_str or "").upper(), BLACK)
    if weather_info.valid:
        f_temp.centered(fb, x + card_w // 2, card_top + 34,
                        "%d%s" % (weather_info.feels, DEG), BLACK)
        rows = [(icon_wind, "%d mph" % weather_info.gusts)]
        if weather_info.rain_hour >= 0:
            rows.append((sym_rain, "%d%% %s" % (weather_info.rain_prob,
                                                _hour12(weather_info.rain_hour))))
        rows.append((sym_sun, "%d %s" % (weather_info.uv, weather_info.uv_level)))
        if ebikes is not None:
            rows.append((icon_ebike, "%d" % ebikes))
        top, bot = card_top + 84, card_bot - 14
        for i, (icon, text) in enumerate(rows):
            cy = round(top + (bot - top) * (i + 0.5) / len(rows))
            icon.draw(fb, x + 12, cy - icon.h // 2, BLACK)
            f_row.draw(fb, x + 12 + icon.w + 8, cy - f_row.height // 2, text, BLACK)

    # ---- one card per train column ----
    for i, c in enumerate(cols):
        x = margin + (i + 1) * (card_w + gap)
        card(x)

        # Header row: bullet chip left, direction arrow pinned right.
        chip_w = 18 + f_chip.text_w(c["label"])
        draw.rounded_rectangle([x + 10, card_top + 8, x + 10 + chip_w, card_top + 28],
                               radius=3, fill=BLACK)
        f_chip.centered(fb, x + 10 + chip_w // 2,
                        card_top + 18 - f_chip.height // 2, c["label"], WHITE)
        arrow = ARROWS_SM.get(c["direction"])
        if arrow:
            arrow.draw(fb, x + card_w - 10 - arrow.w,
                       card_top + 18 - arrow.h // 2, BLACK)

        # Destination gets its own line at the card's full width -- squeezing it
        # beside the chip truncated names down to "WOODLAW".
        f_hdr.draw(fb, x + 10, card_top + 34,
                   _fit(f_hdr, c["station"].upper(), card_w - 20), BLACK)

        merged = c["arrivals"]
        if not merged:
            draw.rectangle([x + 12, card_top + 96, x + 44, card_top + 101], fill=BLACK)
            f_row.draw(fb, x + 12, card_top + 116, "no service", BLACK)
            continue

        # Hero number, left-aligned so it can run large.
        f_big.draw(fb, x + 12, card_top + 50, "%d" % merged[0][0], BLACK)
        unit = "MIN (%s)" % merged[0][1] if c["tag"] else "MIN"
        f_unit.draw(fb, x + 12, card_top + 112, unit, BLACK)

        # Following arrivals as outlined chips.
        cy = card_top + 134
        for m, who, _, _ in merged[1:]:
            txt = ("%d MIN (%s)" % (m, who)) if c["tag"] else ("%d MIN" % m)
            w = f_chip.text_w(txt) + 18
            w = min(w, card_w - 24)
            draw.rounded_rectangle([x + 12, cy, x + 12 + w, cy + 24],
                                   radius=4, outline=BLACK, width=1)
            f_chip.centered(fb, x + 12 + w // 2, cy + 12 - f_chip.height // 2,
                            _fit(f_chip, txt, w - 8), BLACK)
            cy += 30

    # ---- footer strip, below the cards (never overlapping them) ----
    fy0, fy1 = 232, 258
    draw.rounded_rectangle([margin, fy0, SCREEN_W - margin, fy1],
                           radius=4, outline=BLACK, width=1)
    right = clock12 or ""
    rw = f_foot.text_w(right)
    f_foot.draw(fb, SCREEN_W - margin - rw - 10, fy0 + 6, right, BLACK)
    line = _ticker_text(blurbs, rotation)
    if line:
        f_foot.draw(fb, margin + 10, fy0 + 6,
                    _fit(f_foot, line, SCREEN_W - margin * 2 - rw - 34), BLACK)


LAYOUTS = {"R": _render_refined, "H": _render_hero, "P": _render_cards}


def render(arrivals, alerts, weather_info, now, rotation, clock12,
           stop_names=None, ebikes=None, stop_coords=None, cfg=None,
           layout=None, date_str=None):
    """Return an 'L' image (0/255) of the board in the requested layout.

    arrivals: dict ROUTES-index -> RouteArrivals   (as gathered from the feeds)
    alerts:   dict route -> RouteAlert
    weather_info: WeatherInfo
    now:      unix epoch seconds
    rotation: refresh counter (cycles the ticker among no-service columns)
    clock12:  bottom-right string, e.g. "3:05 PM"
    stop_names: {stop_id: name} for turning a terminal id into a destination
    ebikes:   e-bikes available at the nearest Citi Bike station (None = hide)
    cfg:      config module/object supplying COLUMNS/ROUTES/ARRIVALS_SHOWN.
              Defaults to board_config so the emulator is unaffected; the render
              service passes a per-board config to draw any board's layout.
    layout:   "R" (Refined Signage), "H" (Hero Digit) or "P" (Platform Cards).
              Falls back to the config's LAYOUT, then "R".
    date_str: e.g. "Tue, Aug 12" -- drawn next to the clock.
    """
    if cfg is None:
        import board_config as cfg
    if stop_names is None:
        stop_names = {}
    if stop_coords is None:
        stop_coords = {}
    if layout is None:
        layout = getattr(cfg, "LAYOUT", "R")
    draw_fn = LAYOUTS.get(str(layout).upper(), _render_refined)

    img = Image.new("L", (SCREEN_W, SCREEN_H), WHITE)
    draw = ImageDraw.Draw(img)

    cols, blurbs = _prepare_columns(arrivals, alerts, now,
                                    stop_names, stop_coords, cfg)
    draw_fn(img, draw, cols, blurbs, weather_info, ebikes, rotation,
            clock12, date_str, cfg)
    return img
