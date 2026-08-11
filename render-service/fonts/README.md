# Fonts for the render service

For **pixel-exact** parity with the panel, the render service should use the same
faces `genfont.py` bakes into the firmware: macOS **Helvetica** and **Apple
Symbols**. Copy them here from a Mac before building the Docker image:

```bash
cp "/System/Library/Fonts/Helvetica.ttc" render-service/fonts/
# rename to drop the space (Dockerfile ENV can't have spaces in values):
cp "/System/Library/Fonts/Apple Symbols.ttf" render-service/fonts/AppleSymbols.ttf
```

These files are **gitignored** (Apple font licensing + binary size) — they live
only in your local build. The `Dockerfile` points `FONT_*` at them.

## Running on Linux without the Mac fonts

If you can't bundle the Mac fonts, install close substitutes in the image and
override the env vars (preview will look ~right but not byte-identical):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
      fonts-liberation fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
ENV FONT_HELV=/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf \
    FONT_HELV_INDEX=0 \
    FONT_HELV_BOLD=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf \
    FONT_HELV_BOLD_INDEX=0 \
    FONT_SYM=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
```

(Liberation Sans matches Helvetica metrics; DejaVu Sans covers ☀/☂. Verify the
sun/umbrella glyphs render — swap in `fonts-symbola` if a symbol shows as tofu.)
