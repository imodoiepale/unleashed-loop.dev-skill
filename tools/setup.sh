#!/usr/bin/env bash
# One command to populate the skill: crawl Loop's docs, convert them, validate.
#
#   ./tools/setup.sh
#
# Run this on a machine that can reach sandbox.loop.co.ke. It picks the best
# available capture route automatically — an OpenAPI spec beats a wget mirror, and a
# wget mirror beats nothing — and if the portal turns out to render client-side it
# says so and switches to headless Chromium rather than writing an empty corpus and
# calling it a success.
#
# Re-run it any time to refresh the corpus; review the diff before committing, since
# a diff here is a change in Loop's API surface.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
CACHE=".cache/loop-docs"
REFS="skills/loop-api/references"

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m!!  %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mFATAL: %s\033[0m\n' "$*" >&2; exit 1; }

PY="${PYTHON:-python3}"

# ------------------------------------------------------------------ deps
bold "Checking prerequisites"

command -v "$PY" >/dev/null 2>&1 || die "python3 not found. Install Python 3.9+ and re-run."
echo "    python  : $("$PY" --version 2>&1)"

if ! command -v wget >/dev/null 2>&1; then
  warn "wget not found — will use the Python crawler instead of the wget mirror."
  warn "To install: apt install wget   |   brew install wget"
  HAVE_WGET=0
else
  HAVE_WGET=1
  echo "    wget    : $(wget --version | head -1 | cut -d' ' -f1-3)"
fi

if ! "$PY" -c "import bs4, markdownify" 2>/dev/null; then
  bold "Installing Python dependencies"
  "$PY" -m pip install -r tools/requirements.txt \
    || die "dependency install failed. Try: $PY -m pip install --user -r tools/requirements.txt"
fi
echo "    deps    : ok"

# ------------------------------------------------------------------ capture
if [ "$HAVE_WGET" = "1" ]; then
  bold "Capturing the documentation (wget)"
  bash tools/crawl_loop.sh "$CACHE"
  CRAWL_STATUS=$?
  if [ "$CRAWL_STATUS" = "2" ]; then
    die "crawl stopped on robots.txt — see the message above before proceeding."
  fi
fi

# ------------------------------------------------------------------ convert
bold "Converting to the reference corpus"

converted=0

# Best case: a machine-readable spec. Unambiguous about methods, required fields,
# and response shapes — everything scraped prose leaves you guessing about.
if [ -s "$CACHE/spec/spec.json" ]; then
  echo "    OpenAPI spec found — converting"
  "$PY" tools/ingest_docs.py --openapi "$CACHE/spec/spec.json" && converted=1
fi

# Then the wget mirror, if it captured anything substantive.
if [ -d "$CACHE/pages" ] || [ -d "$CACHE/mirror" ]; then
  for dir in "$CACHE/pages" "$CACHE/mirror"; do
    [ -d "$dir" ] || continue
    if find "$dir" -name '*.html' | head -1 | grep -q .; then
      echo "    converting mirror: $dir"
      if "$PY" tools/ingest_docs.py --input-dir "$dir"; then
        converted=1
        break
      fi
    fi
  done
fi

# Count what actually landed, ignoring scaffolding.
count_refs() {
  find "$REFS" -maxdepth 1 -name '*.md' ! -name 'INDEX.md' ! -name 'README.md' 2>/dev/null | wc -l | tr -d ' '
}

# Last resort: render the portal in a real browser. Needed whenever the docs are a
# JavaScript app, which wget fundamentally cannot read.
if [ "$converted" = "0" ] || [ "$(count_refs)" -lt 2 ]; then
  warn "The static capture produced little or nothing — the portal is probably a JavaScript app."
  bold "Retrying with headless Chromium"
  if ! "$PY" -c "import playwright" 2>/dev/null; then
    echo "    installing playwright..."
    "$PY" -m pip install playwright && "$PY" -m playwright install chromium
  fi
  "$PY" tools/ingest_docs.py --render || warn "rendered crawl failed too"
fi

# ------------------------------------------------------------------ verify
bold "Validating"
"$PY" skills/loop-api/scripts/validate_skill.py
VALID=$?

pages=$(count_refs)

bold "Result"
echo "    reference pages : $pages"
[ -f "$CACHE/all-urls.txt" ] && echo "    routes found    : $(wc -l < "$CACHE/all-urls.txt" | tr -d ' ')"
[ -s "$CACHE/spec/spec.json" ] && echo "    OpenAPI spec    : yes"

if [ "$pages" -lt 1 ]; then
  warn "No reference pages were produced."
  warn "Check $CACHE/ for what was captured, and see the notes in $REFS/README.md."
  exit 1
fi

if [ "$VALID" != "0" ]; then
  warn "Validation failed — review the errors above before committing."
  exit 1
fi

cat <<EOF

Corpus populated. Review the diff, then commit:

    git add $REFS
    git commit -m "Add Loop API reference corpus"
    git push

Then install into your harness:

    $PY tools/install.py --harness claude     # or codex / cursor / windsurf / mcp / all
EOF
