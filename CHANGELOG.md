# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
