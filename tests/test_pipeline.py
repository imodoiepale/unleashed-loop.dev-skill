"""Tests for the docs-to-skill pipeline.

These lock down the properties the skill's trustworthiness actually rests on:
provenance survives conversion, a client-rendered shell is detected rather than
silently accepted as content, and the validator refuses a corpus it cannot trace.
Cosmetic details of the conversion are deliberately not asserted — they change
whenever the portal's markup changes, and pinning them would make the suite noisy
without making the skill safer.

    pip install pytest beautifulsoup4 markdownify
    pytest tests/ -v
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURE_MIRROR = Path(__file__).parent / "fixtures" / "mirror"
sys.path.insert(0, str(REPO / "tools"))

ingest = pytest.importorskip("ingest_docs", reason="needs beautifulsoup4 + markdownify")


@pytest.fixture(scope="module")
def corpus(tmp_path_factory) -> Path:
    """Run the real ingestion over the fixture mirror once, reuse the output."""
    out = tmp_path_factory.mktemp("references")
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "ingest_docs.py"),
         "--input-dir", str(FIXTURE_MIRROR), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


# ---------------------------------------------------------------- URL recovery

def test_url_reconstructed_from_wget_layout():
    """Without this the corpus loses provenance and every claim becomes uncitable."""
    path = FIXTURE_MIRROR / "sandbox.loop.co.ke/devportal/docs/loop-api/introduction.html"
    url = ingest.url_from_mirror_path(path, FIXTURE_MIRROR)
    assert url == "https://sandbox.loop.co.ke/devportal/docs/loop-api/introduction"


def test_index_html_maps_to_directory_url():
    path = FIXTURE_MIRROR / "sandbox.loop.co.ke/devportal/docs/loop-api/send-money/index.html"
    url = ingest.url_from_mirror_path(path, FIXTURE_MIRROR)
    assert url.endswith("/loop-api/send-money")
    assert "index" not in url


def test_unrecognisable_path_degrades_to_file_url(tmp_path):
    stray = tmp_path / "notahost" / "page.html"
    stray.parent.mkdir(parents=True)
    stray.write_text("<html></html>")
    assert ingest.url_from_mirror_path(stray, tmp_path).startswith("file://")


# ---------------------------------------------------------------- slugs

def test_nested_index_collapses_to_route_name(corpus):
    assert (corpus / "send-money.md").exists()
    assert not (corpus / "index.md").exists()


def test_slug_drops_redundant_product_prefix(corpus):
    assert (corpus / "introduction.md").exists()
    assert not (corpus / "loop-api--introduction.md").exists()


# ---------------------------------------------------------------- provenance

def test_every_reference_carries_source_and_date(corpus):
    pages = [p for p in corpus.glob("*.md") if p.name not in {"INDEX.md", "README.md"}]
    assert pages, "fixture produced no reference pages"
    for page in pages:
        text = page.read_text()
        assert "<!-- source: https://" in text, f"{page.name} lost its source URL"
        assert "<!-- fetched:" in text, f"{page.name} lost its fetch date"


def test_manifest_matches_files_on_disk(corpus):
    manifest = json.loads((corpus / "manifest.json").read_text())
    for page in manifest["pages"]:
        assert (corpus / f"{page['slug']}.md").exists()
    assert manifest["page_count"] == len(manifest["pages"])


# ---------------------------------------------------------------- conversion

def test_chrome_stripped_content_kept(corpus):
    text = (corpus / "introduction.md").read_text()
    assert "sidebar noise" not in text
    assert "footer noise" not in text
    assert "var x=1" not in text
    assert "example.invalid" in text          # code block survived
    assert "| Header | Required |" in text    # table survived


def test_title_not_duplicated(corpus):
    body = (corpus / "send-money.md").read_text().split("(fetched", 1)[1]
    assert body.count("# Send Money") == 0, "page H1 repeated after the template heading"


# ---------------------------------------------------------------- SPA detection

def test_client_rendered_shell_is_flagged():
    """A wget crawl of an SPA 'succeeds' while capturing nothing. If this check
    regresses, the pipeline emits an empty corpus and reports success."""
    assert ingest.looks_empty('<div id="root"></div>')
    assert not ingest.looks_empty(" ".join(["word"] * 200))


def test_shell_page_reported_on_stderr(tmp_path):
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "ingest_docs.py"),
         "--input-dir", str(FIXTURE_MIRROR), "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert "nearly empty" in result.stderr
    assert "--render" in result.stderr


def _crawler_is_shell(html: str, tmp_path: Path, name: str) -> bool:
    """Invoke the crawler's own is_shell() against a file, in isolation."""
    page = tmp_path / name
    page.write_text(html)
    snippet = subprocess.run(
        ["sed", "-n", "/^is_shell()/,/^}/p", str(REPO / "tools" / "crawl_loop.sh")],
        capture_output=True, text=True, check=True,
    ).stdout
    return subprocess.run(
        ["bash", "-c", f"{snippet}\nis_shell {page}"], capture_output=True
    ).returncode == 0


