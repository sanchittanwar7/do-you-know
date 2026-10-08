"""Instagram post insights fetching and formatting."""
import requests

from .config import GRAPH

INSIGHT_METRICS = "likes,comments,shares,saved,reach,views,total_interactions"


class MediaNotFoundError(RuntimeError):
    """Raised when Instagram reports the media no longer exists."""


def _is_not_found(error):
    subcode = error.get("error_subcode")
    if subcode in (33, 803):
        return True
    message = str(error.get("message", "")).lower()
    return any(
        phrase in message
        for phrase in ("deleted", "does not exist", "not found", "no longer available")
    )


def fetch_post_insights(media_id, page_access_token):
    r = requests.get(
        f"{GRAPH}/{media_id}/insights",
        params={"metric": INSIGHT_METRICS, "access_token": page_access_token},
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        error = data["error"]
        if _is_not_found(error):
            raise MediaNotFoundError(error.get("message", str(error)))
        raise RuntimeError(error.get("message", str(error)))
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
