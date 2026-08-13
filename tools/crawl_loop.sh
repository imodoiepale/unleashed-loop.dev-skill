#!/usr/bin/env bash
# Snapshot the Loop developer portal documentation.
#
# Run this on a machine that can reach sandbox.loop.co.ke, then feed the result to
# tools/ingest_docs.py --input-dir to produce the skill's reference layer.
#
#   ./tools/crawl_loop.sh
#   python tools/ingest_docs.py --input-dir .cache/loop-docs/pages
#
# Design notes:
#   * The crawl is confined to the /devportal/docs/loop-api namespace. Without that
#     fence wget wanders into the portal's login flow and the rest of the sandbox.
#   * Routes are harvested from JS bundles as well as HTML, because docs portals
#     frequently define their navigation in JavaScript where no <a href> exists.
#   * An OpenAPI spec, if there is one, is worth more than the whole HTML mirror,
#     so we look for that first.
#   * robots.txt is respected. If it blocks the docs, the script says so rather
#     than quietly disabling the check — that decision is yours to make explicitly.

set -uo pipefail

# Defaults target Loop's sandbox portal. Override to snapshot any other docs site:
#   BASE=https://docs.example.com DOCS_PATH=/api START_PAGE=/api/intro ./tools/crawl_loop.sh
BASE="${BASE:-https://sandbox.loop.co.ke}"
DOCS_PATH="${DOCS_PATH:-/devportal/docs/loop-api}"
START="${BASE}${START_PAGE:-${DOCS_PATH}/introduction}"
OUT="${1:-.cache/loop-docs}"

# wget's --accept-regex needs the host escaped, and the host is now user-supplied.
HOST="${BASE#*://}"; HOST="${HOST%%/*}"
HOST_RE=$(printf '%s' "$HOST" | sed 's/\./\\./g')
UA="unleashed-loop.dev-skill/0.1 (docs snapshot; +https://github.com/imodoiepale/unleashed-loop.dev-skill)"

