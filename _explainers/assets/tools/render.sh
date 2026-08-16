#!/usr/bin/env bash
# Field Atlas — D4 export renderer.
#
# Rasterizes each src/*.svg to exports/*.png at 2x scale using headless
# Chrome (chosen because it was already present in this environment and
# renders CSS custom properties inside inline <style> blocks correctly,
# unlike rsvg-convert/ImageMagick's SVG delegate which do not reliably
# support them). Also copies the canonical desktop-light SVG into exports/
# as the distributable editable source.
#
# Before rendering, this script always syncs every managed SVG's generated
# <style id="field-atlas-shared"> block against the canonical
# ../field-atlas.css (tools/sync-svg-styles.py) — exports must never be
# produced from a stale token block. Sync failure aborts the render (set
# -e); there is no flag to skip it.
#
# Requires: google-chrome (or set CHROME_BIN to another Chromium binary),
# python3.
#
# Usage: ./render.sh   (run from this directory, or anywhere — paths below
# are resolved relative to this script's location)

set -euo pipefail

CHROME_BIN="${CHROME_BIN:-google-chrome}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$ASSETS_DIR/src"
EXPORTS_DIR="$ASSETS_DIR/exports"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "== syncing Field Atlas shared styles =="
python3 "$SCRIPT_DIR/sync-svg-styles.py"
echo

render() {
  local src_svg="$1" out_png="$2" width="$3" height="$4" scale="$5"
  local wrap="$TMP_DIR/$(basename "$out_png").html"
  {
    echo '<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;padding:0;}</style></head><body>'
    cat "$src_svg"
    echo '</body></html>'
  } > "$wrap"

  "$CHROME_BIN" \
    --headless=new --disable-gpu --no-sandbox \
    --screenshot="$out_png" \
    --window-size="${width},${height}" \
    --force-device-scale-factor="$scale" \
    --hide-scrollbars \
    "file://$wrap" >/dev/null 2>&1

  echo "wrote $out_png"
}

mkdir -p "$EXPORTS_DIR"

render "$SRC_DIR/d4-ranking-vs-visibility.svg"        "$EXPORTS_DIR/d4-ranking-vs-visibility.png"        1600 900 2
render "$SRC_DIR/d4-ranking-vs-visibility-dark.svg"    "$EXPORTS_DIR/d4-ranking-vs-visibility-dark.png"   1600 900 2
render "$SRC_DIR/d4-ranking-vs-visibility-mobile.svg"  "$EXPORTS_DIR/d4-ranking-vs-visibility-mobile.png"  400 948 2
render "$SRC_DIR/d4-ranking-vs-visibility-social.svg"  "$EXPORTS_DIR/d4-ranking-vs-visibility-social.png" 1200 675 2

cp "$SRC_DIR/d4-ranking-vs-visibility.svg" "$EXPORTS_DIR/d4-ranking-vs-visibility.svg"
echo "copied canonical SVG to $EXPORTS_DIR/d4-ranking-vs-visibility.svg"
