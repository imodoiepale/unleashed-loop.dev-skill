#!/usr/bin/env python3
"""MCP server exposing the Loop API reference corpus.

Skills are the better experience where they're supported, but plenty of harnesses
have no skill mechanism and every serious one speaks MCP. This serves the exact same
`references/` corpus over stdio JSON-RPC so the skill's knowledge is reachable
anywhere, with no dependencies beyond the Python standard library.

Register it with (for example) Claude Code:

    claude mcp add loop-docs -- python /abs/path/to/mcp/loop_docs_server.py

or in any harness's MCP config:

    {"mcpServers": {"loop-docs": {"command": "python",
      "args": ["/abs/path/to/mcp/loop_docs_server.py"]}}}
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Overridable so the server can be pointed at a corpus built elsewhere — a shared
# snapshot, a second product's references, or an empty directory under test.
REFERENCES = Path(
    os.environ.get("LOOP_REFERENCES_DIR")
    or Path(__file__).resolve().parent.parent / "skills" / "loop-api" / "references"
)
PROTOCOL_VERSION = "2025-06-18"

GROUNDING_NOTE = (
    "Answer the developer only from the text above, and cite the source URL. "
    "If it does not cover the question, say the documentation does not cover it "
    "rather than inventing an endpoint — this is a banking API and a plausible "
    "guess is worse than an admission of uncertainty."
)

TOOLS = [
    {
        "name": "loop_docs_index",
        "description": (
            "List every available Loop API documentation page with its topic and source URL. "
            "Call this first to find out which page answers the developer's question."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "loop_docs_search",
        "description": (
            "Full-text search across the Loop API documentation. Use for finding which page "
            "mentions a field name, endpoint, error code, or capability. Returns matching "
            "passages with their source URLs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text or regular expression to find."},
                "context": {"type": "integer", "description": "Lines of context per hit (default 3)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "loop_docs_get",
        "description": (
            "Retrieve the full text of one Loop API documentation page by its slug, as listed "
            "by loop_docs_index. Use when you need complete request/response detail."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string", "description": "Page slug, e.g. 'introduction'."}},
            "required": ["slug"],
        },
    },
]


def corpus() -> list[Path]:
    if not REFERENCES.exists():
        return []
    return sorted(p for p in REFERENCES.glob("*.md") if p.name not in {"INDEX.md", "README.md"})


def source_url(text: str) -> str:
    match = re.search(r"<!-- source: (.+?) -->", text)
    return match.group(1) if match else "unknown"


def not_populated() -> str:
    return (
        "The Loop documentation corpus has not been generated yet, so there is nothing to "
        "search. Tell the developer to run `python tools/ingest_docs.py` in the "
        "unleashed-loop.dev-skill repository (add --render if the portal renders "
        "client-side). Do not answer Loop API questions from memory in the meantime."
    )


def tool_index() -> str:
    files = corpus()
    if not files:
        return not_populated()
    manifest = REFERENCES / "manifest.json"
    header = ""
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        header = f"Loop API docs — {data.get('page_count', len(files))} pages, fetched {data.get('fetched', '?')}\n\n"
    lines = [header + "| slug | title | source |", "| --- | --- | --- |"]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), path.stem)
        lines.append(f"| `{path.stem}` | {title} | {source_url(text)} |")
    return "\n".join(lines)


def tool_search(query: str, context: int = 3) -> str:
    files = corpus()
    if not files:
        return not_populated()
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    out: list[str] = []
    hits = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        matched = [i for i, line in enumerate(lines) if pattern.search(line)]
        if not matched:
            continue
        out.append(f"\n=== {path.stem} === (source: {source_url(text)})")
        shown: set[int] = set()
        for idx in matched:
            if hits >= 30:
                out.append("... truncated; narrow the query.")
                break
            lo, hi = max(0, idx - context), min(len(lines), idx + context + 1)
            if all(i in shown for i in range(lo, hi)):
                continue
            out.append("  ...")
            for i in range(lo, hi):
                out.append(f"  {lines[i]}")
                shown.add(i)
            hits += 1

    if not out:
        return (
            f"No matches for {query!r} across {len(files)} Loop documentation pages. "
            "The documentation likely does not cover this — say so rather than guessing, "
            "and suggest the developer confirm with Loop support."
        )
    return "\n".join(out) + "\n\n" + GROUNDING_NOTE


def tool_get(slug: str) -> str:
    files = corpus()
    if not files:
        return not_populated()
    path = REFERENCES / f"{slug}.md"
    if not path.exists():
        available = ", ".join(p.stem for p in files)
        return f"No page with slug {slug!r}. Available: {available}"
    return path.read_text(encoding="utf-8", errors="replace") + "\n\n" + GROUNDING_NOTE


def dispatch(name: str, args: dict) -> str:
    if name == "loop_docs_index":
        return tool_index()
    if name == "loop_docs_search":
        return tool_search(args.get("query", ""), int(args.get("context", 3)))
    if name == "loop_docs_get":
        return tool_get(args.get("slug", ""))
    raise ValueError(f"unknown tool: {name}")


def respond(msg_id, result=None, error=None) -> None:
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method, msg_id = msg.get("method"), msg.get("id")

        # Notifications carry no id and must not be answered.
        if msg_id is None:
            continue

        if method == "initialize":
            respond(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "loop-docs", "version": "0.1.0"},
            })
        elif method == "tools/list":
            respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params", {})
            try:
                text = dispatch(params.get("name", ""), params.get("arguments") or {})
                respond(msg_id, {"content": [{"type": "text", "text": text}]})
            except Exception as exc:  # noqa: BLE001 - surface to the client as a tool error
                respond(msg_id, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True})
        elif method == "ping":
            respond(msg_id, {})
        else:
            respond(msg_id, error={"code": -32601, "message": f"method not found: {method}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