def test_crawler_shell_check_spares_short_placeholder_pages(tmp_path):
    """The crawler must not mistake a genuinely short page for an unrendered shell.

    Loop's portal publishes 'documentation coming soon' stubs. Judging shells on
    word count alone failed those, which wrongly told the user their whole crawl
    was empty and sent them to the headless path for no reason.
    """
    assert _crawler_is_shell('<div id="root"></div>', tmp_path, "shell.html")
    assert not _crawler_is_shell(
        "<h1>Pay to M-Pesa Till</h1><p>Detailed documentation coming soon.</p>",
        tmp_path, "stub.html",
    )
    assert not _crawler_is_shell(
        "<h1>Overview</h1>" + "<p>word</p>" * 50, tmp_path, "full.html"
    )


# ---------------------------------------------------------------- validator

def _validate(env_dir: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO / "skills" / "loop-api" / "scripts" / "validate_skill.py")],
        capture_output=True, text=True,
    )


def test_validator_passes_on_current_skill():
    assert _validate().returncode == 0


def test_validator_rejects_reference_without_provenance(corpus):
    """The whole safety story is 'every claim is traceable'. A reference file with
    no source comment must fail the build, not slip through as a warning."""
    refs = REPO / "skills" / "loop-api" / "references"
    planted = refs / "_pytest_untraceable.md"
    planted.write_text("# Fake page\n\nThe endpoint is POST /invented.\n")
    try:
        result = _validate()
        assert result.returncode == 1
        assert "provenance" in result.stderr
    finally:
        planted.unlink()


def test_validator_flags_empty_corpus(tmp_path):
    """Warn when the corpus is empty — the one state where the skill silently cannot
    do its job. Built in a temp skill dir so the check survives this repo's own
    references being populated."""
    skill = tmp_path / "skills" / "loop-api"
    (skill / "references").mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        "---\nname: loop-api\ndescription: Use this when testing the validator.\n---\n\n# Test\n"
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "skills" / "loop-api" / "scripts" / "validate_skill.py"), str(skill)],
        capture_output=True, text=True,
    )
    assert "no generated pages yet" in result.stdout


def test_validator_accepts_the_shipped_corpus():
    """The references committed to this repo must pass their own provenance check."""
    result = _validate()
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------- installer

