"""Hand-drawn 1-bit icons that aren't in Apple Symbols (wind).

Shared by the emulator (emulator/render.py draws them live) and the firmware
font generator (genfont.py bakes them into helvfont.h), so the panel and the
emulator show the identical icon. Each function returns an 8-bit 'L' image,
ink = 255 on a 0 background, which callers threshold at 110 like the fonts.
"""

from PIL import Image, ImageDraw


def draw_wind(h):
    """Three stacked breeze lines, the top one curling -- reads as wind."""
    w = max(1, round(h * 1.55))
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    lw = max(2, round(h * 0.12))
    x0 = round(lw * 0.7)
    rows = [(round(h * 0.30), 0.60), (round(h * 0.52), 0.90), (round(h * 0.74), 0.72)]
    for y, frac in rows:
        d.line([(x0, y), (round(w * frac), y)], fill=255, width=lw)
    # curl the top and bottom lines up at their right ends (the "gust")
    for y, frac in (rows[0], rows[2]):
        r = round(h * 0.17)
        cx = round(w * frac)
        box = [cx - r, y - 2 * r, cx + r, y]
        d.arc(box, -90, 90, fill=255, width=lw)   # small upward hook
    return img


def draw_arrow(h):
    """A bold arrow pointing up (rotate 90/180/270 for E/S/W)."""
    w = round(h * 0.74)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    d.polygon([(w / 2, 0), (0, h * 0.52), (w - 1, h * 0.52)], fill=255)  # head
    sw = round(w * 0.34)
    d.rectangle([(w - sw) // 2, round(h * 0.40), (w + sw) // 2, h - 1], fill=255)  # shaft
    return img


def draw_ebike(h):
    """Side-view bicycle with a lightning bolt beside it (Citi Bike e-bike)."""
    w = round(h * 2.0)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    lw = max(2, round(h * 0.10))

    r = round(h * 0.25)                 # wheel radius
    yc = h - r - 1                      # wheel-center line
    xL = r + 1                          # rear hub
    xR = round(h * 1.45) - r            # front hub (bike ~1.45h wide)
    d.ellipse([xL - r, yc - r, xL + r, yc + r], outline=255, width=lw)
    d.ellipse([xR - r, yc - r, xR + r, yc + r], outline=255, width=lw)

    bb = (round((xL + xR) * 0.52), yc)             # bottom bracket / pedals
    seat = (round((xL + xR) * 0.42), round(h * 0.30))
    head = (xR - round(h * 0.10), round(h * 0.36))  # handlebar/head tube
    frame = [(xL, yc, bb[0], bb[1]), (bb[0], bb[1], seat[0], seat[1]),
             (seat[0], seat[1], head[0], head[1]), (bb[0], bb[1], head[0], head[1]),
             (head[0], head[1], xR, yc)]
    for x0, y0, x1, y1 in frame:
        d.line([x0, y0, x1, y1], fill=255, width=lw)
    d.line([seat[0] - 3, seat[1], seat[0] + 3, seat[1]], fill=255, width=lw)   # saddle
    d.line([head[0] - 3, head[1], head[0] + 2, head[1]], fill=255, width=lw)   # bars

    # lightning bolt to the upper-right ("electric" badge)
    bx, bw2 = round(w * 0.80), round(w * 0.15)
    by, bh2 = 1, round(h * 0.62)
    bolt = [(bx + bw2 * 0.55, by), (bx, by + bh2 * 0.58),
            (bx + bw2 * 0.5, by + bh2 * 0.58), (bx + bw2 * 0.25, by + bh2),
            (bx + bw2, by + bh2 * 0.42), (bx + bw2 * 0.5, by + bh2 * 0.42)]
    d.polygon(bolt, fill=255)
    return img
