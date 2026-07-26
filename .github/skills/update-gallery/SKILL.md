---
name: update-gallery
description: 'Update the church website gallery from the media@oregoneden.com Google Photos account. Use when the user says "update gallery", "갤러리 업데이트", "갤러리 새로고침", "sync albums", "앨범 동기화", "refresh the gallery", or asks to pull new/changed Google Photos albums into gallery.html. Scans the Google Photos albums page in the browser, merges the share links into tools/photos/albums.txt, then regenerates the album cards and cover images.'
argument-hint: '(no arguments needed)'
---

# Update the gallery from Google Photos

Regenerates the album cards on [gallery.html](../../../gallery.html) from the
albums in the **media@oregoneden.com** Google Photos account.

## Background

Google removed the broad Photos *Library* read scopes in March 2025:
`albums.list` returns only app-created albums and `sharedAlbums.list` was
retired. **There is no API that can list this account's albums**, so the album
links are scraped from the signed-in Photos web page, and each album's title,
date and cover come from the OpenGraph tags on its public share page.

An album only appears on the site if its share link contains `?key=` — without
it the link works for the owner but not for visitors.

## Procedure

### 1. Get a signed-in Google Photos tab

Check the shared browser pages for one on `photos.google.com/albums`.

- If it is already shared, use it.
- Otherwise call `open_browser_page` with
  `https://photos.google.com/albums` and ask the user to sign in as
  **media@oregoneden.com** and share the tab.

Never attempt to type credentials. If a sign-in form appears, stop and ask the
user to complete it themselves.

### 2. Collect the album links

Read [collect-albums.js](./scripts/collect-albums.js) and pass its contents as
the `code` argument to `run_playwright_code` against that tab, with
`timeoutMs: 180000`.

The grid is virtualised, so the script scrolls down and back up. It returns a
JSON array of `{url, title}` in page order. Expect roughly 25 albums; if it
returns 0, the tab is not signed in.

### 3. Merge into albums.txt

Save the returned JSON to a temp file and pipe it in:

```bash
cd "$(git rev-parse --show-toplevel)"
tools/photos/.venv/bin/python \
  .github/skills/update-gallery/scripts/merge_albums.py < "$TMPDIR/albums.json"
```

This preserves the header, year grouping comments, ordering and any
`| title | date` overrides. New albums are added at the top, existing share
links are refreshed in place, and albums that are missing or lack a `key=` are
commented out rather than deleted. Report its summary to the user.

### 4. Regenerate the gallery

```bash
tools/photos/.venv/bin/python \
  .github/skills/update-gallery/scripts/sync_albums.py
```

This fetches each album's title, date and cover, writes optimised `.jpg` +
`.webp` into `assets/photos/albums/`, rewrites the block between the
`ALBUMS:START` / `ALBUMS:END` markers in `gallery.html`, and prunes covers no
longer referenced. Use `--dry-run` first if the user wants a preview.

### 5. Verify

```bash
tools/photos/.venv/bin/python - <<'PY'
import json, collections, os
d = json.load(open('assets/photos/albums/albums.json'))
dupes = {k: v for k, v in collections.Counter(a['slug'] for a in d).items() if v > 1}
missing = [a['slug'] for a in d
           if not (os.path.exists(a['cover_jpg']) and os.path.exists(a['cover_webp']))]
print('albums:', len(d), '| duplicate slugs:', dupes or 'none', '| missing covers:', missing or 'none')
PY
```

Both must report `none`. Then reload `gallery.html` in the browser (serve with
`python3 -m http.server 8000` if nothing is running) and confirm the card count
matches and no image is broken.

### 6. Report

Tell the user how many albums are on the page, which were added or removed, and
list any album that was skipped for a missing `key=` — those need
**Share → Create link** in Google Photos before they can be published.

## Notes

- Korean album titles transliterate to nothing, so slugs fall back to a hash of
  the share id. Never assume the slug matches the title.
- To rename an album on the site without renaming it in Google Photos, add
  `| 제목 | 날짜` after its link in `albums.txt`; the merge step keeps it.
- Do not hand-edit between the `ALBUMS:START` / `ALBUMS:END` markers.
- Cover cropping reuses the `optimize-photos` skill's
  [process_images.py](../optimize-photos/scripts/process_images.py).
- This skill only touches `gallery.html`. For the hero/about/mission photos on
  the other pages, use the `update-site-photos` skill.
- See [tools/photos/README.md](../../../tools/photos/README.md) for environment
  setup.