def test_installer_is_idempotent_and_preserves_user_content(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    install = [sys.executable, str(REPO / "tools" / "install.py"), "--target", str(proj)]

    subprocess.run(install + ["--harness", "codex"], capture_output=True, check=True)
    agents = proj / "AGENTS.md"
    agents.write_text(agents.read_text() + "\n## My own rules\n\nUse tabs.\n")

    subprocess.run(install + ["--harness", "codex"], capture_output=True, check=True)
    text = agents.read_text()
    assert text.count("## Loop API (loop-api)") == 1, "re-install duplicated the section"
    assert "Use tabs." in text, "re-install clobbered hand-written content"


def test_installer_writes_each_harness_native_format(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    for harness in ("codex", "cursor", "windsurf", "gemini"):
        subprocess.run(
            [sys.executable, str(REPO / "tools" / "install.py"),
             "--harness", harness, "--target", str(proj)],
            capture_output=True, check=True,
        )
    assert (proj / "AGENTS.md").exists()
    assert (proj / "GEMINI.md").exists()
    assert (proj / ".cursor" / "rules" / "loop-api.mdc").exists()
    assert (proj / ".windsurf" / "rules" / "loop-api.md").exists()


def test_installer_uses_absolute_path_when_skill_is_outside_project(tmp_path):
    """relpath across unrelated trees yields ../../../../.. chains that break on move."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(
        [sys.executable, str(REPO / "tools" / "install.py"),
         "--harness", "codex", "--target", str(proj)],
        capture_output=True, check=True,
    )
    assert "../../.." not in (proj / "AGENTS.md").read_text()


# ---------------------------------------------------------------- MCP server

def _mcp(*messages: dict, references: Path | None = None) -> list[dict]:
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    env = dict(os.environ)
    if references is not None:
        env["LOOP_REFERENCES_DIR"] = str(references)
    result = subprocess.run(
        [sys.executable, str(REPO / "mcp" / "loop_docs_server.py")],
        input=payload, capture_output=True, text=True, timeout=30, env=env,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def test_mcp_handshake_and_tool_listing():
    responses = _mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert responses[0]["result"]["serverInfo"]["name"] == "loop-docs"
    assert responses[0]["result"]["protocolVersion"]
    names = {t["name"] for t in responses[1]["result"]["tools"]}
    assert names == {"loop_docs_index", "loop_docs_search", "loop_docs_get"}


def test_mcp_ignores_notifications():
    """A notification has no id and must not get a response, or the client desyncs."""
    responses = _mcp(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 9, "method": "ping", "params": {}},
    )
    assert len(responses) == 1
    assert responses[0]["id"] == 9


def test_mcp_unknown_method_returns_error():
    responses = _mcp({"jsonrpc": "2.0", "id": 1, "method": "nope/nope", "params": {}})
    assert responses[0]["error"]["code"] == -32601


def test_mcp_reports_empty_corpus_instead_of_guessing(tmp_path):
    """With no references, the server must tell the agent to stop rather than let it
    fall back on memory — that fallback is the failure this project exists to prevent."""
    empty = tmp_path / "references"
    empty.mkdir()
    responses = _mcp({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "loop_docs_search", "arguments": {"query": "anything"}},
    }, references=empty)
    text = responses[0]["result"]["content"][0]["text"]
    assert "ingest_docs.py" in text or "No matches" in text


def test_mcp_searches_the_shipped_corpus():
    """A real query against the committed references must return a grounded hit."""
    responses = _mcp({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "loop_docs_search", "arguments": {"query": "nonce"}},
    })
    text = responses[0]["result"]["content"][0]["text"]
    assert "signing" in text.lower()
    assert "sandbox.loop.co.ke" in text


# ---------------------------------------------------------------- MCP hardening

def _get(slug: str) -> str:
    return _mcp({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "loop_docs_get", "arguments": {"slug": slug}},
    })[0]["result"]["content"][0]["text"]


@pytest.mark.parametrize("slug", [
    "/etc/passwd",                    # absolute: Path('/refs') / '/etc/x' DISCARDS the base
    "/etc/hosts",
    "../" * 8 + "etc/passwd",         # relative walk out of the corpus
    "signing/../../../../etc/passwd",
    "....//....//etc/passwd",         # naive ".." stripping would collapse to ../../
])
def test_mcp_get_refuses_to_escape_the_corpus(slug, tmp_path):
    """The slug reaches this server from wherever the agent got it — a web page, a PR
    comment, a file. It must not be usable to read anything outside references/.

    The original implementation built `REFERENCES / f"{slug}.md"`, which is unsafe:
    Python's `/` discards the left operand when the right is absolute, so a slug of
    "/etc/passwd" escaped the corpus entirely and read /etc/passwd.md.
    """
    secret = tmp_path / "secret.md"
    secret.write_text("TOPSECRET-CANARY")
    out = _get(slug)
    assert "TOPSECRET-CANARY" not in out
    assert "root:" not in out
    assert out.startswith("No page with slug")

    # And the same escape attempt aimed squarely at a real file must also fail.
    assert "TOPSECRET-CANARY" not in _get(str(secret.with_suffix("")))


@pytest.mark.parametrize("slug", ["signing", "signing.md", "  signing  "])
def test_mcp_get_still_accepts_ordinary_slugs(slug):
    """Hardening must not break the normal path, including forgiving variants."""
    assert _get(slug).startswith("<!-- source:")


def test_mcp_search_rejects_empty_and_oversized_queries():
    def q(query, **kw):
        return _mcp({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "loop_docs_search", "arguments": {"query": query, **kw}},
        })[0]["result"]["content"][0]["text"]

    assert "Provide a search term" in q("   ")
    # A long hand-crafted pattern is the input that turns catastrophic backtracking
    # into a hang, so length is capped before compilation.
    assert "too long" in q("a" * 250)


def test_mcp_search_clamps_context_window():
    """An unbounded context returns the whole corpus and floods the agent's context."""
    def size(ctx):
        return len(_mcp({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "loop_docs_search",
                       "arguments": {"query": "nonce", "context": ctx}},
        })[0]["result"]["content"][0]["text"])

    assert size(99999) == size(20), "context above the cap must behave as the cap"


def test_mcp_survives_a_corrupt_manifest(tmp_path):
    """A malformed manifest must not crash the index — losing it would push the agent
    back onto memory, which is the failure this project exists to prevent."""
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "manifest.json").write_text("{ this is not json")
    (refs / "page.md").write_text("<!-- source: https://example.test/x -->\n# Page\nbody\n")
    responses = _mcp({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "loop_docs_index", "arguments": {}},
    }, references=refs)
    text = responses[0]["result"]["content"][0]["text"]
    assert "page" in text
    assert not responses[0]["result"].get("isError")


