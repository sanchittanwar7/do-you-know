import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import boto3
import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, send_file, session, url_for
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", secrets.token_hex(16))


@app.template_filter("dt")
def _format_dt(value):
    """Render a unix timestamp as a readable editorial date."""
    try:
        return datetime.fromtimestamp(int(value)).strftime("%b %d, %Y")
    except (TypeError, ValueError, OSError):
        return "—"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5001/callback")
PORT = int(os.getenv("PORT", "5001"))
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCOPES = "instagram_basic,instagram_content_publish,instagram_manage_comments,pages_show_list,pages_read_engagement,business_management,instagram_manage_insights"
META_PAGE_ID = os.getenv("META_PAGE_ID", "")
META_CONTENT_IS_AI_GENERATED = os.getenv("META_CONTENT_IS_AI_GENERATED", "true").lower() == "true"

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SUPABASE_KEY = os.getenv("SUPABASE_ACCESS_KEY_ID", "")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET_ACCESS_KEY", "")
SUPABASE_ENDPOINT = os.getenv("SUPABASE_ENDPOINT", "")
SUPABASE_REGION = os.getenv("SUPABASE_REGION", "us-east-1")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "")
SUPABASE_PUBLIC_BASE = os.getenv("SUPABASE_PUBLIC_BASE", "").rstrip("/")
IMG_KEY_PREFIX = "do-you-know"

TOKEN_FILE = Path("token.json")
POSTS_FILE = Path("posts.json")
OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

_posts_lock = threading.Lock()

IMG_W, IMG_H = 1080, 1350
BG = (253, 250, 239)  # warm cream from reference image
FG = (5, 5, 5)        # near-black from reference image
HEADER = "Do you know?"
HANDLE = "@do.you.know.7"

# 3 fixed visibility hashtags that ship with every caption.
FIXED_HASHTAGS = ["#doyouknow", "#facts", "#curious"]


# ---------------------------------------------------------------------------
# Token helpers (file-based, no DB)
# ---------------------------------------------------------------------------
def load_token():
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return {}


def save_token(data):
    TOKEN_FILE.write_text(json.dumps(data, indent=2))


def load_posts():
    if POSTS_FILE.exists():
        try:
            return json.loads(POSTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_posts(posts):
    POSTS_FILE.write_text(json.dumps(posts, indent=2, ensure_ascii=False))


def upsert_post(record):
    with _posts_lock:
        posts = load_posts()
        for i, p in enumerate(posts):
            if p.get("id") == record["id"]:
                posts[i] = record
                save_posts(posts)
                return
        posts.insert(0, record)
        save_posts(posts)


# View-model fields computed per-request; never persist them into posts.json.
_VIEW_FIELDS = {"media_link", "stats", "insights_error"}


def persist_post(record):
    upsert_post({k: v for k, v in record.items() if k not in _VIEW_FIELDS})


def get_post(post_id):
    for p in load_posts():
        if p.get("id") == post_id:
            return p
    return None


# ---------------------------------------------------------------------------
# DeepSeek
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You write Instagram trivia carousel content for the page 'do.you.know.7'. "
    "Given a question, produce TWO answers and THREE post-specific hashtags.\n"
    "- short_answer: at most 10 words, punchy, no preamble.\n"
    "- long_answer: at most 50 words, explain the WHY, end cleanly, no emoji.\n"
    "- hashtags: array of exactly 3 hashtags, each a short lowercase keyword or phrase "
    "(no spaces, no '#' prefix) relevant to this specific question, to boost reach "
    "for this post's topic.\n"
    'Return ONLY valid JSON: {"short_answer": "...", "long_answer": "...", '
    '"hashtags": ["...", "...", "..."]}'
)


def generate_answers(question: str):
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    # strip markdown fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content)
    hashtags = [str(h).strip().lstrip("#") for h in (data.get("hashtags") or [])][:3]
    return data["short_answer"].strip(), data["long_answer"].strip(), hashtags


def build_caption(question, hashtags=None):
    """Question only + 3 fixed + 3 post hashtags. Answers move to a comment."""
    parts = [question]
    tags = list(FIXED_HASHTAGS) + ["#" + str(h).lstrip("#") for h in (hashtags or [])]
    if tags:
        parts += ["", " ".join(tags)]
    return "\n".join(parts)


