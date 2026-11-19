#!/usr/bin/env bash
# Build superintelligenthacker.com into dist/ from the record (sethshoultes/superintelligenthacker#1): site-kit's
# site-templates build, then the headers file Cloudflare Pages reads. Usage: ./build.sh [origin]   (default https://superintelligenthacker.com)
set -euo pipefail
cd "$(dirname "$0")"
ORIGIN="${1:-https://superintelligenthacker.com}"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ in the vendored skills, which site_sync verify would refuse
OUT="dist"
if [ -d "${OUT:?}" ]; then rm -rf "${OUT:?}"; fi
python3 skills/site-templates/build.py .sitekit/layout.json .sitekit/brand.json --origin "$ORIGIN" --out "$OUT" --publish
cp static/_headers "$OUT/_headers"   # HSTS and the CSP (public-site standard 13)
echo "built $(find "$OUT" -name index.html | wc -l | tr -d ' ') pages into $OUT for $ORIGIN"
