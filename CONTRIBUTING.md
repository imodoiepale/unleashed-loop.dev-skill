# Contributing

Thanks for helping make Loop integrations less painful. This project is small and the
bar for contributing is low — but there is one rule that is not negotiable.

## The rule: don't hand-write API facts

`skills/loop-api/references/` is **generated** from Loop's published documentation by
`tools/ingest_docs.py`. Pull requests that hand-edit reference files, or that add Loop
endpoints, headers, or error codes to `SKILL.md`, will be closed.

This isn't pedantry. The entire value of the skill is that a developer can trust what
it says because every claim traces to a source URL and a fetch date. One hand-written
"I'm pretty sure the endpoint is..." poisons that guarantee, and nobody downstream can
tell which parts are trustworthy anymore.

If a reference page converts badly, **fix the converter**, not the output.

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
pip install -r tools/requirements.txt
python tools/ingest_docs.py          # populate references/
```

## Before opening a PR

```bash
python skills/loop-api/scripts/validate_skill.py
python -m compileall -q skills tools mcp
```

CI runs both, plus a secret scan and installer smoke tests.

## Changing the skill description

The `description` in `SKILL.md` frontmatter is the only thing a harness reads when
deciding whether to load the skill, so changes there affect whether it triggers at
all. If you change it, add trigger cases to `evals/trigger-evals.json` covering both
what should and shouldn't pull the skill in — near-misses are the useful ones.

## Security

Never commit credentials, not even expired sandbox ones. See [SECURITY.md](SECURITY.md).

## Licence

Contributions are accepted under the MIT Licence.
