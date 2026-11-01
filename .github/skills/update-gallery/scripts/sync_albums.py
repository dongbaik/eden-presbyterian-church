#!/usr/bin/env python3
"""Build the gallery's album cards from a list of Google Photos share links.

Why this exists
---------------
Google removed the broad Photos *Library* read scopes in March 2025:
``albums.list`` now only returns albums created by the calling app, and
``sharedAlbums.list`` was retired entirely. There is therefore no API that can
enumerate the albums of an ordinary Google Photos account.

A shared album's public page, however, still exposes everything the gallery
needs as OpenGraph metadata: ``og:title`` (album name), ``og:image`` (cover
photo) and ``og:url``. Since an album must be link-shared anyway for site
visitors to open it, reading those tags is a complete and stable substitute.

What it does
------------
For every link in ``albums.txt`` this script

  1. fetches the shared album page and reads its OpenGraph tags,
  2. splits the album name into a title and a date ("Name · Jul 14 - 21"),
  3. downloads the cover at high resolution and writes optimised
     ``.jpg`` + ``.webp`` files into ``assets/photos/albums/``,
  4. writes ``assets/photos/albums/albums.json`` for reference, and
  5. rewrites the block between the ``ALBUMS:START``/``ALBUMS:END`` markers in
     ``gallery.html`` with the generated cards.

Usage, from the repository root::

    tools/photos/.venv/bin/python .github/skills/update-gallery/scripts/sync_albums.py
    tools/photos/.venv/bin/python .github/skills/update-gallery/scripts/sync_albums.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date as calendar_date
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageChops, ImageEnhance, ImageStat

# process_images.py belongs to the sibling optimize-photos skill.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "optimize-photos" / "scripts")
)
from process_images import JPEG_QUALITY, WEBP_QUALITY, crop_to_aspect  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]

ALBUMS_FILE = PROJECT_ROOT / "tools" / "photos" / "albums.txt"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "photos" / "albums"
DATA_FILE = OUTPUT_DIR / "albums.json"
GALLERY_HTML = PROJECT_ROOT / "gallery.html"

START_MARKER = "<!-- ALBUMS:START -->"
END_MARKER = "<!-- ALBUMS:END -->"

# Only these hosts are ever contacted, so a stray line in albums.txt cannot
# make the script fetch an arbitrary internal URL.
ALLOWED_ALBUM_HOSTS = {"photos.google.com", "photos.app.goo.gl"}
ALLOWED_IMAGE_HOSTS_SUFFIX = ".googleusercontent.com"

# Google serves this URL at any size; "-p-k" applies its subject-aware crop.
COVER_REQUEST_SIZE = "w1600-h900-p-k"
COVER_OUTPUT_SIZE = (1200, 675)  # 16:9 card image written to the site
COVER_ASPECT = (16, 9)

# Google re-encodes the same cover slightly differently on every request.
# Keep the existing files unless the picture visibly changed (mean per-channel
# difference of small thumbnails, 0-255), so scheduled runs don't rewrite
# every cover. Re-encodes measure under 1; a different photo measures 20+.
COVER_CHANGE_THRESHOLD = 4.0

# A crawler-style UA is what makes Google return the OpenGraph tags.
USER_AGENT = "Mozilla/5.0 (compatible; EdenChurchSiteBot/1.0; +https://oregoneden.com)"
REQUEST_TIMEOUT = 30


# --------------------------------------------------------------------------- #
# albums.txt
# --------------------------------------------------------------------------- #
@dataclass
class AlbumInput:
    url: str
    title_override: str | None = None
    date_override: str | None = None


def read_album_inputs(path: Path) -> list[AlbumInput]:
    """Parse ``albums.txt`` into album entries, ignoring blanks and comments."""
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Add your album share links there first.")

    entries: list[AlbumInput] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("|")]
        url = parts[0]
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_ALBUM_HOSTS:
            sys.exit(
                f"ERROR: {path.name} line {lineno}: expected an https link to "
                f"{' or '.join(sorted(ALLOWED_ALBUM_HOSTS))}, got:\n  {url}"
            )

        entries.append(
            AlbumInput(
                url=url,
                title_override=parts[1] if len(parts) > 1 and parts[1] else None,
                date_override=parts[2] if len(parts) > 2 and parts[2] else None,
            )
        )

    if not entries:
        sys.exit(f"ERROR: no album links found in {path}.")
    return entries


# --------------------------------------------------------------------------- #
# OpenGraph scraping
# --------------------------------------------------------------------------- #
class _OpenGraphParser(HTMLParser):
    """Collect ``<meta property="og:*">`` values from a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr = dict(attrs)
        prop = attr.get("property") or ""
        if prop.startswith("og:") and attr.get("content"):
            self.tags.setdefault(prop, attr["content"])


