# references/ — generated, do not hand-edit

Every file in this directory (except this one) is produced by
`tools/ingest_docs.py` from Loop's published developer documentation. Each carries a
`<!-- source: ... -->` and `<!-- fetched: ... -->` comment so any claim the skill makes
can be traced back to a page and a date.

That provenance is the whole point. The skill's instructions forbid answering Loop API
questions from memory, so this directory is the only thing standing between a
developer and a confidently invented endpoint.

## Populate it

```bash
pip install -r tools/requirements.txt
python tools/ingest_docs.py                    # plain HTTP crawl
python tools/ingest_docs.py --render           # if the portal renders client-side
python tools/ingest_docs.py --openapi <url>    # if an OpenAPI spec is available
```

## Refresh it

Re-run the same command and review the diff. A diff in this directory is a change in
Loop's API surface, which is exactly the kind of change worth reading carefully before
committing.

## Why edits here get reverted

Hand-editing breaks the guarantee that references match the upstream docs. If a page
converts badly, fix the converter in `tools/ingest_docs.py` so the fix survives the
next refresh.