def build_comment(short_answer, long_answer):
    """Short + long answer combined, posted as the first comment."""
    return "\n\n".join(part for part in (short_answer, long_answer) if part)


# ---------------------------------------------------------------------------
# Image rendering
# ---------------------------------------------------------------------------
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_CANDIDATES = [
    str(FONT_DIR / "Anton-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default(size)


def wrap_text(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def render_slide(text, path, with_header=True):
    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)
    text = capitalize_first(text.strip())

    # header (question slide only)
    if with_header:
        draw.text((IMG_W // 2, 90), HEADER, font=load_font(64), fill=FG, anchor="ma")

    # main text, auto-fit and centered
    box_w = IMG_W - 160
    box_top = 210 if with_header else 140
    box_bottom = IMG_H - 190
    box_h = box_bottom - box_top
    size = 150
    while size > 30:
        font = load_font(size)
        lines = wrap_text(draw, text, font, box_w)
        if size * 1.2 * len(lines) <= box_h:
            break
        size -= 4
    font = load_font(size)
    lines = wrap_text(draw, text, font, box_w)
    total_h = size * 1.2 * len(lines)
    y = box_top + (box_h - total_h) / 2
    for line in lines:
        draw.text((IMG_W // 2, y), line, font=font, fill=FG, anchor="ma")
        y += size * 1.2

    # bottom-right handle
    draw.text((IMG_W - 60, IMG_H - 60), HANDLE, font=load_font(40), fill=FG, anchor="rs")

    img.save(path, "JPEG", quality=92)
    return path


def render_images(question, short_answer, long_answer, draft_id):
    d = OUT_DIR / draft_id
    d.mkdir(parents=True, exist_ok=True)
    render_slide(question, str(d / "0.jpg"), with_header=True)
    render_slide(short_answer, str(d / "1.jpg"), with_header=False)
    render_slide(long_answer, str(d / "2.jpg"), with_header=False)
    return [str(d / "0.jpg"), str(d / "1.jpg"), str(d / "2.jpg")]


# ---------------------------------------------------------------------------
# Supabase Storage upload
# ---------------------------------------------------------------------------
def supabase_client():
    return boto3.client(
        "s3",
        endpoint_url=SUPABASE_ENDPOINT,
        aws_access_key_id=SUPABASE_KEY,
        aws_secret_access_key=SUPABASE_SECRET,
        region_name=SUPABASE_REGION,
        config=boto3.session.Config(s3={"addressing_style": "path"}),
    )


def upload_to_storage(local_paths, draft_id):
    if not (SUPABASE_ENDPOINT and SUPABASE_KEY and SUPABASE_SECRET and SUPABASE_BUCKET):
        raise RuntimeError("Supabase storage is not configured. Set SUPABASE_* in .env.")
    client = supabase_client()
    urls = []
    for i, p in enumerate(local_paths):
        key = f"{IMG_KEY_PREFIX}/{draft_id}/{i}.jpg"
        client.upload_file(p, SUPABASE_BUCKET, key, ExtraArgs={"ContentType": "image/jpeg"})
        urls.append(f"{SUPABASE_PUBLIC_BASE}/{key}")
    return urls


def supabase_folder_url(draft_id):
    """Dashboard link to the folder in the public bucket holding a draft's images."""
    if not (SUPABASE_ENDPOINT and SUPABASE_BUCKET):
        return None
    try:
        ref = SUPABASE_ENDPOINT.split("//")[1].split(".")[0]
    except IndexError:
        return None
    folder = f"{IMG_KEY_PREFIX}/{draft_id}"
    return (
        f"https://supabase.com/dashboard/project/{ref}/storage/files/buckets/"
        f"{SUPABASE_BUCKET}?path={folder}"
    )


# ---------------------------------------------------------------------------
# Instagram Graph API
# ---------------------------------------------------------------------------
def get_connected_instagram_account(user_access_token):
    """Return the one Page-connected Instagram account used by this local app."""
    r = requests.get(
        f"{GRAPH}/me/accounts",
        params={
            "fields": "id,name,access_token,instagram_business_account",
            "access_token": user_access_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    candidates = []
    for page in r.json().get("data", []):
        ig = page.get("instagram_business_account")
        if ig and ig.get("id") and page.get("access_token"):
            candidates.append(
                {
                    "page_id": page["id"],
                    "page_name": page.get("name", page["id"]),
                    "page_access_token": page["access_token"],
                    "ig_user_id": ig["id"],
                }
            )

    if META_PAGE_ID:
        candidates = [account for account in candidates if account["page_id"] == META_PAGE_ID]

    if not candidates:
        detail = f" matching META_PAGE_ID={META_PAGE_ID}" if META_PAGE_ID else ""
        raise RuntimeError(
            "No Page-connected Instagram Business/Creator account found"
            f"{detail}. Confirm the Page link and the requested permissions."
        )
    if len(candidates) > 1:
        page_names = ", ".join(account["page_name"] for account in candidates)
        raise RuntimeError(
            "More than one Page-connected Instagram account was found "
            f"({page_names}). Set META_PAGE_ID in .env to the Page you want to use."
        )
    return candidates[0]


def create_image_container(ig_user_id, image_url, page_access_token):
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
        params={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": page_access_token,
        },
        timeout=60,
    )
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Image container failed: {data}")
    return data["id"]


def wait_for_container(container_id, page_access_token, tries=20):
    """Wait for a media container to finish processing before it is published."""
    for _ in range(tries):
        r = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code,status", "access_token": page_access_token},
            timeout=30,
        )
        r.raise_for_status()
        status = r.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Media container {container_id} failed: {r.json()}")
        time.sleep(2)
    raise RuntimeError(f"Media container {container_id} did not finish processing in time.")


def publish_carousel(ig_user_id, image_urls, caption, page_access_token):
    child_ids = [
        create_image_container(ig_user_id, image_url, page_access_token)
        for image_url in image_urls
    ]
    for child_id in child_ids:
        wait_for_container(child_id, page_access_token)

    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
        "access_token": page_access_token,
    }
    if META_CONTENT_IS_AI_GENERATED:
        # Meta requires this on the parent carousel container, not its children.
        params["is_ai_generated"] = "true"
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
        params=params,
        timeout=60,
    )
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Carousel container failed: {data}")
    carousel_id = data["id"]
    wait_for_container(carousel_id, page_access_token)

    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media_publish",
        params={"creation_id": carousel_id, "access_token": page_access_token},
        timeout=60,
    )
    pub = r.json()
    if "id" not in pub:
        raise RuntimeError(f"Publish failed: {pub}")
    return pub["id"]


def post_comment(media_id, message, page_access_token):
    """Post the combined short + long answer as a comment on the media."""
    r = requests.post(
        f"{GRAPH}/{media_id}/comments",
        params={"message": message, "access_token": page_access_token},
        timeout=60,
    )
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Comment failed: {data}")
    return data["id"]


def wait_for_permalink(media_id, page_access_token, tries=40):
    for _ in range(tries):
        # NOTE: `status_code` is only valid on *containers*, not on published
        # IG Media. Requesting it here returns a #100 error, so query only
        # fields that exist on media.
        r = requests.get(
            f"{GRAPH}/{media_id}",
            params={"fields": "permalink,shortcode", "access_token": page_access_token},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        if d.get("permalink"):
            return d["permalink"]
        if d.get("shortcode"):
            return f"https://www.instagram.com/p/{d['shortcode']}/"
        time.sleep(3)
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    token = load_token()
    logged_in = bool(token.get("page_access_token") and token.get("ig_user_id"))
    posts = load_posts()
    now = int(time.time())
    force = request.args.get("refresh") == "1"
    page_token = token.get("page_access_token")
    for p in posts:
        p["media_link"] = supabase_folder_url(p["id"]) if p.get("image_urls") else None
        p["stats"] = None
        p["insights_error"] = None
        # Permalink backfill: Instagram often returns it a while after publish.
        if (
            p.get("status") == "published"
            and p.get("media_id")
            and not p.get("permalink")
            and page_token
        ):
            pat = p.get("permalink_attempt_at", 0)
            if force or (now - pat) > 60:
                p["permalink_attempt_at"] = now
                try:
                    pl = wait_for_permalink(p["media_id"], page_token, tries=4)
                    if pl:
                        p["permalink"] = pl
                        p["updated_at"] = now
                except Exception:
                    pass
                persist_post(p)
        if p.get("status") == "published" and p.get("media_id") and page_token:
            cached = p.get("insights")
            at = p.get("insights_at", 0)
            if cached is None or force or (now - at) > 600:
                try:
                    cached = fetch_post_insights(p["media_id"], page_token)
                    p["insights"] = cached
                    p["insights_at"] = now
                    persist_post(p)
                except Exception as exc:
                    p["insights_error"] = str(exc)
            p["stats"] = format_insights(cached or {})
    return render_template(
        "index.html",
        logged_in=logged_in,
        username=token.get("username", ""),
        posts=posts,
    )


@app.route("/login")
def login():
    if not META_APP_ID:
        return "Missing META_APP_ID. Add it to .env before connecting Instagram.", 500

    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = {
        "client_id": META_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    url = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(params)}"
    return redirect(url)


@app.route("/callback")
def callback():
    if request.args.get("error"):
        description = request.args.get("error_description", request.args["error"])
        return f"OAuth failed: {description}", 400

    expected_state = session.pop("oauth_state", None)
    received_state = request.args.get("state")
    if not expected_state or not isinstance(received_state, str) or not secrets.compare_digest(
        expected_state, received_state
    ):
        return "OAuth state did not match. Start the login again.", 400

    code = request.args.get("code")
    if not code:
        return "OAuth failed: no authorization code returned.", 400

    try:
        short_token_response = requests.get(
            f"{GRAPH}/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
            },
            timeout=30,
        )
        short_token_response.raise_for_status()
        short_lived_token = short_token_response.json()["access_token"]

        long_token_response = requests.get(
            f"{GRAPH}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": short_lived_token,
            },
            timeout=30,
        )
        long_token_response.raise_for_status()
        long_lived_token = long_token_response.json()["access_token"]

        account = get_connected_instagram_account(long_lived_token)
        r = requests.get(
            f"{GRAPH}/{account['ig_user_id']}",
            params={"fields": "username", "access_token": account["page_access_token"]},
            timeout=30,
        )
        r.raise_for_status()
    except (requests.RequestException, RuntimeError, KeyError):
        app.logger.warning("Instagram connection failed during token or Page-account lookup.")
        return "Could not connect the Instagram account. Check the app credentials and Page link, then try again.", 400

    save_token(
        {
            "user_access_token": long_lived_token,
            "page_access_token": account["page_access_token"],
            "page_id": account["page_id"],
            "ig_user_id": account["ig_user_id"],
            "username": r.json().get("username", ""),
            "data_access_expires_at": long_token_response.json().get("data_access_expiration_time"),
        }
    )
    return redirect(url_for("home"))


@app.route("/generate", methods=["POST"])
def generate():
    token = load_token()
    if not token.get("page_access_token"):
        return redirect(url_for("home"))

    question = request.form.get("question", "").strip()
    if not question:
        return redirect(url_for("home"))

    short_answer, long_answer, hashtags = generate_answers(question)
    caption = build_caption(question, hashtags)
    draft_id = uuid.uuid4().hex[:12]
    paths = render_images(question, short_answer, long_answer, draft_id)

    image_urls = []
    try:
        image_urls = upload_to_storage(paths, draft_id)
    except Exception as exc:
        app.logger.warning("Supabase upload at generate failed: %s", exc)

    now = int(time.time())
    upsert_post(
        {
            "id": draft_id,
            "question": question,
            "short": short_answer,
            "long": long_answer,
            "caption": caption,
            "hashtags": hashtags,
            "status": "generated",
            "image_urls": image_urls,
            "local_images": paths,
            "permalink": None,
            "media_id": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    return redirect(url_for("preview", draft_id=draft_id))


@app.route("/preview/<draft_id>")
def preview(draft_id):
    draft = get_post(draft_id)
    if not draft:
        return "Draft not found.", 404
    return render_template("preview.html", draft=draft, draft_id=draft_id)


@app.route("/img/<draft_id>/<int:n>")
def image(draft_id, n):
    draft = get_post(draft_id)
    if not draft or n >= len(draft.get("local_images", [])):
        return "Not found", 404
    return send_file(draft["local_images"][n], mimetype="image/jpeg")


def publish_in_background(post_id):
    token = load_token()
    record = get_post(post_id)
    if not record:
        return
    if not token.get("page_access_token"):
        record["status"] = "failed"
        record["error"] = "Instagram is not linked."
        record["updated_at"] = int(time.time())
        upsert_post(record)
        return

    try:
        urls = record.get("image_urls") or upload_to_storage(record["local_images"], post_id)
        if not record.get("image_urls"):
            record["image_urls"] = urls
        caption = record.get("caption") or build_caption(
            record.get("question", ""),
            record.get("hashtags", []),
        )
        media_id = publish_carousel(
            token["ig_user_id"], urls, caption, token["page_access_token"]
        )
        comment_id = post_comment(
            media_id,
            build_comment(record.get("short", ""), record.get("long", "")),
            token["page_access_token"],
        )
        # Mark published as soon as Meta accepts the carousel — the permalink
        # resolves lazily and can lag behind the publish itself.
        record.update(
            {
                "status": "published",
                "media_id": media_id,
                "comment_id": comment_id,
                "permalink": None,
                "error": None,
                "updated_at": int(time.time()),
            }
        )
        # Persist "published" the moment media_publish succeeds. The post is
        # already live; don't let the permalink poll keep the row stuck in
        # "publishing".
        upsert_post(record)

        try:
            permalink = wait_for_permalink(media_id, token["page_access_token"], tries=40)
            if permalink:
                record["permalink"] = permalink
                record["updated_at"] = int(time.time())
                upsert_post(record)
        except Exception:
            pass
    except Exception as exc:
        record.update(
            {"status": "failed", "error": str(exc), "updated_at": int(time.time())}
        )
    upsert_post(record)


@app.route("/publish/<draft_id>", methods=["POST"])
def publish(draft_id):
    record = get_post(draft_id)
    if not record:
        return "Draft not found.", 404
    record["status"] = "publishing"
    record["updated_at"] = int(time.time())
    upsert_post(record)
    threading.Thread(target=publish_in_background, args=(draft_id,), daemon=True).start()
    return redirect(url_for("home"))


INSIGHT_METRICS = "likes,comments,shares,saved,reach,views,total_interactions"


def fetch_post_insights(media_id, page_access_token):
    r = requests.get(
        f"{GRAPH}/{media_id}/insights",
        params={"metric": INSIGHT_METRICS, "access_token": page_access_token},
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    out = {}
    for m in data.get("data", []):
        vals = m.get("values") or []
        if vals and isinstance(vals[0], dict) and "value" in vals[0]:
            out[m["name"]] = vals[0]["value"]
    return out


def _fmt(v):
    return str(v) if v is not None else "—"


def format_insights(raw):
    return {
        "views": _fmt(raw.get("views")),
        "likes": _fmt(raw.get("likes")),
        "comments": _fmt(raw.get("comments")),
        "shares": _fmt(raw.get("shares")),
        "saves": _fmt(raw.get("saved")),
        "reach": _fmt(raw.get("reach")),
    }


def repair_missing_permalinks():
    """Fill permalink for published posts where Meta hadn't returned it yet."""
    token = load_token()
    if not token.get("page_access_token"):
        return
    for p in load_posts():
        if p.get("status") == "published" and p.get("media_id") and not p.get("permalink"):
            try:
                pl = wait_for_permalink(p["media_id"], token["page_access_token"], tries=10)
                if pl:
                    p["permalink"] = pl
                    p["updated_at"] = int(time.time())
                    upsert_post(p)
            except Exception:
                pass


if __name__ == "__main__":
    threading.Thread(target=repair_missing_permalinks, daemon=True).start()
    app.run(debug=True, port=PORT)
