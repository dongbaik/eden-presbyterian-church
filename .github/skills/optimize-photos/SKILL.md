---
name: optimize-photos
description: 'Crop, resize and optimise a local folder of photos into the church website''s image slots as .jpg + .webp. Use when the user says "optimize photos", "사진 최적화", "이 사진들 넣어줘", "사진 크기 줄여줘", "process these images", points at a folder of photos (Downloads, Takeout export, shared-album download, iPhone photos), or wants to add photos without going through Google Photos. Also covers changing slot sizes and aspect ratios.'
argument-hint: '[path to a folder of photos]'
---

# Optimise photos into the site's image slots

Turns a folder of source photos into web-ready images for the church site — no
Google account or network access involved.

Each output is centre-cropped to its slot's aspect ratio, resized, lightly
sharpened, and written as an optimised `.jpg` **and** `.webp`.

## When to use which skill

| Need | Skill |
| --- | --- |
| Photos already on disk | **this skill** |
| Pick photos from Google Photos | `update-site-photos` |
| Google Photos album cards on gallery.html | `update-gallery` |

## Procedure

### 1. Locate the source folder

Ask the user for the folder if they did not give one. Supported inputs:
`.jpg .jpeg .png .webp .gif .tif .tiff .bmp .heic .heif`.

HEIC (iPhone) files are skipped unless `pillow-heif` is installed:

```bash
tools/photos/.venv/bin/pip install pillow-heif
```

### 2. Run it

```bash
cd "$(git rev-parse --show-toplevel)"
tools/photos/.venv/bin/python \
  .github/skills/optimize-photos/scripts/process_images.py \
  ~/Downloads/church-photos assets/photos
```

The second argument is the output folder and defaults to `assets/photos`.

Photos are assigned to slots in filename order, preferring landscape shots for
landscape slots. Anything left over is downscaled into `<output>/extras/`.

To fill only some slots, use the sibling script instead, which accepts
`--slots`:

```bash
tools/photos/.venv/bin/python \
  .github/skills/update-site-photos/scripts/fetch_photos.py \
  --source local --local-dir ~/Downloads/church-photos --slots hero,about
```

### 3. Verify

Check that both variants exist for each slot, then serve the site
(`python3 -m http.server 8000`) and inspect the affected pages. The crop is
centred, so confirm nothing important is cut off; if it is, re-run that slot
with a better-framed source photo.

### 4. Report

List which slots were filled, from which source files, and note any photo that
was skipped as unreadable or unsupported.

## Slots

Defined in [process_images.py](./scripts/process_images.py) as the `SLOTS` list:

| Slot | Aspect | Size |
| --- | --- | --- |
| `hero` | 16:9 | 2000×1125 |
| `about` | 4:3 | 1200×900 |
| `mission-1` … `mission-6` | 16:9 | 900×506 |
| `gallery-1` | 16:9 | 1200×675 |
| `gallery-2` … `gallery-5` | 1:1 | 700×700 |

To add or resize a slot, edit that list — then update the matching `<img>` and
`<source>` tags in the HTML so the new file is actually used.

Quality settings also live there: `JPEG_QUALITY = 82`, `WEBP_QUALITY = 80`,
`EXTRA_MAX_EDGE = 2000`.

## Notes

- This module is imported by the `update-site-photos` and `update-gallery`
  skills. Changing function signatures affects both — re-run their verification
  steps after editing.
- EXIF orientation is honoured, so rotated phone photos come out upright.
- Album **cover** images on gallery.html are produced by `update-gallery`, not
  by these slots.
