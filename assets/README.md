# assets/

Images used by the README. **Commit them here** rather than hot-linking.

## Why not hot-link?

The logo was originally supplied as a Google Images thumbnail URL
(`encrypted-tbn0.gstatic.com/images?q=tbn:...`). Those are session-scoped cache
entries: they rotate, they expire, and they are low-resolution thumbnails. A README
pointing at one shows a broken-image icon to every visitor once it lapses — and shows
nothing at all to anyone reading the repository offline.

A committed file renders forever, works offline, and is version-controlled like
everything else.

## What to add

| File | Purpose | Notes |
| --- | --- | --- |
| `nsait-logo.png` | **Optional.** A local copy of the NSAIT mark. | The README currently loads it from `https://nsait.co.ke/col-bal/uploads/2025/07/logo-4.png`. That is fine — it is a stable path on NSAIT's own server, and GitHub caches it through `camo.githubusercontent.com`. Committing a copy only matters if that URL ever moves. |
| `loop-logo.png` | LOOP's mark, small and inline in "What's in the box" | Source from LOOP's own site or press kit, **not** a search-result thumbnail. ~200px wide is plenty for a 28px render. |

The LOOP slot is wired up but **commented out**, so it does not render as a broken
image while the file is missing. Once the file is here, open `README.md`, search for
`loop-logo.png`, and delete the `<!--` and `-->` around that block.

## Sizing

The README sets **`height` only** and lets the browser scale width to match. That
preserves the aspect ratio whatever the source dimensions are, so a logo never comes
out stretched. Do not add a `width` alongside it.

Current heights: **80px** in the header, **72px** in the footer.

## Dark mode

GitHub renders READMEs in both light and dark themes. A logo with dark text on a
transparent background disappears against a dark backdrop.

If that happens, add a light variant and swap on theme:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/nsait-logo-light.png">
  <img src="assets/nsait-logo.png" alt="NSAIT" height="80">
</picture>
```

### Adding them

```bash
# from the repo root, with the file saved somewhere on your machine
cp ~/Downloads/nsait-logo.png assets/
git add assets/nsait-logo.png
git commit -m "Add NSAIT logo"
git push
```

PNG with a transparent background is the safe choice — it works on GitHub's light and
dark themes alike. A logo on a white rectangle looks broken in dark mode.

## Trademark

LOOP and NCBA marks belong to their owners. This is an unofficial, community-maintained
project — see the licence section of the README. The mark is used only to identify
which API the skill documents, which is nominative use; it is not a claim of
endorsement, affiliation, or approval.

Keep it **small, inline, and away from the header**. A vendor logo at the top of a
third-party project reads as official, which this project explicitly is not. If LOOP or
NCBA ever object to its use here, remove it — that is not a fight worth having over a
28-pixel image.
