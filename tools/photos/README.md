# Photo tooling — runtime environment

The photo scripts now live with the skills that use them:

| Skill | Script | Purpose |
| --- | --- | --- |
| [`update-gallery`](../../.github/skills/update-gallery/SKILL.md) | `sync_albums.py` | Google Photos album cards on `gallery.html` |
| [`update-site-photos`](../../.github/skills/update-site-photos/SKILL.md) | `fetch_photos.py` | Hero / About / mission / home gallery slots |
| [`optimize-photos`](../../.github/skills/optimize-photos/SKILL.md) | `process_images.py` | Crop, resize and optimise a local folder |

Ask the agent to *"update gallery"*, *"update site photos"* or *"optimize
photos"* and it will follow the matching skill.

This folder keeps only what should not live in a skill folder: the virtualenv,
the Google credentials, and the album list.

| Path | What it is |
| --- | --- |
| `.venv/` | Shared Python environment for all three scripts |
| `requirements.txt` | Their dependencies |
| `albums.txt` | The Google Photos album links shown in the gallery |
| `credentials.json`, `token.json` | OAuth client + cached refresh token (git-ignored) |
| `downloads/` | Scratch space for photos being fetched (git-ignored) |

---

## Setup

```bash
cd tools/photos
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Optional, for iPhone HEIC photos:
# .venv/bin/pip install pillow-heif
```

Run the scripts from the repository root with this interpreter, for example:

```bash
tools/photos/.venv/bin/python .github/skills/update-gallery/scripts/sync_albums.py
```

## Google Photos access

`sync_albums.py` needs **no** credentials — it reads the public OpenGraph tags
of albums that already have link sharing turned on.

`fetch_photos.py` uses the **Photos Picker API** and needs a Desktop OAuth
client at `tools/photos/credentials.json`. Always run it with
`--auth oauth-client`; the `adc` path fails because Google blocks gcloud's
built-in client from the `photospicker` scope.

Google removed the broad Photos *Library* read scopes in March 2025 and does not
support service accounts, so there is no fully unattended way to read this
account's photos. The picker's browser step happens once and the refresh token
is cached afterwards.

## Security

`credentials.json` and `token.json` are secrets and are git-ignored — never
commit them or paste their contents anywhere.
