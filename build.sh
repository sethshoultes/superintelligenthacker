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
# security.txt: the kit writes Contact from the record's one email (hello@) and no Policy line. Hacker's security contact is
# security@ and its policy is /what-it-checks (WORDS v3.1 section 7). Set here until the kit takes them (site-kit#528).
ST="$OUT/.well-known/security.txt"
grep -q "^Contact: mailto:hello@superintelligenthacker.com$" "$ST"
sed -i.bak "s#^Contact: .*#Contact: mailto:security@superintelligenthacker.com#" "$ST" && rm "${ST:?}.bak"
printf 'Policy: %s/what-it-checks/\n' "$ORIGIN" >>"$ST"
echo "built $(find "$OUT" -name index.html | wc -l | tr -d ' ') pages into $OUT for $ORIGIN"