def fetch_open_graph(session: requests.Session, url: str) -> dict[str, str]:
    """Return the OpenGraph tags of the shared-album page at *url*."""
    response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    parser = _OpenGraphParser()
    parser.feed(response.text)
    return parser.tags


# --------------------------------------------------------------------------- #
# Title / slug helpers
# --------------------------------------------------------------------------- #
_SEPARATOR = re.compile(r"\s*[·•]\s*")
_TRAILING_DECORATION = re.compile(r"^[^\w(\[]+|[^\w)\]]+$")


def _tidy(text: str) -> str:
    """Trim whitespace and decorative symbols (emoji) from both ends."""
    return _TRAILING_DECORATION.sub("", text.strip())


def split_title(album_name: str) -> tuple[str, str]:
    """Split an album name like ``"Retreat · Jul 14 - 21"`` into title + date."""
    parts = _SEPARATOR.split(album_name.strip())
    if len(parts) >= 2:
        return _tidy(parts[0]), _tidy(" · ".join(parts[1:]))
    return _tidy(album_name), ""


def slugify(title: str, fallback: str) -> str:
    """Return a filesystem/URL-safe ASCII slug, falling back for non-Latin text."""
    ascii_form = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_form.lower()).strip("-")
    return slug or fallback


def album_id_of(url: str) -> str:
    """Return the stable album identifier from a share URL."""
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def unique_slug(title: str, url: str, taken: set[str]) -> str:
    """Return a slug for *title* that is guaranteed not to collide.

    Korean album names transliterate to nothing, so several albums would
    otherwise collapse to the same slug (e.g. every ``2024 …`` album becoming
    ``2024``) and overwrite each other's cover files. A short digest of the
    album's share id disambiguates those, and stays stable between runs.
    """
    digest = hashlib.sha1(album_id_of(url).encode("utf-8")).hexdigest()[:6]

    base = slugify(title, fallback="")
    if not base or base.isdigit() or base in taken:
        base = f"{base}-{digest}" if base else f"album-{digest}"
    return base


def prune_stale_covers(keep: set[str]) -> int:
    """Delete cover files in the output folder that no album refers to."""
    if not OUTPUT_DIR.exists():
        return 0
    removed = 0
    for path in OUTPUT_DIR.iterdir():
        if path.suffix in {".jpg", ".webp"} and path.stem not in keep:
            path.unlink()
            removed += 1
    return removed


# --------------------------------------------------------------------------- #
# Cover image
# --------------------------------------------------------------------------- #
def upgrade_cover_url(url: str) -> str:
    """Swap Google's small preview size parameter for a high-resolution one."""
    base = url.rsplit("=", 1)[0] if "=" in url.rsplit("/", 1)[-1] else url
    return f"{base}={COVER_REQUEST_SIZE}"


def _same_picture(path: Path, img: Image.Image) -> bool:
    """True if the cover already at *path* looks the same as *img*."""
    try:
        with Image.open(path) as existing:
            existing = existing.convert("RGB")
            if existing.size != img.size:
                return False
            # Compare small thumbnails so JPEG noise in busy photos is averaged out.
            thumb = (160, 90)
            diff = ImageStat.Stat(
                ImageChops.difference(existing.resize(thumb, Image.BOX), img.resize(thumb, Image.BOX))
            )
            return max(diff.mean) <= COVER_CHANGE_THRESHOLD
    except (OSError, ValueError):
        return False


