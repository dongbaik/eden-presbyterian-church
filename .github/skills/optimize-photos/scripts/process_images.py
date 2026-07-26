"""Crop, resize and optimise source photos into the website's image slots.

Given a list of source image paths, each detected slot on the site (hero,
About photo, three mission cards, gallery tiles) is filled by centre-cropping
a source image to the slot's aspect ratio, resizing it, applying a light sharpen
and saving optimised ``.jpg`` + ``.webp`` files into ``assets/photos/``.

This module is import-safe (no side effects) and can also be run directly to
process a folder of images without touching Google APIs::

    python process_images.py <source-dir> [<output-dir>]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

# Optional HEIC/HEIF support (iPhone photos). Enabled automatically if the
# `pillow-heif` package is installed; otherwise HEIC files are skipped.
try:  # pragma: no cover - depends on optional dependency
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Slot:
    """A single image slot on the website."""

    name: str
    aspect: tuple[int, int]
    size: tuple[int, int]
    prefer_landscape: bool = True


# Slots detected in the site markup (index.html / about.html).
SLOTS: list[Slot] = [
    Slot("hero", (16, 9), (2000, 1125)),          # full-width hero background
    Slot("about", (4, 3), (1200, 900)),           # About section .photo-ph--4x3
    Slot("mission-1", (16, 9), (900, 506)),       # Domestic mission card
    Slot("mission-2", (16, 9), (900, 506)),       # Global mission card
    Slot("mission-3", (16, 9), (900, 506)),       # Relief mission card
    Slot("gallery-1", (16, 9), (1200, 675)),      # gallery span-2 wide tile
    Slot("gallery-2", (1, 1), (700, 700), prefer_landscape=False),
    Slot("gallery-3", (1, 1), (700, 700), prefer_landscape=False),
    Slot("gallery-4", (1, 1), (700, 700), prefer_landscape=False),
    Slot("gallery-5", (1, 1), (700, 700), prefer_landscape=False),
]

SLOTS_BY_NAME: dict[str, Slot] = {s.name: s for s in SLOTS}

JPEG_QUALITY = 82
WEBP_QUALITY = 80
EXTRA_MAX_EDGE = 2000  # leftover photos are kept at this max dimension

SUPPORTED_INPUT = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".tif", ".tiff", ".bmp", ".heic", ".heif",
}


def gather_sources(source_dir: Path) -> list[Path]:
    """Return supported image files in *source_dir*, sorted by name."""
    files = [
        p
        for p in sorted(source_dir.iterdir())
        if p.is_file() and p.suffix.lower() in SUPPORTED_INPUT
    ]
    return files


def load_image(path: Path) -> Image.Image:
    """Open *path*, honour EXIF orientation and return an RGB image."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # rotate per camera orientation
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    return img


def crop_to_aspect(img: Image.Image, aspect: tuple[int, int]) -> Image.Image:
    """Centre-crop *img* to the given aspect ratio without distortion."""
    aw, ah = aspect
    target = aw / ah
    w, h = img.size
    current = w / h
    if current > target:  # too wide -> trim the sides
        new_w = round(h * target)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:  # too tall -> trim top/bottom
        new_h = round(w / target)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    return img.crop(box)


def _save_variants(img: Image.Image, out_dir: Path, name: str) -> list[Path]:
    """Save *img* as optimised .jpg and .webp; return written paths."""
    jpg_path = out_dir / f"{name}.jpg"
    webp_path = out_dir / f"{name}.webp"
    img.save(jpg_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    img.save(webp_path, "WEBP", quality=WEBP_QUALITY, method=6)
    return [jpg_path, webp_path]


def process_to_slot(src: Image.Image, slot: Slot, out_dir: Path) -> list[Path]:
    """Crop/resize/sharpen *src* for *slot* and write the output files."""
    cropped = crop_to_aspect(src, slot.aspect)
    resized = cropped.resize(slot.size, Image.LANCZOS)
    resized = ImageEnhance.Sharpness(resized).enhance(1.06)  # gentle post-resize sharpen
    return _save_variants(resized, out_dir, slot.name)


def _save_extra(src: Image.Image, out_dir: Path, index: int) -> Path:
    """Save a leftover photo downscaled to EXTRA_MAX_EDGE as an optimised JPEG."""
    img = src.copy()
    img.thumbnail((EXTRA_MAX_EDGE, EXTRA_MAX_EDGE), Image.LANCZOS)
    path = out_dir / f"extra-{index:02d}.jpg"
    img.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return path


@dataclass
class _Source:
    path: Path
    img: Image.Image
    used: bool = False

    @property
    def is_landscape(self) -> bool:
        return self.img.width >= self.img.height


def process(
    sources: list[Path],
    out_dir: Path,
    slots: list[Slot] | None = None,
) -> list[tuple[str, str]]:
    """Fill the requested slots from *sources* and stage results in *out_dir*.

    *slots* defaults to every slot on the site. Returns a list of
    ``(slot_name, source_filename)`` assignments.
    """
    target_slots = slots if slots is not None else SLOTS
    out_dir.mkdir(parents=True, exist_ok=True)

    loaded: list[_Source] = []
    for path in sources:
        try:
            loaded.append(_Source(path, load_image(path)))
        except Exception as exc:  # skip unreadable / unsupported files
            print(f"  ! skipping {path.name}: {exc}")

    if not loaded:
        print("  ! no readable images to process")
        return []

    def take(prefer_landscape: bool) -> _Source | None:
        # Prefer the requested orientation, then fall back to any unused image.
        orders = (
            [s for s in loaded if s.is_landscape == prefer_landscape],
            loaded,
        )
        for group in orders:
            for s in group:
                if not s.used:
                    s.used = True
                    return s
        return None

    assignments: list[tuple[str, str]] = []
    for slot in target_slots:
        chosen = take(slot.prefer_landscape)
        if chosen is None:
            print(f"  ! not enough photos for slot '{slot.name}'")
            continue
        process_to_slot(chosen.img, slot, out_dir)
        assignments.append((slot.name, chosen.path.name))
        print(f"  \u2713 {slot.name:<10} <- {chosen.path.name}")

    # Preserve any leftover photos as optimised extras (full runs only).
    if slots is None:
        extras_dir = out_dir / "extras"
        extra_index = 0
        for s in loaded:
            if s.used:
                continue
            if extra_index == 0:
                extras_dir.mkdir(parents=True, exist_ok=True)
            extra_index += 1
            _save_extra(s.img, extras_dir, extra_index)
        if extra_index:
            print(f"  \u2713 {extra_index} leftover photo(s) saved to {extras_dir}")

    return assignments


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    source_dir = Path(argv[0]).expanduser().resolve()
    out_dir = (
        Path(argv[1]).expanduser().resolve()
        if len(argv) > 1
        else Path(__file__).resolve().parents[2] / "assets" / "photos"
    )
    if not source_dir.is_dir():
        print(f"ERROR: not a directory: {source_dir}")
        return 1
    sources = gather_sources(source_dir)
    if not sources:
        print(f"ERROR: no supported images found in {source_dir}")
        return 1
    print(f"Processing {len(sources)} photo(s) -> {out_dir}")
    process(sources, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
