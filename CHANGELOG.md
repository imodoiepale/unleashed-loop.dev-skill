# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Populated `references/`** — 11 of the portal's 13 documentation pages, captured by
  manual transcription (`capture: manual-transcription`) because the portal is not
  reachable from the build environment. Covers Authorisation, LOOP Prompt, Transaction
  Status Inquiry, all three Pay-to endpoints and all three Send Money endpoints.
- Four derived reference files consolidated across pages: `signing.md` (the shared
  HMAC-SHA256 scheme, with LOOP's four published test vectors **recomputed and
  verified**), `conventions.md` (the `statusCode`-in-body convention, request envelope,
  and retry rules), `doc-conflicts.md` (15 self-contradictions found in LOOP's own
  documentation), and `coverage.md` (what the corpus does not contain).
- `LOOP_REFERENCES_DIR` environment variable for the MCP server, and an optional
  skill-directory argument for `validate_skill.py`, so both can target a corpus or
  skill other than the one they ship beside.
- Two capture methods are now a documented, first-class distinction: every reference
  file and `manifest.json` record `capture:`, and `SKILL.md` instructs the agent to
  qualify exact values when the corpus was transcribed rather than crawled.
- Loop API skill (`skills/loop-api/`) with three workflows: feasibility triage
  ("is this possible with Loop?"), building an integration, and debugging a failing
  call. `SKILL.md` deliberately contains no API facts — every claim the agent makes
  must come from the generated reference corpus.
- `tools/ingest_docs.py` — compiles Loop's documentation into `references/` from any
  of four sources: a live HTTP crawl, headless Chromium (for client-rendered
  portals), an OpenAPI/Swagger document, or an offline wget mirror. Every emitted
  file is stamped with its source URL and fetch date.
- `tools/crawl_loop.sh` — wget snapshot fenced to the `/devportal/docs/loop-api`
  namespace. Harvests routes from JavaScript bundles as well as HTML, hunts for an
  OpenAPI spec, respects `robots.txt`, and detects the empty-shell signature of a
  client-rendered portal instead of silently capturing nothing.
- `tools/setup.sh` — single-command crawl → convert → validate, choosing the best
  available capture route and falling back to a rendered crawl when the static one
  comes up empty.
- `tools/install.py` — adapts one source of truth to each harness's native
  convention: Claude Code skills, `AGENTS.md` (Codex, OpenCode), Cursor `.mdc`
  rules, Windsurf rules, and `GEMINI.md`.
- `mcp/loop_docs_server.py` — stdio MCP server exposing the same corpus as
  `loop_docs_index`, `loop_docs_search`, and `loop_docs_get`, with no dependencies
  beyond the Python standard library, so harnesses with no skill mechanism can still
  use it.
- `.claude-plugin/` — plugin and marketplace manifests for one-command installation
  in Claude Code.
- `skills/loop-api/scripts/validate_skill.py` — enforces skill structure, link
  integrity, and the provenance rule that no reference may exist without a traceable
  source. Runs in CI.
- `tests/` — pytest suite covering URL reconstruction from wget's layout, slug
  collapsing, provenance survival, client-rendered-shell detection, validator
  failure modes, installer idempotency, and the MCP JSON-RPC roundtrip.
- Security policy covering credential handling, sandbox defaults, and the rule that
  agents draft rather than execute money-moving calls.

### Notes
- `references/` ships empty. The corpus is generated from Loop's documentation by
  each user running `./tools/setup.sh`, which keeps the snapshot's provenance honest
  and leaves Loop's documentation under Loop's own terms.