# ---------------------------------------------------------------- README claims

def test_readme_badges_match_reality():
    """The README makes countable claims. A stale badge is a small lie, and this
    project's whole pitch is that its claims are checkable — so check them."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")

    declared = int(re.search(r"badge/tests-(\d+)%20passing", readme).group(1))
    actual = len([
        line for line in (REPO / "tests" / "test_pipeline.py").read_text().splitlines()
        if line.startswith("def test_")
    ])
    # parametrised cases expand at runtime, so the badge counts at least the functions
    assert declared >= actual, f"README claims {declared} tests but {actual} functions exist"

    manifest = json.loads(
        (REPO / "skills" / "loop-api" / "references" / "manifest.json").read_text()
    )
    pages_claim = int(re.search(r"badge/docs%20pages-(\d+)%20captured", readme).group(1))
    assert pages_claim <= manifest["page_count"], (
        f"README claims {pages_claim} captured pages but the manifest lists "
        f"{manifest['page_count']} entries"
    )


def test_readme_has_no_broken_local_links():
    """Every relative link and image in the README must resolve, ignoring commented-out
    blocks (logo slots are parked there until a file is committed)."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    active = re.sub(r"<!--.*?-->", "", readme, flags=re.S)

    targets = [
        t for t in re.findall(r"\]\(([^)#]+?)(?:#[^)]*)?\)", active)
        if not t.startswith(("http://", "https://", "mailto:"))
    ]
    targets += [
        s for s in re.findall(r'<img[^>]+src="([^"]+)"', active)
        if not s.startswith(("http://", "https://", "data:"))
    ]
    missing = [t for t in targets if not (REPO / t).exists()]
    assert not missing, f"README links to missing files: {missing}"
