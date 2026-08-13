#!/usr/bin/env python3
"""Crawl the Loop developer portal and emit the skill's reference layer.

The skill deliberately keeps *no* API facts in SKILL.md. Everything an agent
states about Loop's endpoints, auth, and errors comes from `references/`, and
everything in `references/` comes from here — so every claim traces back to a
source URL and a fetch date. That is what makes the skill safe to trust: when
Loop changes, you re-run this and diff, rather than hand-editing prose and
hoping it still matches reality.

Usage
-----
    python tools/ingest_docs.py                      # crawl with plain HTTP
    python tools/ingest_docs.py --render             # crawl via headless Chromium (SPA docs)
    python tools/ingest_docs.py --openapi URL_OR_PATH
    python tools/ingest_docs.py --input-dir ./saved-html

Install deps first:  pip install -r tools/requirements.txt
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

DEFAULT_ROOT = "https://sandbox.loop.co.ke/devportal/docs/loop-api/introduction"
REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCES_DIR = REPO_ROOT / "skills" / "loop-api" / "references"

# Only follow links that stay inside the docs tree. Without this a crawler
# happily wanders into marketing pages, login flows, and the whole internet.
PATH_ALLOW = re.compile(r"/devportal/docs/")


@dataclass
class Page:
    url: str
    title: str
    markdown: str
    slug: str
    links: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------


def fetch_plain(url: str, timeout: int = 30) -> str:
    import requests

    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "unleashed-loop.dev-skill/ingest (+https://github.com/imodoiepale/unleashed-loop.dev-skill)"},
    )
    resp.raise_for_status()
    return resp.text


class RenderedFetcher:
    """Headless-Chromium fetcher for docs portals that render client-side.

    Many developer portals ship an empty <div id="root"> and build the page in
    JavaScript. Plain HTTP then yields a shell with no documentation in it — the
    crawl "succeeds" and produces nothing useful. If a page comes back
    suspiciously thin, re-run with --render.
    """

    def __init__(self, wait_ms: int = 2500):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch()
        self.page = self.browser.new_page()
        self.wait_ms = wait_ms

    def fetch(self, url: str) -> str:
        self.page.goto(url, wait_until="networkidle", timeout=60_000)
        self.page.wait_for_timeout(self.wait_ms)
        return self.page.content()

    def close(self) -> None:
        self.browser.close()
        self._pw.stop()


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------


def html_to_markdown(html: str, base_url: str) -> tuple[str, str, list[str]]:
    """Return (title, markdown, outbound_doc_links)."""
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    # Prefer the semantic content region. Docs portals bury the real content
    # under nav/sidebar chrome that would otherwise dominate every page and make
    # the references repetitive and hard for an agent to search.
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_=re.compile(r"(content|documentation|markdown|prose)", re.I))
        or soup.body
        or soup
    )

    links = []
    for a in soup.find_all("a", href=True):
        absolute = urljoin(base_url, a["href"]).split("#")[0]
        if PATH_ALLOW.search(urlparse(absolute).path):
            links.append(absolute)

    markdown = markdownify(str(main), heading_style="ATX", code_language="")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    # The emitted file already opens with the title as an H1, so keep the page's own
    # leading H1 from appearing twice.
    markdown = re.sub(r"^#\s+" + re.escape(title) + r"\s*\n+", "", markdown, count=1) if title else markdown
    return title or "Untitled", markdown, sorted(set(links))


def slugify(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/devportal/docs/")[-1] if "/devportal/docs/" in path else path
    slug = slug.strip("/").replace("/", "--")
    slug = re.sub(r"[^a-zA-Z0-9._-]", "-", slug).lower()
    # Every page sits under the same product namespace, so repeating it in each
    # filename is noise that makes the reference list harder to scan.
    slug = re.sub(r"^loop-api--", "", slug)
    return slug or "index"


def looks_empty(markdown: str) -> bool:
    """Heuristic for 'the crawler got a JS shell, not the docs'."""
    return len(markdown.split()) < 40


def url_from_mirror_path(path: Path, root_dir: Path) -> str:
    """Reconstruct the original URL from wget's on-disk mirror layout.

    wget writes `<prefix>/<host>/<path...>.html`, so the host is recoverable and the
    reference file can carry a real source URL. Provenance is the property that makes
    the whole corpus trustworthy — a reference that only says `file:///home/...` is
    useless to anyone reading the skill's output later.
    """
    try:
        rel = path.relative_to(root_dir)
    except ValueError:
        return f"file://{path}"

    parts = list(rel.parts)
    if not parts or "." not in parts[0]:
        return f"file://{path}"

    host, rest = parts[0], parts[1:]
    if rest and rest[-1] == "index.html":
        rest = rest[:-1]
    elif rest:
        rest[-1] = re.sub(r"\.html?$", "", rest[-1])
    return f"https://{host}/" + "/".join(rest)


# --------------------------------------------------------------------------
# crawl
# --------------------------------------------------------------------------


def crawl(root: str, fetcher, max_pages: int, delay: float) -> list[Page]:
    seen: set[str] = set()
    queue: list[str] = [root]
    pages: list[Page] = []
    thin: list[str] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        try:
            html = fetcher(url)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"  !! {url}: {exc}", file=sys.stderr)
            continue

        title, markdown, links = html_to_markdown(html, url)
        if looks_empty(markdown):
            thin.append(url)
        pages.append(Page(url=url, title=title, markdown=markdown, slug=slugify(url), links=links))
        print(f"  ok {url}  ({len(markdown.split())} words)")

        for link in links:
            if link not in seen:
                queue.append(link)

        if delay:
            time.sleep(delay)

    if thin:
        print(
            f"\n!! {len(thin)} page(s) came back nearly empty. If the portal renders "
            f"client-side, re-run with --render.\n   e.g. {thin[0]}",
            file=sys.stderr,
        )
    return pages


# --------------------------------------------------------------------------
# openapi
# --------------------------------------------------------------------------


def ingest_openapi(source: str) -> str:
    """Flatten an OpenAPI document into a compact endpoint table.

    A machine-readable spec beats scraped prose: it is unambiguous about methods,
    required parameters, and response shapes, which are exactly the details an
    agent gets wrong when guessing.
    """
    if source.startswith("http"):
        raw = fetch_plain(source)
    else:
        raw = Path(source).read_text(encoding="utf-8")

    try:
        spec = json.loads(raw)
    except json.JSONDecodeError:
        import yaml

        spec = yaml.safe_load(raw)

    lines = ["# Loop API — endpoint index (generated from OpenAPI)", ""]
    info = spec.get("info", {})
    if info:
        lines += [f"**{info.get('title', 'Loop API')}** version `{info.get('version', '?')}`", ""]
    for server in spec.get("servers", []):
        lines.append(f"- Server: `{server.get('url')}` {server.get('description', '')}".rstrip())
    lines.append("")

    for path, methods in sorted(spec.get("paths", {}).items()):
        for method, op in sorted(methods.items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            lines.append(f"## `{method.upper()} {path}`")
            if op.get("summary"):
                lines.append(op["summary"])
            if op.get("description"):
                lines.append("")
                lines.append(op["description"])
            params = op.get("parameters", [])
            if params:
                lines += ["", "| Param | In | Required | Type |", "| --- | --- | --- | --- |"]
                for p in params:
                    schema = p.get("schema", {})
                    lines.append(
                        f"| `{p.get('name')}` | {p.get('in')} | "
                        f"{'yes' if p.get('required') else 'no'} | {schema.get('type', '?')} |"
                    )
            responses = op.get("responses", {})
            if responses:
                codes = ", ".join(f"`{c}`" for c in sorted(responses))
                lines += ["", f"Responses: {codes}"]
            lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# emit
# --------------------------------------------------------------------------


def write_references(pages: list[Page], out_dir: Path, root: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched = time.strftime("%Y-%m-%d")

    for page in pages:
        body = (
            f"<!-- generated by tools/ingest_docs.py — do not hand-edit -->\n"
            f"<!-- source: {page.url} -->\n"
            f"<!-- fetched: {fetched} -->\n\n"
            f"# {page.title}\n\n"
            f"> Source: <{page.url}> (fetched {fetched})\n\n"
            f"{page.markdown}\n"
        )
        (out_dir / f"{page.slug}.md").write_text(body, encoding="utf-8")

    index = [
        "<!-- generated by tools/ingest_docs.py — do not hand-edit -->",
        "# Loop API reference index",
        "",
        f"Generated from <{root}> on {fetched}.",
        "",
        "Read the file that matches the developer's question rather than loading "
        "everything — these are the authoritative source for any claim about Loop's API.",
        "",
        "| Topic | File | Words |",
        "| --- | --- | --- |",
    ]
    for page in sorted(pages, key=lambda p: p.slug):
        index.append(f"| {page.title} | [`{page.slug}.md`](./{page.slug}.md) | {len(page.markdown.split())} |")
    index.append("")
    (out_dir / "INDEX.md").write_text("\n".join(index), encoding="utf-8")

    manifest = {
        "root": root,
        "fetched": fetched,
        "page_count": len(pages),
        "pages": [{"slug": p.slug, "url": p.url, "title": p.title} for p in pages],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(pages)} reference file(s) + INDEX.md + manifest.json to {out_dir}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.environ.get("LOOP_DOCS_ROOT", DEFAULT_ROOT))
    ap.add_argument("--out", type=Path, default=REFERENCES_DIR)
    ap.add_argument("--render", action="store_true", help="use headless Chromium (for client-rendered portals)")
    ap.add_argument("--openapi", help="URL or path to an OpenAPI/Swagger document")
    ap.add_argument("--input-dir", type=Path, help="convert already-saved .html files instead of crawling")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.4, help="seconds between requests; be polite")
    args = ap.parse_args()

    if args.openapi:
        text = ingest_openapi(args.openapi)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "openapi-endpoints.md").write_text(text, encoding="utf-8")
        print(f"Wrote {args.out / 'openapi-endpoints.md'}")
        return 0

    if args.input_dir:
        pages, thin = [], []
        seen_slugs: set[str] = set()
        for path in sorted(args.input_dir.glob("**/*.html")):
            url = url_from_mirror_path(path, args.input_dir)
            title, markdown, _ = html_to_markdown(path.read_text(encoding="utf-8", errors="replace"), url)
            if looks_empty(markdown):
                thin.append(str(path))
            slug = slugify(url)
            # wget writes both foo.html and foo/index.html for the same route; keep
            # whichever version actually carried content.
            if slug in seen_slugs:
                existing = next(p for p in pages if p.slug == slug)
                if len(markdown.split()) <= len(existing.markdown.split()):
                    continue
                pages.remove(existing)
            seen_slugs.add(slug)
            pages.append(Page(url=url, title=title, markdown=markdown, slug=slug))
            print(f"  ok {path.name}  -> {slug}  ({len(markdown.split())} words)")

        if thin:
            print(
                f"\n!! {len(thin)} captured page(s) were nearly empty. wget cannot execute\n"
                f"   JavaScript, so a client-rendered portal yields empty shells.\n"
                f"   Re-run with: python tools/ingest_docs.py --render",
                file=sys.stderr,
            )
        if not pages:
            print("No pages converted — nothing written.", file=sys.stderr)
            return 1
        write_references(pages, args.out, args.root)
        return 0

    print(f"Crawling {args.root}")
    if args.render:
        fetcher_obj = RenderedFetcher()
        try:
            pages = crawl(args.root, fetcher_obj.fetch, args.max_pages, args.delay)
        finally:
            fetcher_obj.close()
    else:
        pages = crawl(args.root, fetch_plain, args.max_pages, args.delay)

    if not pages:
        print("No pages captured — nothing written.", file=sys.stderr)
        return 1
    write_references(pages, args.out, args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
