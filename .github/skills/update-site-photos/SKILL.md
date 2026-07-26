---
name: update-site-photos
description: 'Replace the photos in the church website''s fixed image slots (hero banner, About photo, mission cards, home gallery tiles) using the media@oregoneden.com Google Photos account. Use when the user says "update site photos", "홈페이지 사진 교체", "메인 사진 바꿔줘", "hero 사진 교체", "replace the hero image", "새 사진으로 바꿔줘", or wants to refresh the photos on index.html / about.html. Opens the Google Photos Picker, downloads the chosen photos, then crops and optimises them into assets/photos/.'
argument-hint: '[slot names, e.g. hero or gallery-5]'
---

# Update the site's photo slots

Fills the fixed image slots on [index.html](../../../index.html) and
[about.html](../../../about.html) with photos picked from the
**media@oregoneden.com** Google Photos library.

> This is **not** the gallery page. For the Google Photos album cards on
> `gallery.html`, use the `update-gallery` skill instead.

## Slots

| Slot | Aspect | Size | Where it appears |
| --- | --- | --- | --- |
| `hero` | 16:9 | 2000×1125 | Home page hero background |
| `about` | 4:3 | 1200×900 | About section photo |
| `mission-1` … `mission-3` | 16:9 | 900×506 | Mission cards |
| `gallery-1` | 16:9 | 1200×675 | Home photo grid, wide tile |
| `gallery-2` … `gallery-5` | 1:1 | 700×700 | Home photo grid, square tiles |

Each slot is written as an optimised `.jpg` **and** `.webp` into
`assets/photos/`. Leftover photos land in `assets/photos/extras/`.

## Why a browser step is required

Google removed the broad Photos *Library* read scopes in March 2025 and does not
support service accounts, so an album cannot be listed unattended. The supported
path is the **Photos Picker API**: the user picks photos in a browser once, then
download, crop, optimise and staging are automatic.

If the user wants no browser step at all, they can export the photos (Google
Takeout or a shared-album download) and use the `optimize-photos` skill on that
folder instead.

## Procedure

### 1. Confirm what to replace

Ask which slots to update if the user was not specific. Replacing everything is
disruptive — prefer `--slots` for targeted changes.

### 2. Run the picker

```bash
cd "$(git rev-parse --show-toplevel)"
tools/photos/.venv/bin/python \
  .github/skills/update-site-photos/scripts/fetch_photos.py \
  --auth oauth-client --slots hero,about
```

Omit `--slots` to fill every slot. The script prints a picker URL and opens it;
tell the user to sign in as **media@oregoneden.com**, select the photos, and
confirm. It then polls until the selection is done.

**Always pass `--auth oauth-client`.** The default `adc` mode fails: Google
blocks gcloud's built-in OAuth client from the `photospicker` scope with a
`disabled_client` error. Credentials live in `tools/photos/credentials.json`
with a cached refresh token in `token.json` (both git-ignored).

Never run `gcloud` commands — the terminal blocks them as requiring sensitive
input. Do Cloud Console steps in the browser instead.

### 3. Verify

Confirm each requested slot wrote both variants:

```bash
ls -la assets/photos/*.jpg assets/photos/*.webp
```

Then serve the site (`python3 -m http.server 8000`) and check the affected pages
in the browser for correct framing — the crop is centred, so faces near an edge
can get cut. If a photo is framed badly, re-run for that one slot and pick a
different source photo.

### 4. Report

List which slots changed and their file sizes. Remind the user that the
originals in `tools/photos/downloads/` are deleted unless `--keep-downloads`
was passed.

## Useful options

| Flag | Purpose |
| --- | --- |
| `--slots hero,gallery-5` | Fill only these slots |
| `--source local --local-dir DIR` | Skip Google entirely, use a folder |
| `--keep-downloads` | Keep the raw originals |
| `--no-open` | Do not auto-open the picker URL |

## Notes

- Cropping and optimisation live in the `optimize-photos` skill's
  [process_images.py](../optimize-photos/scripts/process_images.py), which this
  script imports; slot definitions are edited there.
- HEIC (iPhone) input needs `pip install pillow-heif` in `tools/photos/.venv`.
- See [tools/photos/README.md](../../../tools/photos/README.md) for environment
  setup.