def save_cover(session: requests.Session, cover_url: str, slug: str) -> bool:
    """Download the cover and write optimised ``.jpg`` + ``.webp`` variants.

    Returns False when the existing files already show the same picture and
    were left untouched.
    """
    host = urlparse(cover_url).hostname or ""
    if not host.endswith(ALLOWED_IMAGE_HOSTS_SUFFIX):
        raise ValueError(f"unexpected cover host: {host}")

    response = session.get(upgrade_cover_url(cover_url), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content))
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = crop_to_aspect(img, COVER_ASPECT).resize(COVER_OUTPUT_SIZE, Image.LANCZOS)
    img = ImageEnhance.Sharpness(img).enhance(1.06)

    jpg_path = OUTPUT_DIR / f"{slug}.jpg"
    webp_path = OUTPUT_DIR / f"{slug}.webp"
    if webp_path.exists() and _same_picture(jpg_path, img):
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(jpg_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    img.save(webp_path, "WEBP", quality=WEBP_QUALITY, method=6)
    return True


# --------------------------------------------------------------------------- #
# HTML generation
# --------------------------------------------------------------------------- #
@dataclass
class Album:
    slug: str
    title: str
    date: str
    url: str
    cover_jpg: str
    cover_webp: str


_MONTHS = {
    month: index
    for index, month in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        1,
    )
}
_MONTH_DAY = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")[a-z]*\s+(\d{1,2})(?:,\s*(\d{4}))?",
    re.IGNORECASE,
)
_SHORT_RANGE_END = re.compile(r"[–-]\s*(\d{1,2})(?:,\s*(\d{4}))?\s*$")
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def album_sort_date(album: Album) -> calendar_date:
    """Return the album's best event date for newest-first ordering."""
    matches = list(_MONTH_DAY.finditer(album.date))
    if not matches:
        return calendar_date.min

    last = matches[-1]
    month = _MONTHS[last.group(1).title()[:3]]
    day = int(last.group(2))
    short_end = _SHORT_RANGE_END.search(album.date)
    if short_end:
        day = int(short_end.group(1))

    title_years = _YEAR.findall(album.title)
    date_years = _YEAR.findall(album.date)
    year = int((title_years or date_years or [str(calendar_date.today().year)])[-1])
    return calendar_date(year, month, day)


def render_cards(albums: list[Album]) -> str:
    """Return the markup for the album grid, ready to sit between the markers."""
    cards = []
    for album in albums:
        title = html.escape(album.title)
        date = html.escape(album.date)
        date_markup = (
            f'\n              <span class="album-card__date">{date}</span>' if date else ""
        )
        cards.append(f"""\
          <a class="album-card" href="{html.escape(album.url)}" target="_blank" rel="noopener">
            <span class="album-card__media">
              <picture>
                <source srcset="{album.cover_webp}" type="image/webp" />
                <img src="{album.cover_jpg}" alt="{title} 앨범 커버" loading="lazy" width="1200" height="675" />
              </picture>
            </span>
            <span class="album-card__body">
              <span class="album-card__title">{title}</span>{date_markup}
            </span>
          </a>""")

    return (
        '        <div class="album-grid">\n'
        + "\n".join(cards)
        + "\n        </div>"
    )


def update_gallery(markup: str) -> None:
    """Replace the marked block in ``gallery.html`` with *markup*."""
    source = GALLERY_HTML.read_text(encoding="utf-8")
    start = source.find(START_MARKER)
    end = source.find(END_MARKER)
    if start == -1 or end == -1:
        sys.exit(
            f"ERROR: {GALLERY_HTML.name} is missing the {START_MARKER} / "
            f"{END_MARKER} markers."
        )

    updated = (
        source[: start + len(START_MARKER)]
        + "\n"
        + markup
        + "\n        "
        + source[end:]
    )
    GALLERY_HTML.write_text(updated, encoding="utf-8")


