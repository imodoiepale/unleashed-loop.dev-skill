# assets/

Local copies of images used by the README.

## Current state: nothing here is required

Both logos load from their owners' own servers:

| Logo | Where it appears | Source |
| --- | --- | --- |
| LOOP | README header, 80px | `https://loop.co.ke/wp-content/uploads/2025/10/loop-dfs-logo.png` |
| NSAIT | README footer, 72px | `https://nsait.co.ke/col-bal/uploads/2025/07/logo-4.png` |

Both are stable paths on the owners' sites, and GitHub serves external images through
`camo.githubusercontent.com`, which caches them and keeps visitor IPs off the origin
servers. Nothing needs committing unless a URL moves.

## When to commit a local copy

Drop a file here and point the README at it instead if:

- **the URL breaks** — a site redesign moves the upload path;
- **you want the README to render offline**, in a fork, or in a mirror that cannot
  reach the open internet;
- **the mark disappears in dark mode** and you need a second, light variant.

```bash
cp ~/Downloads/logo.png assets/nsait-logo.png
git add assets/nsait-logo.png
git commit -m "Add local NSAIT logo"
```

Then change the `src` in `README.md` from the URL to `assets/nsait-logo.png`.

> **Not this kind of URL.** The logo was first supplied as a Google Images thumbnail
> (`encrypted-tbn0.gstatic.com/images?q=tbn:...`). Those are session-scoped cache keys —
> they rotate, expire, and are low-resolution. Never point a README at one. A direct
> path on the owner's own domain, as used above, is fine.

## Sizing

The README sets **`height` only** and lets the browser scale width to match. That keeps
the aspect ratio whatever the source dimensions are, so a logo is never stretched. Do
not add a `width` alongside it.

## Dark mode

GitHub renders READMEs in both light and dark themes. A logo with dark text on a
transparent background vanishes against a dark backdrop.

Check both themes. If one disappears, add a light variant and swap on theme:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-light.png">
  <img src="assets/logo.png" alt="NSAIT" height="72">
</picture>
```

## Icons

Social links in the README footer use **[shields.io](https://shields.io)** badges,
which render their glyphs from **[Simple Icons](https://simpleicons.org)** (CC0) via the
`logo=` parameter — e.g. `logo=linkedin`. That needs no committed files.

If you ever want a self-hosted icon instead: commit the SVG here and reference it by
relative path with `<img src="assets/name.svg">`. Do **not** hot-link an SVG from an
external CDN — GitHub's image proxy rasterises those and they look broken — and note
that inline `<svg>` markup is stripped by the README sanitiser.

## Trademark

LOOP and NCBA marks belong to their owners. This project is unofficial — the README
says so directly beneath the LOOP logo in the header, and again in its licence section.
The mark identifies which API the skill documents (nominative use); it is not a claim
of endorsement, affiliation, or approval. If LOOP or NCBA ever ask for it to be
removed, remove it.
