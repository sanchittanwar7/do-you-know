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
HEADER_SHORT = "Short answer"
HEADER_LONG = "Long answer"
HANDLE = "@do.you.know.7"

# --- Reel (video) rendering ---
REEL_W, REEL_H = 1080, 1920  # 9:16
REEL_FPS = int(os.getenv("REEL_FPS", "25"))
REEL_CROSSFADE = float(os.getenv("REEL_CROSSFADE", "0.5"))
# Per-slide durations (seconds): question, short answer, long answer.
REEL_QUESTION_SECONDS = float(os.getenv("REEL_QUESTION_SECONDS", "3"))
REEL_SHORT_SECONDS = float(os.getenv("REEL_SHORT_SECONDS", "3"))
REEL_LONG_SECONDS = float(os.getenv("REEL_LONG_SECONDS", "5"))
# Draining timer bar rendered below each slide's header (video/reel only).
# `REEL_TIMER_Y` is the top edge in slide-image coordinates (1080x1350); the
# video layer offsets it by the letterbox margin. `REEL_TIMER_WIDTH_FRACTION`
# controls how wide the bar is as a fraction of the slide width.
REEL_TIMER_HEIGHT = int(os.getenv("REEL_TIMER_HEIGHT", "18"))
REEL_TIMER_Y = int(os.getenv("REEL_TIMER_Y", "190"))
REEL_TIMER_WIDTH_FRACTION = float(os.getenv("REEL_TIMER_WIDTH_FRACTION", "0.5"))
# Path to an audio file (mp3/m4a/wav) to bake into the reel. Must be audio you
# own or are licensed to use; the IG API cannot attach licensed/trending music.
# If empty, a random track from REEL_AUDIO_DIR is used instead.
REEL_MUSIC_PATH = os.getenv("REEL_MUSIC_PATH", "").strip()
# Directory of background tracks; a random one is picked per reel. Relative to
# the project root unless an absolute path is given.
REEL_AUDIO_DIR = BASE_DIR / os.getenv("REEL_AUDIO_DIR", "media/reels/audio")
# Background music gain. 1.0 = original volume, 0.0 = silent. Default 0.3.
REEL_MUSIC_VOLUME = float(os.getenv("REEL_MUSIC_VOLUME", "0.3"))
REEL_SHARE_TO_FEED = os.getenv("REEL_SHARE_TO_FEED", "true").lower() == "true"

# 3 fixed visibility hashtags that ship with every caption.
FIXED_HASHTAGS = ["#doyouknow", "#facts", "#curious"]

# --- Frontend build served in production ---
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
