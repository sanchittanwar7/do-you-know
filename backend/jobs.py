"""Approval workflow: generate → Telegram review → render + publish.

Kept separate from the Flask routes so it can be driven by the scheduler,
the Telegram bot callbacks, and the CLI in the same way.
"""
import time
import uuid

from . import deepseek
from . import imaging
from . import instagram
from . import storage
from . import supabase_store


def create_approval(question=None, source="manual"):
    """Create a pending approval. If no question given, generate one.

    Sends the question + short + long answer to Telegram for review.
    Returns the stored approval record.
    """
    if question is None:
        question = deepseek.generate_question()
    question = question.strip()
    if not question:
        raise RuntimeError("Empty question.")

    short_answer, long_answer, hashtags = deepseek.generate_answers(question)

    approval = {
        "id": uuid.uuid4().hex[:12],
        "question": question,
        "short": short_answer,
        "long": long_answer,
        "hashtags": hashtags,
        "status": "pending",
        "source": source,
        "post_id": None,
        "permalink": None,
        "error": None,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    storage.upsert_approval(approval)

    from . import telegram_bot  # lazy import to avoid a circular import

    telegram_bot.send_approval(approval)
    return approval


def reject_approval(approval_id):
    approval = storage.get_approval(approval_id)
    if not approval or approval.get("status") != "pending":
        return None
    approval["status"] = "rejected"
    approval["updated_at"] = int(time.time())
    storage.upsert_approval(approval)
    return approval


def approve_and_publish(approval_id):
    """Render images, upload, publish to IG, and record a published post."""
    approval = storage.get_approval(approval_id)
    if not approval or approval.get("status") != "pending":
        return None

    from . import telegram_bot  # lazy import to avoid a circular import

    approval["status"] = "publishing"
    approval["updated_at"] = int(time.time())
    storage.upsert_approval(approval)

    try:
        token = storage.load_token()
        if not token.get("page_access_token") or not token.get("ig_user_id"):
            raise RuntimeError("Instagram is not linked. Connect via the web app first.")

        paths = imaging.render_images(
            approval["question"], approval["short"], approval["long"], approval_id
        )
        urls = supabase_store.upload_to_storage(paths, approval_id)
        caption = deepseek.build_caption(
            approval["question"], approval.get("hashtags", [])
        )
        media_id = instagram.publish_carousel(
            token["ig_user_id"], urls, caption, token["page_access_token"]
        )
        comment_id = instagram.post_comment(
            media_id,
            deepseek.build_comment(approval["short"], approval["long"]),
            token["page_access_token"],
        )
        permalink = instagram.wait_for_permalink(
            media_id, token["page_access_token"], tries=40
        )

        now = int(time.time())
        post = {
            "id": approval_id,
            "question": approval["question"],
            "short": approval["short"],
            "long": approval["long"],
            "caption": caption,
            "hashtags": approval.get("hashtags", []),
            "status": "published",
            "image_urls": urls,
            "local_images": paths,
            "permalink": permalink,
            "media_id": media_id,
            "comment_id": comment_id,
            "error": None,
            "created_at": approval["created_at"],
            "updated_at": now,
        }
        storage.upsert_post(post)

        approval.update(
            {
                "status": "published",
                "post_id": approval_id,
                "permalink": permalink,
                "error": None,
                "updated_at": now,
            }
        )
        storage.upsert_approval(approval)

        telegram_bot.send_message(f"✅ Posted!\n{permalink or ''}")
        return approval
    except Exception as exc:
        approval["status"] = "failed"
        approval["error"] = str(exc)
        approval["updated_at"] = int(time.time())
        storage.upsert_approval(approval)
        telegram_bot.send_message(f"❌ Publish failed: {exc}")
        return approval
