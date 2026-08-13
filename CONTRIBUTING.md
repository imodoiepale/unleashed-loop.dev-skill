# Contributing

Thanks for helping make Loop integrations less painful. This project is small and the
bar for contributing is low — but there is one rule that is not negotiable.

## The rule: every API fact must trace to a published page

`skills/loop-api/references/` exists so a developer can trust what the skill says:
every claim carries a source URL, a fetch date, and a capture method. Pull requests
that add Loop endpoints, headers, or error codes to `SKILL.md`, or that introduce
reference content with no traceable source, will be closed.

This isn't pedantry. One "I'm pretty sure the endpoint is..." poisons the guarantee,
and nobody downstream can tell which parts are trustworthy anymore.

### Two legitimate capture methods

Each reference file records which was used, in a `<!-- capture: -->` header and in
`manifest.json`.

| `capture` | How it was produced | Trust |
| --- | --- | --- |
| `crawler` | `tools/ingest_docs.py` against the live portal | Mechanical copy. **Preferred.** |
| `manual-transcription` | Portal text supplied by a maintainer, transcribed by hand | Same content, but not machine-verified — a typo is possible. |

The corpus currently in this repository is `manual-transcription`: the portal was not
reachable from the build machine, so the maintainer supplied the rendered page text.
Running the crawler replaces it with a `crawler` corpus, which is strictly better.

**Transcription is a fallback, not a licence to write from memory.** If you contribute
transcribed content you must have the page in front of you, and the file must record
the source URL it came from. Adding a field, code, or endpoint you did not read on a
published page is the thing this rule prohibits, regardless of capture method.

If a reference page converts badly, **fix the converter**, not the output.

### Verify what can be verified

Where the documentation publishes something checkable — test vectors, worked examples,
sample signatures — recompute it and say so in the file. The four HMAC vectors in
`references/signing.md` were verified this way, which is why that file's central claim
is stronger than a transcription alone would be.

## What's welcome

- Improvements to `tools/ingest_docs.py` — better content extraction, handling more of
  the portal's structure, OpenAPI support.
- Improvements to the workflows in `SKILL.md` — better debugging order, clearer
  feasibility triage, sharper guidance on what developers actually get stuck on.
- Support for another harness in `tools/install.py`.
- Eval cases in `evals/` that catch the skill being wrong or failing to trigger.
- Fixes to the MCP server.

## Setup

```bash
git clone https://github.com/imodoiepale/unleashed-loop.dev-skill
cd unleashed-loop.dev-skill
./tools/setup.sh                     # deps + crawl + convert + validate
pip install pytest                   # for the test suite
```

## Before opening a PR

```bash
pytest tests/ -v
python skills/loop-api/scripts/validate_skill.py
shellcheck -S warning tools/*.sh
```

CI runs all three, plus a secret scan and installer smoke tests.

The tests use a synthetic documentation mirror in `tests/fixtures/` rather than
hitting the live portal, so they run offline and don't hammer Loop's servers. If you
change the converter, add a fixture page that exercises the case you fixed.

### The secret scan

`evals/evals.json` contains a deliberately realistic fake API key — it tests that the
skill refuses to execute payments and tells the user to rotate a leaked credential. A
placeholder wouldn't exercise that behaviour. `.gitleaks.toml` carries a narrow,
documented path exemption for it. Do not widen that exemption; if your change trips
the scanner elsewhere, the scanner is probably right.

## Changing the skill description

The `description` in `SKILL.md` frontmatter is the only thing a harness reads when
deciding whether to load the skill, so changes there affect whether it triggers at
all. If you change it, add trigger cases to `evals/trigger-evals.json` covering both
what should and shouldn't pull the skill in — near-misses are the useful ones.

## Security

Never commit credentials, not even expired sandbox ones. See [SECURITY.md](SECURITY.md).

## Licence

Contributions are accepted under the MIT Licence.
