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
HELV = "/System/Library/Fonts/Helvetica.ttc"
SYM = "/System/Library/Fonts/Apple Symbols.ttf"

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
helv18 = HelvFont(HELV, 0, 18, _ASCII + DEG)
helv28b = HelvFont(HELV, 1, 28, _ASCII + DEG)
helv40b = HelvFont(HELV, 1, 40, "0123456789/" + DEG)

# Small unit face for the "min" label (~65% of the bold arrival number).
# Drop to helv15 for a ~50% look.
MIN_FONT = helv18

# Destination line: an auto-fit ladder (matches genfont.py's baked sizes). The
# largest that fits the column width + the vertical band is used, so short
# names (Woodlawn) render big and long ones (Brooklyn Bridge-City Hall) shrink.
STATION_SIZES = [11, 15, 19, 23]
STATION_FONTS = [HelvFont(HELV, 0, px, _ASCII + DEG) for px in STATION_SIZES]
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
_arrow_up = iconlib.draw_arrow(26)
ARROWS = {
    "N": DrawnIcon(_arrow_up),
    "E": DrawnIcon(_arrow_up.transpose(Image.ROTATE_270)),
    "S": DrawnIcon(_arrow_up.transpose(Image.ROTATE_180)),
    "W": DrawnIcon(_arrow_up.transpose(Image.ROTATE_90)),
}


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


def render(arrivals, alerts, weather_info, now, rotation, clock12,
           stop_names=None, ebikes=None, stop_coords=None):
    """Return an 'L' image (0/255) exactly as the panel would show it.

    arrivals: dict ROUTES-index -> RouteArrivals   (as gathered from the feeds)
    alerts:   dict route -> RouteAlert
    weather_info: WeatherInfo
    now:      unix epoch seconds
    rotation: refresh counter (cycles the ticker among no-service columns)
    clock12:  bottom-right string, e.g. "3:05 PM"
    stop_names: {stop_id: name} for turning a terminal id into a destination
    ebikes:   e-bikes available at the nearest Citi Bike station (None = hide)
    """
    if stop_names is None:
        stop_names = {}
    if stop_coords is None:
        stop_coords = {}
    img = Image.new("L", (SCREEN_W, SCREEN_H), WHITE)
    draw = ImageDraw.Draw(img)
    fb = img  # paste target

    _draw_weather(fb, COL_W // 2, weather_info, ebikes)

    blurbs = []          # ticker lines for columns that ended up empty
    station_labels = []  # (cx, text) drawn together at one uniform size

    for col, (label, fallback, route_idxs, dest_filter) in enumerate(cfg.COLUMNS):
        cx = (col + 1) * COL_W + COL_W // 2

        # Bullet (the route label).
        draw.ellipse([cx - BULLET_R, BULLET_CY - BULLET_R,
                      cx + BULLET_R, BULLET_CY + BULLET_R], fill=BLACK)
        helv28b.centered(fb, cx, BULLET_CY - helv28b.height // 2, label, WHITE)

        # Merge this column's routes into one sorted minutes list, remembering
        # each arrival's route and destination name (stable, ascending -- see
        # display.cpp's insertion). A non-empty dest_filter keeps only trains
        # bound for those destinations. Take the first ARRIVALS_SHOWN.
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

        # Sub-label = where the next train is going (fallback when none),
        # capped to 3 words. Collected now, drawn after the loop at one size.
        station = (merged[0][2] or fallback) if n else fallback
        station_labels.append((cx, _three_words(station)))

        # Direction arrow left of the bullet: which way the next train actually
        # heads, inferred from the terminal's coordinates vs this stop.
        if n:
            d = stops.direction4(cfg.ROUTES[route_idxs[0]][1], merged[0][3], stop_coords)
            arrow = ARROWS.get(d)
            if arrow:
                arrow.draw(fb, cx - BULLET_R - 6 - arrow.w,
                           BULLET_CY - arrow.h // 2, BLACK)

        if n == 0:
            # dash + "no service"
            draw.rectangle([cx - 16, BIG_Y + 18, cx + 16, BIG_Y + 22], fill=BLACK)
            helv18.centered(fb, cx, ROW_Y[0] + 4, "no service", BLACK)

            blurb = None
            for ri in route_idxs:
                route = cfg.ROUTES[ri][0]
                a = alerts.get(route)
                if a and a.text:
                    blurb = a.text
                    break
            if not blurb:
                blurb = "No [%s] trains scheduled right now" % label
            if blurb not in blurbs:
                blurbs.append(blurb)
            continue

        # Next train large; following trains as plain numbers. Two-route
        # columns tag every time with its route: "5 (B)".
        # Each arrival: the minutes in a large font, then a smaller "min"
        # (and route tag on merged columns) baseline-aligned beside it, the
        # pair centered in the column. MIN_FONT is the small unit face.
        tag = len(route_idxs) > 1

        def draw_arrival(mins_val, who, y, num_font, gap):
            nums = "%d" % mins_val
            suf = "min (%s)" % who if tag else "min"
            wn, ws = num_font.text_w(nums), MIN_FONT.text_w(suf)
            xx = cx - (wn + gap + ws) // 2
            num_font.draw(fb, xx, y, nums, BLACK)
            MIN_FONT.draw(fb, xx + wn + gap,
                          y + (num_font.height - MIN_FONT.height), suf, BLACK)

        m0, who0, _, _ = merged[0]
        draw_arrival(m0, who0, BIG_Y, helv40b, 6)      # next train, big
        for i in range(1, n):
            mi, whoi, _, _ = merged[i]
            draw_arrival(mi, whoi, ROW_Y[i - 1], helv28b, 4)

    # Destination labels: one uniform size across all columns (the largest that
    # fits every label), so they read as a set. Truncate any that still overflow.
    sfont = _uniform_station_font([t for _, t in station_labels], COL_W - 8)
    sy = STATION_TOP + ((STATION_BOT - STATION_TOP) - sfont.height) // 2
    for scx, stext in station_labels:
        while stext and sfont.text_w(stext) > COL_W - 8:
            stext = stext[:-1]
        sfont.centered(fb, scx, sy, stext, BLACK)

    # Column separators + bottom rule.
    for c in range(1, NUM_COLS):
        draw.line([c * COL_W, 10, c * COL_W, RULE_Y - 8], fill=BLACK, width=1)
    draw.line([0, RULE_Y, SCREEN_W - 1, RULE_Y], fill=BLACK, width=1)

    # Bottom line: alert ticker on the left, clock on the right.
    clock_w = helv18.text_w(clock12) if clock12 else 0
    if clock12:
        helv18.draw(fb, SCREEN_W - clock_w - 8, BOTTOM_Y, clock12, BLACK)

    if blurbs:
        line = blurbs[rotation % len(blurbs)]
        if len(blurbs) > 1:
            line += " (%d/%d)" % (rotation % len(blurbs) + 1, len(blurbs))
        max_w = SCREEN_W - clock_w - 32
        while line and helv18.text_w(line) > max_w:
            line = line[:-1]
        helv18.draw(fb, 8, BOTTOM_Y, line, BLACK)

    return img
