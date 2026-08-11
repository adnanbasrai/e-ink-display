# Preview render service image.
#
# Build from the REPO ROOT (needs emulator/ and iconlib.py as well):
#   docker build -f render-service/Dockerfile -t subwayboard-render .
#
# For pixel-exact parity with the panel, place your Mac's Helvetica.ttc and
# "Apple Symbols.ttf" in render-service/fonts/ before building
# (see render-service/fonts/README.md). Without them, set the FONT_* env vars
# below to Linux fonts (Liberation + a symbol font) for a close-but-not-exact look.

FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir Pillow

COPY emulator/ /app/emulator/
COPY iconlib.py /app/iconlib.py
COPY render-service/ /app/render-service/

ENV RENDER_HOST=0.0.0.0 \
    PORT=8090 \
    FONT_HELV=/app/render-service/fonts/Helvetica.ttc \
    FONT_HELV_INDEX=0 \
    FONT_HELV_BOLD=/app/render-service/fonts/Helvetica.ttc \
    FONT_HELV_BOLD_INDEX=1 \
    FONT_SYM=/app/render-service/fonts/AppleSymbols.ttf

EXPOSE 8090
WORKDIR /app/render-service
CMD ["python", "server.py"]
