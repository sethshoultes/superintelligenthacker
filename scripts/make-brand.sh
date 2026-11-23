#!/usr/bin/env bash
# The brand files (superintelligenthacker#1): brand/mark.png from brand/mark.html (a typographic stand-in until the media
# pane's Hacker mark replaces it), every icon size the brand record names and favicon.ico from the mark, and the 1200x630
# share image from brand/share.html, each screenshot in headless Chrome so the type is the site's own Bangers.
# Needs ImageMagick (magick) and Google Chrome. Run: bash scripts/make-brand.sh
set -euo pipefail
cd "$(dirname "$0")/../brand"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
shot() { "$CHROME" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
  --window-size="$2" --screenshot="$PWD/$3" "file://$PWD/$1" 2>/dev/null; }
shot mark.html 512,512 mark.png
for n in 16 32 180 192 512; do
  magick mark.png -resize "${n}x${n}" "icon-$n.png"
done
magick mark.png -define icon:auto-resize=64,48,32,16 favicon.ico
shot share.html 1200,630 share.png
for f in mark.png icon-16.png icon-32.png icon-180.png icon-192.png icon-512.png favicon.ico share.png; do
  test -s "$f" || { echo "make-brand: $f is empty" >&2; exit 1; }
done
echo "make-brand: mark, icons, favicon.ico and share.png written"
