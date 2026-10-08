# do.you.know.7 — local IG carousel generator

Localhost web app. Type a question → LLM (DeepSeek) writes short + long answers → renders
3 images (1080×1350) → preview → publish carousel to Instagram via Meta OAuth.

This project uses Meta's **Instagram API with Facebook Login** configuration. It is
still supported, but it is different from Meta's newer **Instagram Login** configuration.
Follow the Facebook Login steps below: changing only the Meta dashboard setup to
Instagram Login will not work with the current code.

No DB. No Telegram. Token lives in `token.json`.

---

## 1. Prerequisites

- Python 3.10+
- Instagram **Business or Creator** account (Personal accounts cannot publish via the official API)
- A Facebook Page linked to that Instagram account (required by this project's Facebook Login flow)
- Meta developer account
- The Facebook account you will use for login, assigned an app role and with full control of that Page
- DeepSeek API key
- Supabase project with a public Storage bucket (S3-compatible; free tier, no card)

---

## 2. Meta App setup (detailed)

### 2.1 Create a Business app
1. Go to https://developers.facebook.com and log in. Create a developer account if asked (phone verification).
2. **My Apps → Create App**.
3. Choose the **Business** app type. Depending on the current dashboard wording, this may be under
   **Other** or a business-management use case.
4. Give it a name (for example, `do-you-know`), set a contact email, and create it.

The labels in Meta's dashboard change occasionally; the important outcome is a Business app that
has the Instagram and Facebook Login products below.

### 2.2 Add the Instagram and Facebook Login products
1. In the app dashboard left sidebar: **Add Product → Instagram** → Set up.
2. Choose the **Instagram API with Facebook Login** path (sometimes shown as **Instagram Graph API**).
   Do **not** use Instagram Basic Display; it is retired and cannot publish content.
3. Add **Facebook Login**. Meta's current documentation refers to this configuration as
   **Facebook Login for Business**. Choose **Web** when the dashboard asks for a platform and set
   the site URL to `http://localhost:5001/`.

### 2.3 Configure the OAuth redirect
1. Open the Facebook Login / Facebook Login for Business settings.
2. In **Valid OAuth Redirect URIs**, add this exact value:
   ```
   http://localhost:5001/callback
   ```
3. Save. The redirect URI must match `REDIRECT_URI` exactly, including protocol, hostname, port,
   path, and trailing slash behavior.

When a user selects **Login with Instagram**, the app uses the server-side Facebook Login OAuth
code flow. It exchanges the callback code for a long-lived user token, retrieves the connected
Page access token, and uses that Page token for carousel publishing. The Instagram account and
Facebook Page must already be linked before login.

### 2.4 Assign your app role and request the permissions
1. In **App roles**, add the Facebook account that will connect the Instagram account as an
   administrator, developer, or tester. Make sure the invitation is accepted.
2. In **App Review → Permissions and Features**, configure these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
   - `pages_show_list` (needed by this app to query `/me/accounts` and find the connected IG account)
   - `business_management` (required by the current Facebook Login for Business setup)
3. In Development mode, standard access is sufficient only for people who hold an app role and
   use assets they administer. Keep the app in Development mode for this single-account local app.
4. To let people who are not app-role holders connect their accounts, move the app to Live mode and
   obtain the necessary Advanced Access / App Review approval. Meta may also require business
   verification.

### 2.5 Get credentials
1. **App settings → Basic**: copy **App ID** and **App Secret**.

### 2.6 Prepare the Instagram account
1. In the Instagram app: **Settings → Account type and tools → Switch to professional account** → choose **Creator** (or Business).
2. Link a Facebook Page: Instagram Settings → "Facebook Page" (or in Meta Business Suite). Your IG must be linked to a Page you admin.
3. The Facebook account you use to log in through the OAuth flow must have full control of that Page.
4. If Meta asks the Page to complete **Page Publishing Authorization**, complete it before testing.
   Publishing can otherwise be blocked, and the API does not expose a reliable way to detect that
   requirement in advance.

### 2.7 Important: do not mix the two Instagram login configurations

Meta's newer **Instagram API with Instagram Login** can be a better fit for a new integration: it
does not require a Facebook Page and uses `instagram_business_basic` and
`instagram_business_content_publish` permissions. It also uses `graph.instagram.com` and an
Instagram User access token.

This repository does **not** use that flow. Its OAuth URL, scopes, account discovery call, and
publishing calls use the Facebook Login configuration and `graph.facebook.com`. Keep the Facebook
Page linked and follow the steps above unless the application code is migrated as well.

### 2.8 Production-readiness notes

- Meta fetches the media itself, so every Supabase image URL must be public at the moment of publishing.
  Signed URLs, browser-only access, login gates, and hotlink protection can cause publishing to fail.
- For the Facebook Login configuration, publishing should use the connected **Facebook Page access
  token**, not only the initial Facebook user token. Store the token expiry and provide a way to
  re-authorize/refresh it; long-lived user tokens do not last indefinitely.
- A carousel child container needs `is_carousel_item=true`. The carousel container then uses
  `media_type=CAROUSEL` and the children IDs. Carousels support up to 10 items.
- If the rendered media qualifies as AI-generated under Meta's current requirements, include
  `is_ai_generated=true` on the parent carousel container. Recheck this requirement whenever the
  publishing API version changes.
- The application defaults to Graph API `v26.0` through `META_GRAPH_VERSION`. Recheck the
  changelog and test the full publishing flow before every version upgrade.

### Meta references

- [Instagram API with Facebook Login — content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing)
- [Instagram API with Instagram Login — content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing)
- [Graph API version schedule](https://developers.facebook.com/docs/graph-api/changelog/versions/)

---

## 3. Supabase Storage setup

1. https://supabase.com → create a project (note the **project ref** from the dashboard URL).
2. **Storage → New bucket** → name `do-you-know` → toggle **Public bucket** ON → create.
3. **Storage → Configuration → S3 Access Keys** → **Create access key** → copy **Access Key ID** + **Secret Access Key** (secret shown once).
4. From the same page copy the **Endpoint** (`https://<project-ref>.supabase.co/storage/v1/s3`) and note the **Region** (e.g. `us-east-1`).
5. Public URL base: `https://<project-ref>.supabase.co/storage/v1/object/public/do-you-know`.

---

## 4. DeepSeek

1. https://platform.deepseek.com → create API key.
2. Model id: `deepseek-chat` (DeepSeek-V3). The API has no model called "v4 flash" — if you have a different/newer model id, just set `DEEPSEEK_MODEL` in `.env`.

---

## 5. Run

The app is split into a Flask API backend (`backend/`) and a React frontend
(`frontend/`, built with Vite).

### One-time setup

```bash
cd do-you-know
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env

cd frontend
npm install
npm run build   # builds frontend/dist, which Flask serves
cd ..
```

### Production-style (single origin, recommended)

```bash
python run.py
```

Open http://localhost:5001 → "Connect Instagram" → approve → type a question → Generate →
Preview → Post. Flask serves the built React app and the API on the same port.

### Development (React hot reload)

Run the backend and the Vite dev server side by side:

```bash
# terminal 1
python run.py

# terminal 2
cd frontend
npm run dev
```

Open http://localhost:5173. Vite proxies `/api`, `/img`, `/login` and `/callback`
to Flask on :5001. The OAuth redirect URI stays `http://localhost:5001/callback`,
so after logging in you land on :5001 (which serves the built app). Rebuild with
`npm run build` if you want :5001 to always show the latest frontend.

### Note on redirect URI
The OAuth redirect is `http://localhost:5001/callback`. If you change the port, update
`REDIRECT_URI` in `.env` AND the Valid OAuth Redirect URIs in the Meta app.

---

## 6. Telegram approval + daily scheduler

The app can now run a daily job and ask for your approval over Telegram before
publishing. `run.py` starts three things at once:

- the Flask API + web UI
- a background scheduler that fires once a day at the configured time
- a Telegram long-polling bot for review

### 6.1 Configure Telegram

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Message your new bot once, then get your chat id (e.g. via
   `https://api.telegram.org/bot<TOKEN>/getUpdates`, or ask @userinfobot).
3. Add to `.env`:

```
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

Only this chat id can run commands and approve/reject drafts.

### 6.2 Daily job (8:00 AM IST by default)

`SCHEDULE_ENABLED=true`, `SCHEDULE_HOUR=8`, `SCHEDULE_MINUTE=0`,
`SCHEDULE_TZ=Asia/Kolkata`. At that time the app generates a question, then sends
you the question + short answer + long answer with **✅ Approve & Post** and
**❌ Reject** buttons. Approving renders the images, uploads to Supabase, and
publishes the carousel to Instagram.

### 6.3 Manual triggers

CLI (needs `python run.py` already running to handle the approve callback):

```bash
source .venv/bin/activate
python cli.py daily                       # same as the scheduled job
python cli.py ask "Do you know ...?"      # your own question
```

Or from Telegram (the configured chat only):

```
/daily
/ask Do you know ...?
```

### 6.4 Run on Oracle bare metal

Run the same single process in the background with systemd (or `nohup`):

```
nohup python run.py > app.log 2>&1 &
```

Keep the process alive with a systemd unit (recommended):

```ini
[Unit]
Description=do.you.know.7
After=network.target

[Service]
WorkingDirectory=/opt/do-you-know
ExecStart=/opt/do-you-know/.venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Set `REDIRECT_URI` and the Meta Valid OAuth Redirect URI to the server's public
URL (e.g. `https://your-host/callback`) so Instagram login still works when you
re-authorize.

## Files

```
backend/
  config.py            # env config + constants
  storage.py           # token.json / posts.json persistence
  deepseek.py          # answer generation + caption/comment builders
  imaging.py           # Pillow slide rendering
  supabase_store.py    # S3 upload to Supabase
  instagram.py         # Instagram Graph API calls
  insights.py          # post insights fetch/format
  app.py               # Flask app + JSON API
  jobs.py              # approval workflow (generate → review → publish)
  scheduler.py         # daily job loop
  telegram_bot.py      # Telegram long-polling review bot
frontend/
  src/                 # React SPA (Home, Preview, components)
  src/styles.css       # design system (verbatim port)
  dist/                # production build (gitignored)
run.py                 # entrypoint (Flask + scheduler + Telegram bot)
cli.py                 # manual triggers: daily / ask
fonts/                 # Anton-Regular.ttf used by the renderer
token.json             # saved IG token (auto-created, do not commit)
approvals.json         # pending/approved/rejected approval records
out/<draft>/0..2.jpg   # rendered slides (auto-created)
.env                   # secrets (do not commit)
```

### API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/me` | OAuth/login state |
| GET | `/api/posts?refresh=1` | post library + view-model fields |
| POST | `/api/generate` | `{question}` → new draft |
| GET | `/api/posts/<id>` | draft detail (preview page) |
| POST | `/api/posts/<id>/publish` | publish carousel in background |
| GET | `/img/<id>/<n>` | rendered slide image |
| GET | `/login`, `/callback` | Instagram OAuth (server redirect) |
