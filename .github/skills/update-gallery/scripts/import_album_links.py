#!/usr/bin/env python3
"""Add album share links submitted through the gallery's Google Form.

Volunteers paste a Google Photos share link into a Google Form. Its response
sheet is published as CSV ("File → Share → Publish to web → CSV"), and this
script reads that CSV and adds any album that isn't in ``albums.txt`` yet.

The CSV URL comes from the ``ALBUM_FORM_CSV_URL`` environment variable (a
GitHub Actions secret), or ``--csv-file`` for local testing. When neither is
set the script does nothing, so the scheduled sync still works without a form.

Form input is untrusted: only Google Photos share links are accepted, short
``photos.app.goo.gl`` links are resolved to their full form, and every line
written to ``albums.txt`` is rebuilt from the validated album id and key.

Rules
-----
already processed (form_imported.txt)   -> ignored, so deleting a line sticks
not in albums.txt                       -> added to the new-albums section
active in albums.txt                    -> left alone
commented out as ``key 없음``           -> replaced with the keyed link
commented out for any other reason      -> left alone (it was hidden on purpose)

Every submitted album id is recorded in ``form_imported.txt``. The script
re-reads the whole response sheet on each run, so without that record an
album removed from ``albums.txt`` would be re-added the next day.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
ALBUMS_FILE = PROJECT_ROOT / "tools" / "photos" / "albums.txt"
IMPORTED_FILE = PROJECT_ROOT / "tools" / "photos" / "form_imported.txt"
IMPORTED_HEADER = (
    "# Album ids already taken from the gallery Google Form (one per line).\n"
    "# Written by import_album_links.py — remove a line to let that album be imported again.\n"
)

CSV_HOSTS = {"docs.google.com"}
SHORT_LINK_HOST = "photos.app.goo.gl"
USER_AGENT = "Mozilla/5.0 (compatible; EdenChurchSiteBot/1.0; +https://oregoneden.com)"
REQUEST_TIMEOUT = 30

CANDIDATE_RE = re.compile(
    r"https://(?:photos\.google\.com/(?:u/\d+/)?share/[^\s,\"'<>]+"
    r"|photos\.app\.goo\.gl/[A-Za-z0-9_-]+)"
)
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
SHARE_URL_RE = re.compile(r"https://photos\.google\.com/share/[^\s|]+")
NEW_SECTION = "# --- 새로 추가된 앨범 (원하는 위치로 옮기세요) ---"
UNSHARED_PREFIX = "# key 없음"


def album_id(url: str) -> str:
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def canonical_share_url(url: str) -> str | None:
    """Return ``https://photos.google.com/share/<id>?key=<key>`` or None."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "photos.google.com":
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "u":
        parts = parts[2:]
    if len(parts) != 2 or parts[0] != "share":
        return None
    key = (parse_qs(parsed.query).get("key") or [""])[0]
    if not (TOKEN_RE.match(parts[1]) and TOKEN_RE.match(key)):
        return None
    return f"https://photos.google.com/share/{parts[1]}?key={key}"


def resolve(session: requests.Session, url: str) -> str | None:
    """Turn a submitted link into a canonical share URL, following short links."""
    if urlparse(url).hostname != SHORT_LINK_HOST:
        return canonical_share_url(url)
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    except requests.RequestException:
        return None
    for hop in [*response.history, response]:
        location = hop.headers.get("Location") or ""
        for candidate in (location, hop.url):
            if canonical := canonical_share_url(candidate):
                return canonical
    return None


def read_csv(args: argparse.Namespace, session: requests.Session) -> str | None:
    if args.csv_file:
        return Path(args.csv_file).read_text(encoding="utf-8")

    url = os.environ.get("ALBUM_FORM_CSV_URL", "").strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in CSV_HOSTS:
        sys.exit("ERROR: ALBUM_FORM_CSV_URL must be a published Google Sheets CSV link.")
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def read_imported() -> set[str]:
    """Return album ids already processed on earlier runs."""
    if not IMPORTED_FILE.exists():
        return set()
    return {
        line.strip()
        for line in IMPORTED_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def submitted_links(text: str) -> list[str]:
    """Return every candidate link found in the CSV, in submission order."""
    links: list[str] = []
    for row in csv.reader(io.StringIO(text)):
        for cell in row:
            links.extend(m.group(0) for m in CANDIDATE_RE.finditer(cell))
    return links


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv-file", help="read responses from a local CSV instead")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    text = read_csv(args, session)
    if text is None:
        print("ALBUM_FORM_CSV_URL is not set — skipping form import.")
        return 0

    lines = ALBUMS_FILE.read_text(encoding="utf-8").splitlines()
    status: dict[str, tuple[int, str]] = {}
    for i, line in enumerate(lines):
        if match := SHARE_URL_RE.search(line):
            stripped = line.lstrip()
            state = (
                "active" if not stripped.startswith("#")
                else "unshared" if stripped.startswith(UNSHARED_PREFIX)
                else "hidden"
            )
            status.setdefault(album_id(match.group(0)), (i, state))

    added: list[str] = []
    activated: list[str] = []
    hidden: list[str] = []
    invalid = 0
    previously = 0
    seen: set[str] = set()
    imported = read_imported()
    newly_imported: list[str] = []

    for link in submitted_links(text):
        url = resolve(session, link)
        if not url:
            invalid += 1
            continue
        aid = album_id(url)
        if aid in seen:
            continue
        seen.add(aid)
        if aid in imported:
            previously += 1
            continue
        newly_imported.append(aid)

        index, state = status.get(aid, (-1, "new"))
        if state == "new":
            added.append(url)
        elif state == "unshared":
            lines[index] = url
            activated.append(url)
        elif state == "hidden":
            hidden.append(url)

    if added:
        stamp = f"# 폼으로 추가됨 {date.today().isoformat()}"
        block = [line for url in added for line in (stamp, url)]
        if NEW_SECTION in lines:
            at = lines.index(NEW_SECTION) + 1
            lines[at:at] = block
        else:
            at = next((i for i, l in enumerate(lines) if SHARE_URL_RE.search(l)), len(lines))
            lines[at:at] = [NEW_SECTION, *block, ""]

    if added or activated:
        ALBUMS_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    if newly_imported:
        existing = IMPORTED_FILE.read_text(encoding="utf-8") if IMPORTED_FILE.exists() else IMPORTED_HEADER
        IMPORTED_FILE.write_text(
            existing.rstrip("\n") + "\n" + "\n".join(newly_imported) + "\n", encoding="utf-8"
        )

    print(f"Form links checked: {len(seen) + invalid}")
    print(f"  added      : {len(added)}")
    print(f"  re-enabled : {len(activated)}")
    print(f"  hidden     : {len(hidden)} (commented out in {ALBUMS_FILE.name}; left alone)")
    print(f"  processed  : {previously} (handled on an earlier run)")
    print(f"  invalid    : {invalid} (not a public Google Photos album link)")
    for url in added + activated:
        print(f"  + {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
