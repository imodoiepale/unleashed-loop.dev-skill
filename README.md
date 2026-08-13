<h1 align="center">unleashed-loop.dev-skill</h1>

<p align="center">
  <strong>Talk to the Loop (NCBA) developer API in plain English — from Claude Code, Codex, Cursor, or any MCP-capable agent.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-blue.svg"></a>
  <a href="#supported-harnesses"><img alt="harnesses" src="https://img.shields.io/badge/harnesses-Claude%20Code%20%7C%20Codex%20%7C%20Cursor%20%7C%20Windsurf%20%7C%20MCP-brightgreen.svg"></a>
</p>

---

Integrating with a bank API usually means keeping twelve documentation tabs open and
guessing which one has the field name you need. This project turns Loop's developer
documentation into a **skill** your coding agent can use — so you ask "can I pay out to
several suppliers in one call?" and get an answer with the actual endpoint, the actual
payload, and a link to the page it came from.

```
you  ▸ can I schedule supplier payouts from my Loop account every Friday?
agent▸ reading references/INDEX.md … references/payments.md
       Yes, with one caveat. Loop documents <endpoint> for this. The scheduling
       is on your side — Loop doesn't expose a cron primitive. Here's the call:
       [runnable code]
       Source: sandbox.loop.co.ke/devportal/docs/loop-api/... (fetched 2026-08-13)
```

## Why this exists rather than "just paste the docs"

The failure mode of asking an LLM about a niche banking API is that it *invents* a
plausible endpoint, and you don't find out for an hour. So the skill is built around a
single hard constraint:

> **`SKILL.md` contains no API facts.** Every endpoint, header, field, and error code
> the agent states must come from `references/`, which is generated from Loop's
> published documentation with the source URL and fetch date stamped into every file.

If something isn't in the references, the skill instructs the agent to *say so* and
point you at the page — rather than guess. That's the difference between a tool you can
trust with a payments integration and one you have to double-check anyway.

## Quick start

```bash
git clone https://github.com/imodoiepale/unleashed-loop.dev-skill
cd unleashed-loop.dev-skill

# 1. Build the knowledge base from Loop's docs (one command, ~2 minutes)
./tools/setup.sh

# 2. Install into your harness — run this from your own project directory
python /path/to/unleashed-loop.dev-skill/tools/install.py --harness claude
```

Then just ask. The skill triggers on Loop, NCBA Loop, the devportal, and on payment /
payout / balance / transaction questions even when you don't name an endpoint.

> **`references/` ships empty on purpose.** You generate your own snapshot of Loop's
> documentation rather than trusting one baked in by a stranger — the provenance stays
> yours, the corpus stays current, and Loop's documentation stays under Loop's terms.

### What `setup.sh` does

It picks the best available capture route and falls back automatically:

| Route | When it's used | Why it's ranked here |
| --- | --- | --- |
| OpenAPI / Swagger spec | if the portal exposes one | Unambiguous about methods, required params, and response shapes |
| `wget` mirror | normal server-rendered docs | Fast, offline-convertible, no browser needed |
| Headless Chromium | if the portal renders client-side | The only thing that works on a JavaScript app |

The crawl is fenced to `/devportal/docs/loop-api`, harvests routes from **JavaScript
bundles as well as HTML** (docs portals often define navigation in JS where no
`<a href>` exists), and respects `robots.txt`.

The check that matters most is the empty-shell detector: a `wget` crawl of a
single-page app prints "saved" for every page while capturing nothing but empty
`<div id="root">` shells — it *looks* like it worked. The detector is structural
rather than length-based: a page counts as a shell only when it is both short **and**
contains no prose elements at all. Loop's portal publishes "documentation coming soon"
stubs, and a word-count threshold would fail those and send you to the browser path
for nothing.

To refresh later, re-run `./tools/setup.sh` and review the diff. A diff in
`references/` is a change in Loop's API surface.

### Using the crawler on another docs site

Nothing in the capture pipeline is Loop-specific beyond its defaults, so the same
tooling will snapshot any documentation portal:

