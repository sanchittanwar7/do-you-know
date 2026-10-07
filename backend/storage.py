"""File-based persistence for the OAuth token and generated posts."""
import json
import threading

from .config import POSTS_FILE, TOKEN_FILE

_posts_lock = threading.Lock()

# View-model fields computed per-request; never persisted into posts.json.
_VIEW_FIELDS = {"media_link", "stats", "insights_error"}


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


def persist_post(record):
    upsert_post({k: v for k, v in record.items() if k not in _VIEW_FIELDS})


def get_post(post_id):
    for p in load_posts():
        if p.get("id") == post_id:
            return p
    return None
