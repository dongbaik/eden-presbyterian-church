#!/usr/bin/env python3
"""Fetch photos from the media@oregoneden.com Google Photos album and stage
them into the website's image slots.

Google removed the broad Google Photos *Library* read scopes in March 2025, so
an existing album's contents can no longer be listed with a simple read-only
token, and service accounts are not supported for Google Photos. This tool uses
the **Google Photos Picker API**: you authorise once (a refresh token is cached
so there is no repeated login) and select the album's photos in a browser a
single time; downloading, cropping, optimising and staging then happen
automatically.

Modes
-----
picker (default)
    Authorise as media@oregoneden.com, open the picker, select the album's
    photos, then download + process them.

local
    Skip Google entirely and process an already-exported folder of images
    (e.g. from Google Takeout / a shared-album download). Fully unattended::

        python fetch_photos.py --source local --local-dir ~/Downloads/eden-album

See README.md for the one-time Google Cloud setup.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import webbrowser
from pathlib import Path

import requests

import process_images

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

CREDENTIALS_FILE = HERE / "credentials.json"
TOKEN_FILE = HERE / "token.json"
DOWNLOAD_DIR = HERE / "downloads"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "photos"

SCOPES = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
PICKER_API = "https://photospicker.googleapis.com/v1"

REQUEST_TIMEOUT = 60  # seconds per HTTP request
SELECTION_TIMEOUT = 600  # seconds to wait for the user to pick photos

ADC_LOGIN_HINT = (
    "Authorise gcloud Application Default Credentials once (opens a browser —\n"
    "sign in as media@oregoneden.com):\n\n"
    "  gcloud auth application-default login \\\n"
    "      --scopes=openid,https://www.googleapis.com/auth/cloud-platform,"
    "https://www.googleapis.com/auth/photospicker.mediaitems.readonly\n\n"
    "Then re-run this script with the project that has the Photos Picker API\n"
    "enabled, e.g.:  python fetch_photos.py --project YOUR_PROJECT_ID\n"
    "(or set the GOOGLE_CLOUD_PROJECT environment variable)."
)


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
def get_credentials(auth_method: str):
    """Return valid Google credentials.

    ``adc`` (default) uses gcloud Application Default Credentials created by
    ``gcloud auth application-default login``. ``oauth-client`` runs a one-time
    consent flow with a Desktop OAuth client (credentials.json) and caches a
    refresh token in token.json.
    """
    from google.auth.transport.requests import Request

    if auth_method == "adc":
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError, RefreshError

        try:
            creds, _ = google.auth.default(scopes=SCOPES)
        except DefaultCredentialsError:
            sys.exit("ERROR: No Application Default Credentials found.\n\n" + ADC_LOGIN_HINT)
        try:
            creds.refresh(Request())
        except RefreshError:
            sys.exit(
                "ERROR: Could not refresh Application Default Credentials.\n\n" + ADC_LOGIN_HINT
            )
        return creds

    # auth_method == "oauth-client"
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                sys.exit(
                    "ERROR: credentials.json not found.\n"
                    f"       Expected at: {CREDENTIALS_FILE}\n"
                    "       Create an OAuth 2.0 Desktop client and download it — see README.md."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message=(
                    "Opening your browser to sign in as media@oregoneden.com …\n"
                    "If it does not open automatically, visit:\n    {url}"
                ),
            )
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def _headers(creds, project: str | None) -> dict[str, str]:
    """Build request headers, refreshing the access token if it has expired."""
    from google.auth.transport.requests import Request

    if not creds.valid:
        creds.refresh(Request())
    headers = {"Authorization": f"Bearer {creds.token}"}
    # gcloud ADC uses a shared client, so requests must be attributed to a
    # project that has the Photos Picker API enabled (quota project).
    quota_project = project or getattr(creds, "quota_project_id", None)
    if quota_project:
        headers["X-Goog-User-Project"] = quota_project
    return headers


# --------------------------------------------------------------------------- #
# Picker API
# --------------------------------------------------------------------------- #
def _parse_duration(value: str | None) -> float | None:
    """Parse a protobuf duration string such as '3s' or '1.500s'."""
    if not value:
        return None
    try:
        return float(value.rstrip("s"))
    except ValueError:
        return None


def create_session(creds, project: str | None) -> dict:
    resp = requests.post(
        f"{PICKER_API}/sessions",
        headers=_headers(creds, project),
        json={},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def wait_for_selection(creds, project: str | None, session: dict) -> dict:
    """Poll the session until the user has finished picking photos."""
    session_id = session["id"]
    interval = _parse_duration(session.get("pollingConfig", {}).get("pollInterval")) or 3.0
    deadline = time.time() + SELECTION_TIMEOUT

    print("\nWaiting for you to select photos in the browser …")
    while time.time() < deadline:
        resp = requests.get(
            f"{PICKER_API}/sessions/{session_id}",
            headers=_headers(creds, project),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        state = resp.json()
        if state.get("mediaItemsSet"):
            return state
        interval = (
            _parse_duration(state.get("pollingConfig", {}).get("pollInterval")) or interval
        )
        time.sleep(interval)

    raise TimeoutError(
        "Timed out waiting for a photo selection. Re-run and finish selecting sooner."
    )


def list_media_items(creds, project: str | None, session_id: str) -> list[dict]:
    """Return every media item the user picked in the session."""
    items: list[dict] = []
    page_token: str | None = None
    while True:
        params: dict[str, object] = {"sessionId": session_id, "pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(
            f"{PICKER_API}/mediaItems",
            headers=_headers(creds, project),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("mediaItems", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def _is_photo(item: dict) -> bool:
    if item.get("type") == "PHOTO":
        return True
    mime = item.get("mediaFile", {}).get("mimeType", "")
    return mime.startswith("image/")


def download_item(creds, project: str | None, item: dict, dest_dir: Path) -> Path | None:
    """Download the full-resolution bytes of a picked photo."""
    media_file = item.get("mediaFile", {})
    base_url = media_file.get("baseUrl")
    if not base_url:
        return None
    filename = media_file.get("filename") or f"{item.get('id', 'photo')}.jpg"
    dest = dest_dir / filename
    # '=d' asks the Picker API for the original, unscaled bytes.
    resp = requests.get(
        f"{base_url}=d",
        headers=_headers(creds, project),
        stream=True,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            fh.write(chunk)
    return dest


def delete_session(creds, project: str | None, session_id: str) -> None:
    try:
        requests.delete(
            f"{PICKER_API}/sessions/{session_id}",
            headers=_headers(creds, project),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        pass  # best-effort cleanup


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_picker(open_browser: bool, auth_method: str, project: str | None) -> list[Path]:
    creds = get_credentials(auth_method)

    session = create_session(creds, project)
    picker_uri = session.get("pickerUri")
    session_id = session["id"]
    print("\n" + "=" * 68)
    print("Open this URL, sign in as media@oregoneden.com, then open the album")
    print("and select the photos you want (Ctrl/Cmd-click for multiple):\n")
    print(f"  {picker_uri}\n")
    print("=" * 68)
    if open_browser and picker_uri:
        webbrowser.open(picker_uri)

    try:
        wait_for_selection(creds, project, session)
        items = [i for i in list_media_items(creds, project, session_id) if _is_photo(i)]
    finally:
        delete_session(creds, project, session_id)

    if not items:
        print("No photos were selected.")
        return []

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nDownloading {len(items)} photo(s) …")
    downloaded: list[Path] = []
    for item in items:
        try:
            path = download_item(creds, project, item, DOWNLOAD_DIR)
            if path:
                downloaded.append(path)
                print(f"  \u2193 {path.name}")
        except requests.RequestException as exc:
            print(f"  ! failed to download {item.get('id')}: {exc}")
    return downloaded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["picker", "local"],
        default="picker",
        help="picker (Google Photos, default) or local (process an existing folder)",
    )
    parser.add_argument(
        "--auth",
        choices=["adc", "oauth-client"],
        default="adc",
        help=(
            "adc = gcloud Application Default Credentials (default); "
            "oauth-client = Desktop OAuth client via credentials.json"
        ),
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT"),
        help=(
            "Google Cloud project ID with the Photos Picker API enabled, used for "
            "quota attribution with ADC. Defaults to $GOOGLE_CLOUD_PROJECT."
        ),
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        help="folder of exported photos when --source local",
    )
    parser.add_argument(
        "--slots",
        help=(
            "comma-separated slot names to fill instead of all slots, "
            "e.g. --slots gallery-5"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"where to stage processed images (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--keep-downloads",
        action="store_true",
        help="keep the raw downloaded originals in ./downloads",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the picker URL in a browser automatically",
    )
    args = parser.parse_args()

    selected_slots = None
    if args.slots:
        names = [n.strip() for n in args.slots.split(",") if n.strip()]
        try:
            selected_slots = [process_images.SLOTS_BY_NAME[n] for n in names]
        except KeyError as exc:
            parser.error(
                f"unknown slot {exc}. Valid slots: "
                + ", ".join(process_images.SLOTS_BY_NAME)
            )

    if args.source == "local":
        if not args.local_dir:
            parser.error("--source local requires --local-dir")
        source_dir = args.local_dir.expanduser().resolve()
        if not source_dir.is_dir():
            parser.error(f"not a directory: {source_dir}")
        sources = process_images.gather_sources(source_dir)
        if not sources:
            print(f"No supported images found in {source_dir}")
            return 1
    else:
        sources = run_picker(
            open_browser=not args.no_open,
            auth_method=args.auth,
            project=args.project,
        )
        if not sources:
            return 1

    print(f"\nProcessing {len(sources)} photo(s) into slots …")
    process_images.process(sources, args.output_dir.expanduser().resolve(), selected_slots)

    if args.source == "picker" and not args.keep_downloads:
        for path in sources:
            path.unlink(missing_ok=True)

    print(f"\nDone. Staged images are in: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
