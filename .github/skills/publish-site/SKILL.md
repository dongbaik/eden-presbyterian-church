---
name: publish-site
description: 'Build/deploy the church website to Firebase Hosting (Google Cloud) and manage the oregoneden.com custom domain. Use when the user says "publish", "deploy", "publish the site", "사이트 배포", "배포해줘", "홈페이지 올려줘", "go live", "push to production", "update the live site", or wants to connect/verify the oregoneden.com domain. This site is plain static HTML/CSS/JS with no build step; deploying = uploading the repo to Firebase Hosting.'
argument-hint: '[optional: "domain" to work on the custom domain step]'
---

# Publish the site to Firebase Hosting

The church website is a **static** HTML/CSS/JS site (no build step). It is hosted
on **Firebase Hosting** (a Google Cloud product): free tier, free automatic SSL,
global CDN, one-command deploy.

- **Live domain:** `oregoneden.com` (apex) + `www.oregoneden.com`
- **Firebase project:** see [.firebaserc](../../../.firebaserc) (`default` alias)
- **Hosting config:** [firebase.json](../../../firebase.json) — serves the repo
  root, ignoring `.git`, `.github`, `.venv`, `tools/`, `node_modules`, `README.md`.
- **DNS registrar:** GoDaddy (records for `oregoneden.com` are managed there)

## Prerequisites (one time)

Node.js + the Firebase CLI must be on PATH:

```powershell
node --version        # any LTS is fine
firebase --version    # >= 13
```

If missing:

```powershell
winget install --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements --silent
npm install -g firebase-tools
```

> After installing Node in a fresh terminal, refresh PATH for the current session:
> `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`

> **Interactive commands need a real terminal.** `firebase login` (and any command
> that prompts) must be run in a normal terminal window — PowerShell or Windows
> Terminal — **not** inside an automated/agent shell. On Node 24 the CLI's
> device-code prompt can crash with a libuv assertion in a non-interactive shell;
> a real terminal uses the browser-loopback flow and works fine. Non-interactive
> commands (`firebase deploy --only hosting`, `firebase projects:create <id> ...`)
> are safe to run anywhere.

## Everyday deploy (the common case)

Once the project + domain are already set up, publishing is just:

```powershell
firebase deploy --only hosting
```

`firebase login` must have been run at least once. The command uploads the
current working tree (per [firebase.json](../../../firebase.json)) and prints the
live URL. Changes are live within seconds; Firebase keeps previous releases so
you can roll back.

### Roll back a bad deploy

Firebase Console → Hosting → **Release history** → hover the previous release →
**Rollback**. (There is no stable CLI rollback command.)

## First-time setup

Do these steps only once, in order. They are interactive (browser sign-in), so
run them one at a time and let the user complete each browser step. Sign in with
a Google account that should own the church's hosting.

### 1. Sign in

```powershell
firebase login
```

Opens a browser for Google OAuth. **Do not** run `firebase login:ci` or paste
tokens into chat.

### 2. Create the Firebase project

```powershell
firebase projects:create --display-name "Eden Presbyterian Church"
```

Firebase prints the generated **project ID** (globally unique, e.g.
`eden-presbyterian-church`). If that ID is taken, pass an explicit one:
`firebase projects:create oregon-eden-church --display-name "Eden Presbyterian Church"`.

### 3. Point the repo at the project

```powershell
firebase use --add
```

Pick the project just created and give it the alias **`default`**. This writes
[.firebaserc](../../../.firebaserc). Commit that file.

### 4. First deploy

```powershell
firebase deploy --only hosting
```

Confirm the `*.web.app` / `*.firebaseapp.com` URL works before touching the
domain.

## Connect the oregoneden.com custom domain

> This changes the LIVE domain that currently points to Weebly. Do the Firebase
> deploy first and verify the `*.web.app` URL. The cut-over is a DNS change at
> **GoDaddy** — reversible, but propagation can take up to 48h.

### 1. Add the domain in Firebase

Firebase Console → **Hosting** → **Add custom domain** → enter `oregoneden.com`.
Also add `www.oregoneden.com` (choose to redirect `www` → apex, or vice-versa).

Firebase shows the DNS records to create. Two phases:

1. **Ownership verification** — a `TXT` record (only if prompted).
2. **Go live** — usually **two `A` records** for the apex pointing at Firebase's
   IPs (Firebase shows the exact values, commonly `151.101.1.195` and
   `151.101.65.195`), plus a `CNAME` for `www` → `<project>.web.app`.

### 2. Edit DNS at GoDaddy

GoDaddy → **My Products** → `oregoneden.com` → **DNS** → **Manage DNS**.

1. **Remove the Weebly records** for the same names — typically the existing
   apex `A` record(s) (`@`) and the `www` `CNAME`. Note them down first in case
   of rollback.
2. Add the **`A` records** Firebase gave you for `@` (Host = `@`).
3. Add/point the **`www` `CNAME`** to `<project>.web.app`.
4. Add the verification **`TXT`** record if Firebase asked for one.
5. Leave `MX` / email records untouched.

GoDaddy's minimum TTL is 600s; lowering TTL before the change speeds cut-over.

### 3. Wait & verify

Back in Firebase, the domain status goes `Needs setup` → `Pending` → `Connected`,
and Firebase auto-provisions a free SSL certificate (can take from minutes up to
24h). Verify:

```powershell
nslookup oregoneden.com
```

The apex should resolve to the Firebase IPs. Once `Connected`, `https://oregoneden.com`
serves this site with a valid certificate.

## Notes & gotchas

- **No build step.** Never run a bundler; `firebase deploy` uploads files as-is.
- **What ships** is governed by the `ignore` list in
  [firebase.json](../../../firebase.json). If you add a top-level folder that
  should not be public, add it there.
- **Secrets:** `tools/photos/credentials.json` and `token.json` are git-ignored
  *and* firebase-ignored (they live under `tools/`). Never deploy them.
- **`.firebaserc`** is safe to commit (it only holds the project ID). Auth tokens
  live in the CLI's own config, never in the repo.
- Keep `git push` (GitHub) and `firebase deploy` as **separate** actions — GitHub
  is the source of truth / preview, Firebase is production.