def load_previous_albums() -> dict[str, Album]:
    """Return the last successful sync's albums, keyed by album id."""
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return {album_id_of(a["url"]): Album(**a) for a in data}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def _is_permanent_failure(exc: requests.RequestException) -> bool:
    """True for 4xx responses (other than rate limiting) — the album is gone."""
    response = getattr(exc, "response", None)
    return response is not None and 400 <= response.status_code < 500 and response.status_code != 429


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be collected without writing any files",
    )
    args = parser.parse_args()

    entries = read_album_inputs(ALBUMS_FILE)
    print(f"Reading {len(entries)} album link(s) from {ALBUMS_FILE.name}\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    previous = load_previous_albums()
    albums: list[Album] = []
    used_slugs: set[str] = set()
    kept: list[str] = []
    dropped: list[str] = []
    rewritten = 0

    def keep_previous(index: int, entry: AlbumInput, reason: str) -> None:
        """Fall back to the last good card so a hiccup doesn't drop an album."""
        prev = previous.get(album_id_of(entry.url))
        if (
            prev
            and prev.slug not in used_slugs
            and (PROJECT_ROOT / prev.cover_jpg).exists()
            and (PROJECT_ROOT / prev.cover_webp).exists()
        ):
            used_slugs.add(prev.slug)
            albums.append(prev)
            kept.append(prev.title)
            print(f"  ~ [{index}] {reason}; kept the previous card for '{prev.title}'")
        else:
            dropped.append(entry.url)
            print(f"  ! [{index}] {reason}; skipped\n      {entry.url}")

    for index, entry in enumerate(entries, 1):
        try:
            tags = fetch_open_graph(session, entry.url)
        except requests.RequestException as exc:
            if _is_permanent_failure(exc):
                dropped.append(entry.url)
                print(f"  ! [{index}] album page is gone ({exc}); skipped\n      {entry.url}")
            else:
                keep_previous(index, entry, f"could not load album page ({exc})")
            continue

        album_name = tags.get("og:title", "")
        cover_url = tags.get("og:image", "")
        if not album_name or not cover_url:
            dropped.append(entry.url)
            print(
                f"  ! [{index}] no album metadata found — is link sharing still on?\n"
                f"      {entry.url}"
            )
            continue

        auto_title, auto_date = split_title(album_name)
        title = entry.title_override or auto_title
        date = entry.date_override if entry.date_override is not None else auto_date
        slug = unique_slug(title, entry.url, used_slugs)

        album = Album(
            slug=slug,
            title=title,
            date=date,
            url=tags.get("og:url") or entry.url,
            cover_jpg=f"assets/photos/albums/{slug}.jpg",
            cover_webp=f"assets/photos/albums/{slug}.webp",
        )

        if not args.dry_run:
            try:
                rewritten += save_cover(session, cover_url, slug)
            except (requests.RequestException, ValueError, OSError) as exc:
                keep_previous(index, entry, f"cover download failed for '{title}' ({exc})")
                continue

        used_slugs.add(slug)
        albums.append(album)
        print(f"  \u2713 [{index}] {title}" + (f"  ({date})" if date else ""))

    if not albums:
        sys.exit("\nERROR: no albums could be collected — nothing was written.")

    # A burst of failures usually means Google blocked or changed the page,
    # not that the albums were deleted. Refuse to strip the gallery.
    if len(dropped) > max(2, len(entries) // 4):
        sys.exit(
            f"\nERROR: {len(dropped)} of {len(entries)} album(s) could not be read — "
            "refusing to rewrite the gallery. Check the links above and retry."
        )

    albums.sort(key=album_sort_date, reverse=True)

    if args.dry_run:
        print(f"\nDry run: {len(albums)} album(s) resolved, no files written.")
        return 0

    if kept:
        print(f"\nKept the previous card for {len(kept)} album(s) that failed to refresh")
    print(f"Updated {rewritten} cover image(s); the rest were unchanged")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps([asdict(a) for a in albums], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    update_gallery(render_cards(albums))

    stale = prune_stale_covers({a.slug for a in albums})
    if stale:
        print(f"Removed {stale} unused cover file(s)")

    print(f"\nWrote {len(albums)} album card(s) to {GALLERY_HTML.name}")
    print(f"Covers staged in {OUTPUT_DIR.relative_to(PROJECT_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
