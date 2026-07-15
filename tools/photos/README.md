# Church photo fetcher

Downloads photos from the **media@oregoneden.com** Google Photos album, then
crops, resizes and optimises them into the website's image slots under
[`assets/photos/`](../../assets/photos/).

## Why there is a browser step

Google removed the broad Google Photos *Library* read scopes in **March 2025**.
You can no longer list or download an existing album's contents with a plain
read-only token, and **service accounts are not supported** for Google Photos.
The supported path is the **Google Photos Picker API**: you authorise once and
select the album's photos in a browser a single time. Everything after that —
download, crop, optimise, stage — is automatic.

If you want **zero browser interaction**, export the album another way (Google
Takeout, or download a shared-album zip) and use `--source local` below.

---

## One-time setup (gcloud ADC — recommended)

This path uses `gcloud auth application-default login` for authentication, so
you do **not** need to create or download an OAuth client.

### 1. Enable the Photos Picker API on a project
1. Go to <https://console.cloud.google.com/> (sign in as someone who can manage
   Cloud for the domain, e.g. `admin@oregoneden.com`) and pick/create a project.
2. **APIs & Services → Library**, search **"Photos Picker API"**, click **Enable**.
3. Note the **project ID** — you'll pass it as `--project`.

### 2. Authorise Application Default Credentials
Sign in as **media@oregoneden.com** when the browser opens:
```bash
gcloud auth application-default login \
    --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/photospicker.mediaitems.readonly
```
This is the only browser sign-in for auth; the credential is cached by gcloud
and reused automatically afterwards.

### 3. Install dependencies
```bash
cd tools/photos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional, for iPhone HEIC photos:
# pip install pillow-heif
```

---

## Usage

### Fetch from Google Photos (Picker)
```bash
cd tools/photos
source .venv/bin/activate
python fetch_photos.py --project YOUR_PROJECT_ID
```
(Or `export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID` and omit `--project`.)

1. The script prints a **picker URL** (and opens it). Sign in as
   **media@oregoneden.com**, open the album and select the photos you want.
2. When you click **Done**, the script downloads the originals and stages the
   processed images into `assets/photos/`.

Useful flags:
- `--keep-downloads` — keep the raw originals in `tools/photos/downloads/`.
- `--no-open` — don't auto-open the browser (print the URL only).
- `--output-dir PATH` — stage somewhere other than `assets/photos/`.

### Fully unattended (no browser) — process a local folder
```bash
python fetch_photos.py --source local --local-dir ~/Downloads/eden-album
```
Or process images directly:
```bash
python process_images.py ~/Downloads/eden-album
```

---

## Alternative: Desktop OAuth client (instead of gcloud ADC)

If you'd rather not use gcloud ADC, create a Desktop OAuth client and use
`--auth oauth-client`:

1. **APIs & Services → OAuth consent screen** → User type **Internal**
   (or **External** with `media@oregoneden.com` as a test user).
2. **APIs & Services → Credentials → Create credentials → OAuth client ID** →
   Application type **Desktop app** → **Download JSON**.
3. Save it as `tools/photos/credentials.json` (git-ignored).
4. Run:
   ```bash
   python fetch_photos.py --auth oauth-client
   ```
   A refresh token is cached in `token.json` so you only consent once.

---

## What gets produced

Each site slot is filled with an optimised `.jpg` **and** `.webp` in
`assets/photos/`:

| File | Aspect | Used for |
| --- | --- | --- |
| `hero.*` | 16:9 | Home hero background |
| `about.*` | 4:3 | About section photo |
| `mission-1.*` … `mission-3.*` | 16:9 | Mission cards (Domestic / Global / Relief) |
| `gallery-1.*` | 16:9 | Wide gallery tile (`span-2`) |
| `gallery-2.*` … `gallery-5.*` | 1:1 | Square gallery tiles |
| `extras/extra-NN.jpg` | — | Any leftover photos, downscaled |

Photos are assigned to slots in order, preferring landscape images for
wide slots and square/portrait crops for the square gallery tiles.

## Security notes
- `credentials.json` and `token.json` (only used with `--auth oauth-client`) are
  secrets and are git-ignored — never commit them.
- The OAuth scope requested is read-only:
  `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`.
- To revoke access later: <https://myaccount.google.com/permissions> while
  signed in as `media@oregoneden.com`. For ADC, also run
  `gcloud auth application-default revoke`; for the OAuth-client flow, delete
  `token.json`.
