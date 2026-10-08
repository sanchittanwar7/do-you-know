"""Central configuration loaded once from environment variables."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project root (parent of the backend/ package) so paths stay stable no matter
# where the process is started from.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Meta (Instagram Graph API) ---
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5001/callback")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5001"))
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCOPES = (
    "instagram_basic,instagram_content_publish,instagram_manage_comments,"
    "pages_show_list,pages_read_engagement,business_management,"
    "instagram_manage_insights"
)
META_PAGE_ID = os.getenv("META_PAGE_ID", "")
META_CONTENT_IS_AI_GENERATED = (
    os.getenv("META_CONTENT_IS_AI_GENERATED", "true").lower() == "true"
)

# --- DeepSeek ---
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# --- Supabase Storage (S3-compatible) ---
SUPABASE_KEY = os.getenv("SUPABASE_ACCESS_KEY_ID", "")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET_ACCESS_KEY", "")
SUPABASE_ENDPOINT = os.getenv("SUPABASE_ENDPOINT", "")
SUPABASE_REGION = os.getenv("SUPABASE_REGION", "us-east-1")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "")
SUPABASE_PUBLIC_BASE = os.getenv("SUPABASE_PUBLIC_BASE", "").rstrip("/")
IMG_KEY_PREFIX = "do-you-know"

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Scheduler (daily job) ---
SCHEDULE_ENABLED = os.getenv("SCHEDULE_ENABLED", "true").lower() == "true"
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "8"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))
SCHEDULE_TZ = os.getenv("SCHEDULE_TZ", "Asia/Kolkata")

# --- Flask ---
FLASK_SECRET = os.getenv("FLASK_SECRET", secrets.token_hex(16))

# --- Local persistence ---
TOKEN_FILE = BASE_DIR / "token.json"
POSTS_FILE = BASE_DIR / "posts.json"
APPROVALS_FILE = BASE_DIR / "approvals.json"
OUT_DIR = BASE_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

# --- Image rendering ---
IMG_W, IMG_H = 1080, 1350
BG = (253, 250, 239)  # warm cream
FG = (5, 5, 5)        # near-black
HEADER = "Do you know?"
HANDLE = "@do.you.know.7"

# 3 fixed visibility hashtags that ship with every caption.
FIXED_HASHTAGS = ["#doyouknow", "#facts", "#curious"]

# --- Frontend build served in production ---
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
