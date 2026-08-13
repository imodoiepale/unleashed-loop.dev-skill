#!/usr/bin/env python3
"""Install the Loop API skill into whichever agent harness you use.

There is exactly one source of truth — `skills/loop-api/` — and this script adapts it
to each harness's native convention. Keeping a single source means a docs refresh
updates every harness at once instead of drifting into six divergent copies.

    python tools/install.py --harness claude          # Claude Code (project scope)
    python tools/install.py --harness claude --global # Claude Code (all projects)
    python tools/install.py --harness codex           # AGENTS.md (Codex, and anything reading AGENTS.md)
    python tools/install.py --harness cursor
    python tools/install.py --harness windsurf
    python tools/install.py --harness gemini
    python tools/install.py --harness mcp             # prints MCP server config
    python tools/install.py --harness all
    python tools/install.py --harness claude --copy   # copy instead of symlink

Symlinks are the default so `git pull` in this repo updates your installed skill.
Use --copy on Windows or when you want a frozen snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skills" / "loop-api"
SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_NAME = "loop-api"

HARNESSES = ["claude", "codex", "cursor", "windsurf", "gemini", "opencode", "mcp"]


def read_description() -> str:
    text = SKILL_MD.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    lines, capture, out = block.splitlines(), False, []
    for line in lines:
        if re.match(r"^description:", line):
            capture = True
            rest = line.split(":", 1)[1].strip()
            if rest not in {">-", ">", "|", "|-"}:
                out.append(rest)
            continue
        if capture:
            if line.startswith((" ", "\t")):
                out.append(line.strip())
            else:
                break
    return " ".join(out).strip()


def link_or_copy(src: Path, dst: Path, copy: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)

    if copy or os.name == "nt":
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
        print(f"  copied  {dst}")
    else:
        dst.symlink_to(src, target_is_directory=src.is_dir())
        print(f"  linked  {dst} -> {src}")


def skill_path_for(target: Path) -> str:
    """How the installed instruction file should refer back to the skill.

    A relative path is nicer to read and survives the project being moved, but only
    when the skill actually lives inside the project. Otherwise relpath produces
    things like `../../../../../home/user/...`, which is both unreadable and breaks
    the moment anything is relocated — an absolute path is the honest choice there.
    """
    try:
        return "./" + str(SKILL_DIR.relative_to(target))
    except ValueError:
        return str(SKILL_DIR)


def pointer_body(description: str, relative_hint: str) -> str:
    """Shared body for harnesses that load a single instruction file.

    These harnesses have no progressive disclosure, so inlining the whole skill would
    burn context on every request. A pointer keeps the always-on cost small while
    still telling the agent when and how to load the real thing.
    """
    return f"""## Loop API ({SKILL_NAME})

{description}

When a task matches the above, read `{relative_hint}/SKILL.md` and follow it before
answering. It is the authoritative workflow for Loop API work.

Critical: never state a Loop endpoint, header, field, or error code from memory.
Every such claim must come from a file in `{relative_hint}/references/`, which is
generated from Loop's published documentation. Search it with:

    python {relative_hint}/scripts/search_docs.py "<term>"

If the references are missing, run `python tools/ingest_docs.py` rather than guessing.
This is a banking API — an invented endpoint costs a developer real time and money.
"""


def install_claude(target: Path, copy: bool, is_global: bool) -> None:
    base = Path.home() / ".claude" / "skills" if is_global else target / ".claude" / "skills"
    link_or_copy(SKILL_DIR, base / SKILL_NAME, copy)
    scope = "globally (all projects)" if is_global else f"in {target}"
    print(f"  Claude Code will load the skill {scope}.")


def install_agents_md(target: Path, description: str, filename: str, label: str) -> None:
    path = target / filename
    section = pointer_body(description, skill_path_for(target))
    marker = f"## Loop API ({SKILL_NAME})"

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if marker in existing:
            # Replace just our section so hand-written content in the file survives.
            existing = re.sub(rf"{re.escape(marker)}.*?(?=\n## |\Z)", section.strip() + "\n", existing, flags=re.S)
            path.write_text(existing, encoding="utf-8")
            print(f"  updated {path} ({label})")
            return
        path.write_text(existing.rstrip() + "\n\n" + section, encoding="utf-8")
        print(f"  appended to {path} ({label})")
        return

    path.write_text(f"# Agent instructions\n\n{section}", encoding="utf-8")
    print(f"  wrote   {path} ({label})")


def install_cursor(target: Path, description: str) -> None:
    path = target / ".cursor" / "rules" / f"{SKILL_NAME}.mdc"
    path.parent.mkdir(parents=True, exist_ok=True)
    rel = skill_path_for(target)
    # alwaysApply: false keeps this out of every prompt; Cursor pulls it in when the
    # description matches, which is the behaviour we want from a domain skill.
    path.write_text(
        f"---\ndescription: {description}\nalwaysApply: false\n---\n\n{pointer_body(description, rel)}",
        encoding="utf-8",
    )
    print(f"  wrote   {path} (Cursor rule)")


def install_windsurf(target: Path, description: str) -> None:
    path = target / ".windsurf" / "rules" / f"{SKILL_NAME}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    rel = skill_path_for(target)
    path.write_text(
        f"---\ntrigger: model_decision\ndescription: {description}\n---\n\n{pointer_body(description, rel)}",
        encoding="utf-8",
    )
    print(f"  wrote   {path} (Windsurf rule)")


def print_mcp(target: Path) -> None:
    server = REPO / "mcp" / "loop_docs_server.py"
    config = {"mcpServers": {"loop-docs": {"command": sys.executable, "args": [str(server)]}}}
    print("\n  Add this to your harness's MCP configuration:\n")
    print(json.dumps(config, indent=2))
    print("\n  Claude Code one-liner:")
    print(f"    claude mcp add loop-docs -- {sys.executable} {server}")
    print("\n  This works in any MCP-capable harness, including ones with no skill support.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--harness", required=True, choices=HARNESSES + ["all"])
    ap.add_argument("--target", type=Path, default=Path.cwd(), help="project directory (default: cwd)")
    ap.add_argument("--copy", action="store_true", help="copy files instead of symlinking")
    ap.add_argument("--global", dest="is_global", action="store_true", help="install for all projects (claude only)")
    args = ap.parse_args()

    if not SKILL_MD.exists():
        print(f"error: {SKILL_MD} not found", file=sys.stderr)
        return 1

    target = args.target.resolve()
    description = read_description()
    chosen = HARNESSES if args.harness == "all" else [args.harness]

    print(f"Installing {SKILL_NAME} into {target}\n")
    for harness in chosen:
        print(f"[{harness}]")
        if harness == "claude":
            install_claude(target, args.copy, args.is_global)
        elif harness == "codex":
            install_agents_md(target, description, "AGENTS.md", "Codex / AGENTS.md standard")
        elif harness == "gemini":
            install_agents_md(target, description, "GEMINI.md", "Gemini CLI")
        elif harness == "opencode":
            install_agents_md(target, description, "AGENTS.md", "OpenCode / AGENTS.md standard")
        elif harness == "cursor":
            install_cursor(target, description)
        elif harness == "windsurf":
            install_windsurf(target, description)
        elif harness == "mcp":
            print_mcp(target)
        print()

    refs = SKILL_DIR / "references"
    if not refs.exists() or not any(refs.glob("*.md")):
        print(
            "NOTE: references/ is not populated yet, so the skill knows the workflow but no\n"
            "      Loop API specifics. Run:  python tools/ingest_docs.py"
        )
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