```bash
BASE=https://docs.example.com \
DOCS_PATH=/api \
START_PAGE=/api/introduction \
./tools/crawl_loop.sh .cache/example-docs

python tools/ingest_docs.py --input-dir .cache/example-docs/pages --out my-references
```

`DOCS_PATH` is the fence — the crawl will not leave it, which is what keeps you out of
the site's login flow and the rest of its domain.

Then just ask. The skill triggers on Loop, NCBA Loop, the devportal, and on payment /
payout / balance / transaction questions even when you don't name an endpoint.

## Supported harnesses

| Harness | Install | Mechanism |
| --- | --- | --- |
| Claude Code | plugin (below) or `--harness claude` | `.claude/skills/loop-api/` |
| Codex | `--harness codex` | `AGENTS.md` section |
| Cursor | `--harness cursor` | `.cursor/rules/loop-api.mdc` |
| Windsurf | `--harness windsurf` | `.windsurf/rules/loop-api.md` |
| Gemini CLI | `--harness gemini` | `GEMINI.md` section |
| OpenCode | `--harness opencode` | `AGENTS.md` section |
| **Anything else** | `--harness mcp` | MCP server over stdio |

`--harness all` does the lot. Installs are symlinks by default, so `git pull` updates
every harness at once; pass `--copy` for a frozen snapshot or on Windows.

**Claude Code plugin** — the lowest-friction path, installs the skill and the MCP
server together:

```
/plugin marketplace add imodoiepale/unleashed-loop.dev-skill
/plugin install loop-api
```

You still need to run `./tools/setup.sh` once to build the corpus.

For harnesses with no skill or rules mechanism, the MCP server exposes the same corpus
as three tools — `loop_docs_index`, `loop_docs_search`, `loop_docs_get` — with no
dependencies beyond the Python standard library:

```bash
claude mcp add loop-docs -- python /path/to/mcp/loop_docs_server.py
```

## What the skill actually does

Three workflows, tuned to what developers get stuck on:

- **"Is this possible?"** — translates the goal into banking terms, searches the
  references, then answers *supported* / *supported with caveats* / *not documented*.
  It surfaces onboarding and entitlement blockers early, because in banking those are
  usually the real answer rather than anything to do with code.
- **Building an integration** — auth working first, sandbox confirmed, smallest
  read-only call proven, and only then the feature. Failure paths are treated as part
  of the feature, not an afterthought.
- **Debugging** — an ordered checklist that starts with the real status code and
  environment mismatches, which is where the cause usually is.

## Credential safety

This is a banking API, so the skill carries non-negotiable rules: never write a secret
into source or a message, always default examples to sandbox, and **never execute a
money-moving call on its own initiative** — it drafts the request and hands it to you.
Full policy in [SECURITY.md](SECURITY.md); CI runs a secret scan on every push.

## Layout

```
skills/loop-api/
  SKILL.md            workflow + navigation (no API facts, by design)
  references/         GENERATED from Loop's docs — every file stamped with source + date
  scripts/            search_docs.py, validate_skill.py
tools/
  setup.sh            one command: crawl → convert → validate
  crawl_loop.sh       namespace-fenced wget snapshot + JS route harvesting
  ingest_docs.py      compiler → references/  (HTTP, Chromium, OpenAPI, or mirror)
  install.py          one source of truth → every harness's native format
mcp/
  loop_docs_server.py stdio MCP server over the same corpus (stdlib only)
tests/                pytest suite over a synthetic docs mirror
evals/                trigger and task test cases
```

## Keeping it current

Re-run `python tools/ingest_docs.py` and review the diff — a diff in `references/` is a
change in Loop's API surface. Every reference file records when it was fetched, and the
skill tells the agent to trust the live API over a stale snapshot.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One rule above all: **don't hand-write API
facts.** If a page converts badly, fix the converter, not its output.

## Disclaimer

Unofficial and community-maintained. Not published, endorsed, or supported by NCBA or
Loop. The references are a snapshot of public documentation, not a contract — confirm
settlement behaviour, limits, fees, and compliance obligations with Loop directly.
Licensed under the [MIT Licence](LICENSE).