mkdir -p "$OUT"/{mirror,pages,assets,spec}

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m!!  %s\033[0m\n' "$*" >&2; }

# Is this file an unrendered SPA shell rather than a real page?
#
# Word count alone is not enough. A legitimate "documentation coming soon" stub is
# genuinely short, and failing it as a shell would wrongly push you to the headless
# crawler. The distinguishing feature of a real shell is *structural*: the server
# sent a mount point and nothing else — no prose elements at all. So we require
# both thin text and an absence of paragraph/heading/list content.
is_shell() {
  local f="$1"
  local words
  words=$(sed 's/<[^>]*>/ /g' "$f" | wc -w | tr -d ' ')
  [ "$words" -ge 60 ] && return 1
  grep -qiE '<(p|h1|h2|h3|li|td|pre)[ >]' "$f" && return 1
  return 0
}

# ---------------------------------------------------------------- preflight
say "[0/6] Preflight"

if ! command -v wget >/dev/null 2>&1; then
  warn "wget not found. Install it (brew install wget / apt install wget)."
  exit 1
fi

code=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$START" || echo 000)
echo "    start URL returned HTTP $code"
if [ "$code" = "000" ]; then
  warn "Cannot reach $START at all — check your network, VPN, or DNS."
  exit 1
fi
if [ "$code" != "200" ]; then
  warn "Start URL did not return 200. The docs may require a login, or the path moved."
fi

# Match robots.txt against the top segment of the docs path (/devportal for Loop),
# since that is the granularity most sites write their rules at.
TOP_SEGMENT="/$(printf '%s' "${DOCS_PATH#/}" | cut -d/ -f1)"
curl -s -A "$UA" "$BASE/robots.txt" -o "$OUT/robots.txt" 2>/dev/null
if [ -s "$OUT/robots.txt" ] && grep -qi "^Disallow: *${TOP_SEGMENT}" "$OUT/robots.txt"; then
  warn "robots.txt disallows ${TOP_SEGMENT}. Not crawling."
  warn "These docs are published publicly, so this is most likely a blanket rule —"
  warn "but the call to proceed anyway is yours. Review $OUT/robots.txt, and if you"
  warn "decide to continue, re-run with: CRAWL_IGNORE_ROBOTS=1 $0"
  [ "${CRAWL_IGNORE_ROBOTS:-0}" = "1" ] || exit 2
fi
ROBOTS_FLAG=()
[ "${CRAWL_IGNORE_ROBOTS:-0}" = "1" ] && ROBOTS_FLAG=(-e robots=off)

# Is the portal server-rendered or a JavaScript app? This decides everything
# downstream: wget cannot execute JavaScript, so on an SPA it returns an empty
# shell and the crawl "succeeds" while capturing nothing.
curl -s -A "$UA" "$START" -o "$OUT/_probe.html"
words=$(sed 's/<[^>]*>/ /g' "$OUT/_probe.html" | wc -w | tr -d ' ')
echo "    start page contains ~$words words of text outside markup"
SPA=0
if is_shell "$OUT/_probe.html"; then
  SPA=1
  warn "This looks client-rendered — the server returned a mount point with no prose."
  warn "wget will capture empty shells. Use the headless path instead (step 6 explains)."
fi

# ---------------------------------------------------------------- sitemap
say "[1/6] Sitemap"
for candidate in "$BASE/sitemap.xml" "$BASE/devportal/sitemap.xml" "$BASE/sitemap_index.xml"; do
  if curl -sfA "$UA" "$candidate" -o "$OUT/sitemap.xml" && [ -s "$OUT/sitemap.xml" ]; then
    echo "    found $candidate"
    grep -oE '<loc>[^<]+</loc>' "$OUT/sitemap.xml" | sed 's/<\/*loc>//g' \
      | grep -F "$DOCS_PATH" | sort -u > "$OUT/routes-sitemap.txt"
    echo "    $(wc -l < "$OUT/routes-sitemap.txt") documentation URL(s) in sitemap"
    break
  fi
done
[ -f "$OUT/routes-sitemap.txt" ] || { : > "$OUT/routes-sitemap.txt"; echo "    no sitemap found"; }

# ---------------------------------------------------------------- mirror
say "[2/6] Mirroring $DOCS_PATH"
wget "${ROBOTS_FLAG[@]}" \
  --mirror --level=inf --adjust-extension --convert-links --page-requisites \
  --domains="$HOST" \
  --accept-regex="^https?://${HOST_RE}${DOCS_PATH}(/.*)?$" \
  --reject-regex='(logout|signout|login|signin)' \
  --wait=1 --random-wait --tries=3 --timeout=30 \
  --user-agent="$UA" \
  --directory-prefix="$OUT/mirror" \
  "$START" 2>&1 | grep -Ei 'saved|ERROR|failed' | tail -20

# Grab the app shell's JS/CSS separately — that's where SPA routes hide, and the
# namespace filter above deliberately excludes asset paths.
say "[3/6] Fetching app assets (for route discovery)"
wget "${ROBOTS_FLAG[@]}" \
  --page-requisites --adjust-extension --span-hosts \
  --domains="$HOST" \
  --tries=3 --timeout=30 --user-agent="$UA" \
  --directory-prefix="$OUT/assets" \
  "$START" 2>&1 | grep -Ei 'saved|ERROR' | tail -10

# ---------------------------------------------------------------- routes
say "[4/6] Harvesting routes from HTML + JS"
grep -rhoE "${DOCS_PATH}/[A-Za-z0-9._~/%+-]+" "$OUT/mirror" "$OUT/assets" 2>/dev/null \
  | sed 's/[?#].*$//; s#/$##; s/\.html$//' \
  | grep -vE '\.(js|css|png|jpg|jpeg|svg|woff2?|ico|map)$' \
  | sort -u > "$OUT/routes-crawled.txt"

# Sitemap entries are already absolute URLs; crawled routes are paths needing the
# host prefix. Merge both into one deduplicated list.
sed "s#^#${BASE}#" "$OUT/routes-crawled.txt" > "$OUT/_abs.txt"
cat "$OUT/routes-sitemap.txt" "$OUT/_abs.txt" 2>/dev/null \
  | grep -E '^https?://' | sort -u > "$OUT/all-urls.txt"
rm -f "$OUT/_abs.txt"
echo "    $(wc -l < "$OUT/all-urls.txt") unique documentation URL(s) discovered"

# ---------------------------------------------------------------- spec hunt
say "[5/6] Hunting for an OpenAPI / Swagger spec"
# A machine-readable spec is strictly better than scraped prose, so it is worth
# looking hard for one before settling for HTML.
grep -rhoE '"[^"]*(openapi|swagger|api-docs)[^"]*\.(json|ya?ml)"' "$OUT/assets" "$OUT/mirror" 2>/dev/null \
  | tr -d '"' | sort -u > "$OUT/spec/candidates.txt"
for guess in \
  "$BASE/devportal/api/openapi.json" \
  "$BASE/devportal/docs/loop-api/openapi.json" \
  "$BASE/devportal/v3/api-docs" \
  "$BASE/v3/api-docs" \
  "$BASE/swagger.json"; do
  echo "$guess" >> "$OUT/spec/candidates.txt"
done
found_spec=""
while read -r cand; do
  [ -z "$cand" ] && continue
  case "$cand" in http*) url="$cand" ;; /*) url="${BASE}${cand}" ;; *) continue ;; esac
  if curl -sfA "$UA" "$url" -o "$OUT/spec/spec.json" 2>/dev/null \
     && head -c 400 "$OUT/spec/spec.json" | grep -qE '"(openapi|swagger)"'; then
    found_spec="$url"; break
  fi
done < "$OUT/spec/candidates.txt"

if [ -n "$found_spec" ]; then
  echo "    FOUND: $found_spec"
else
  rm -f "$OUT/spec/spec.json"
  echo "    none found — will use the HTML snapshot"
fi

# ---------------------------------------------------------------- fetch all
say "[6/6] Fetching every discovered route"
if [ -s "$OUT/all-urls.txt" ]; then
  wget "${ROBOTS_FLAG[@]}" \
    --input-file="$OUT/all-urls.txt" --adjust-extension --timestamping \
    --wait=1 --random-wait --tries=3 --timeout=30 --user-agent="$UA" \
    --directory-prefix="$OUT/pages" 2>&1 | grep -Ei 'saved|ERROR' | tail -20
fi

# Report which captured pages are suspiciously empty — the signature of an SPA
# and the single most common way a crawl silently produces nothing of value.
thin=0; total=0
while IFS= read -r -d '' f; do
  total=$((total+1))
  is_shell "$f" && thin=$((thin+1))
done < <(find "$OUT/pages" "$OUT/mirror" -name '*.html' -print0 2>/dev/null)

say "Result"
echo "    HTML pages captured : $total"
echo "    nearly-empty pages  : $thin"
echo "    routes discovered   : $(wc -l < "$OUT/all-urls.txt")"
[ -n "$found_spec" ] && echo "    OpenAPI spec        : $OUT/spec/spec.json"
echo ""
sed "s#${BASE}${DOCS_PATH}/##" "$OUT/all-urls.txt" | sed 's/^/    - /'
echo ""

if [ -n "$found_spec" ]; then
  echo "Next:  python tools/ingest_docs.py --openapi $OUT/spec/spec.json"
  echo "       (then also run the --input-dir pass below for the prose)"
fi

if [ "$SPA" = "1" ] || { [ "$total" -gt 0 ] && [ "$thin" -gt $((total / 2)) ]; }; then
  warn "Most captured pages are empty — this portal renders client-side."
  warn "wget cannot help further. Use the headless-browser crawler instead:"
  echo ""
  echo "    pip install -r tools/requirements.txt && playwright install chromium"
  echo "    python tools/ingest_docs.py --render"
  echo ""
else
  echo "Next:  python tools/ingest_docs.py --input-dir $OUT/pages"
fi
