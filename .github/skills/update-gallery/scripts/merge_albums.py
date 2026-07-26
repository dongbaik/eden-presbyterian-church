#!/usr/bin/env python3
"""Merge scraped Google Photos album links into ``tools/photos/albums.txt``.

Reads the JSON produced by [collect-albums.js](./collect-albums.js) on stdin::

    [{"url": "https://photos.google.com/share/AF1Qip...?key=...", "title": "..."}]

and updates ``albums.txt`` in place, preserving everything the user has
customised: the header, the year grouping comments, the line order and any
``| title | date`` overrides.

Rules
-----
new album        -> added at the top of the list
existing album   -> URL refreshed in place (share keys change when re-shared)
no ``key=``      -> commented out; such links only work for the album's owner
gone from Photos -> commented out and reported, never deleted outright

Nothing is removed from the file, so a mis-scrape can always be undone by hand.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
ALBUMS_FILE = PROJECT_ROOT / "tools" / "photos" / "albums.txt"

SHARE_URL_RE = re.compile(r"https://photos\.google\.com/share/[^\s|]+")


def album_id(url: str) -> str:
    """Return the stable album identifier from a share URL."""
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def has_key(url: str) -> bool:
    """True if the share URL carries the access key anonymous visitors need."""
    return bool(parse_qs(urlparse(url).query).get("key"))


def overrides_of(line: str) -> str:
    """Return the ``| title | date`` suffix of a line, if any."""
    _, sep, rest = line.partition("|")
    return f" |{rest}" if sep else ""


def main() -> int:
    try:
        scraped = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: stdin was not valid JSON: {exc}")

    if not isinstance(scraped, list) or not scraped:
        sys.exit("ERROR: expected a non-empty JSON array of {url, title} objects.")

    by_id = {album_id(a["url"]): a for a in scraped if a.get("url")}
    if not by_id:
        sys.exit("ERROR: no album share URLs found in the input.")

    lines = ALBUMS_FILE.read_text(encoding="utf-8").splitlines()
    first_url = next(
        (i for i, l in enumerate(lines) if SHARE_URL_RE.search(l)), len(lines)
    )
    header, body = lines[:first_url], lines[first_url:]

    seen: set[str] = set()
    merged: list[str] = []
    refreshed: list[str] = []
    unshared: list[str] = []
    stale: list[str] = []

    for line in body:
        match = SHARE_URL_RE.search(line)
        if not match:
            merged.append(line)
            continue

        aid = album_id(match.group(0))
        seen.add(aid)
        entry = by_id.get(aid)
        was_active = not line.lstrip().startswith("#")

        if entry is None:
            # Album is no longer on the Photos page (deleted or unshared).
            if was_active:
                stale.append(match.group(0))
                merged.append(f"# 구글 포토 목록에 없음: {line.strip()}")
            else:
                merged.append(line)
            continue

        url = entry["url"]
        if not has_key(url):
            unshared.append(entry.get("title") or aid)
            merged.append(f"# key 없음(소유자 전용): {url}")
            continue

        new_line = f"{url}{overrides_of(line)}"
        if was_active and match.group(0) != url:
            refreshed.append(entry.get("title") or aid)
        merged.append(new_line)

    new_entries = [(aid, a) for aid, a in by_id.items() if aid not in seen]
    additions: list[str] = []
    for aid, entry in new_entries:
        title = entry.get("title") or "(제목은 sync_albums.py 가 채웁니다)"
        if has_key(entry["url"]):
            additions.extend([f"# {title}", entry["url"]])
        else:
            unshared.append(title)
            additions.extend([f"# {title}", f"# key 없음(소유자 전용): {entry['url']}"])

    if additions:
        additions = ["# --- 새로 추가된 앨범 (원하는 위치로 옮기세요) ---", *additions, ""]

    ALBUMS_FILE.write_text(
        "\n".join([*header, *additions, *merged]).rstrip() + "\n", encoding="utf-8"
    )

    active = sum(
        1 for l in merged + additions
        if SHARE_URL_RE.search(l) and not l.lstrip().startswith("#")
    )
    print(f"Scanned {len(by_id)} album(s) on the Photos page")
    print(f"  new        : {len(new_entries)}")
    print(f"  refreshed  : {len(refreshed)}")
    print(f"  not shared : {len(unshared)}")
    print(f"  missing    : {len(stale)}")
    print(f"  -> {active} active link(s) in {ALBUMS_FILE.name}")

    for title in unshared:
        print(f"  ! 공유 링크에 key 가 없어 제외됨: {title}")
    for url in stale:
        print(f"  ! 구글 포토 목록에서 사라져 주석 처리됨: {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
