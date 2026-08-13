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
| `nsait-logo.png` | NSAIT's mark, in the README footer beside the credit | Your own brand — use it wherever you like. Transparent background, ~400px wide renders crisply at 56px on high-DPI screens. |
| `loop-logo.png` | LOOP's mark, small and inline in "What's in the box" | Source from LOOP's own site or press kit, **not** a search-result thumbnail. ~200px wide is plenty for a 28px render. |

Both are wired up already but **commented out**, so nothing renders as a broken image
while the files are missing. Once a file is here, open `README.md`, search for its
filename, and delete the `<!--` and `-->` around that block.

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
