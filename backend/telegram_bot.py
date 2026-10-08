"""Telegram bot: long-polling review flow for draft approvals.

Runs in a background thread alongside Flask. Only the configured chat is
allowed to trigger commands or approve/reject drafts.
"""
import threading
import time

import requests

from . import config

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _url(method):
    return TELEGRAM_API.format(token=config.TELEGRAM_BOT_TOKEN) + "/" + method


def _post(method, payload):
    r = requests.post(_url(method), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def is_configured():
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


def send_message(text):
    """Send a plain message to the configured chat."""
    if not is_configured():
        return None
    try:
        data = _post("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID, "text": text})
        return data.get("result", {}).get("message_id")
    except requests.RequestException as exc:
        raise RuntimeError(f"Telegram send failed: {exc}") from exc


def send_approval(approval):
    """Send question + short + long answer with Approve/Reject buttons."""
    if not is_configured():
        return None
    text = (
        "🆕 New draft ready for review\n\n"
        f"❓ {approval['question']}\n\n"
        f"✳️ Short: {approval['short']}\n\n"
        f"📖 Long: {approval['long']}"
    )
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve & Post",
                    "callback_data": f"approve:{approval['id']}",
                },
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject:{approval['id']}",
                },
            ]
        ]
    }
    _post(
        "sendMessage",
        {"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "reply_markup": keyboard},
    )


def _answer_callback(callback_query_id, text):
    try:
        _post("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
    except requests.RequestException:
        pass


def _handle_command(text):
    from . import jobs

    if text == "/daily":
        jobs.create_approval(question=None, source="scheduled")
    elif text.startswith("/ask"):
        question = text[4:].strip()
        if not question:
            send_message("Usage: /ask <question>")
            return
        jobs.create_approval(question=question, source="manual")
    elif text == "/start" or text == "/help":
        send_message(
            "/daily — create today's draft from a generated question\n"
            "/ask <question> — create a draft from your question"
        )


def _normalize_chat_id(value):
    """Compare chat ids as ints; Telegram accepts leading digits + junk when
    sending, but callback/message chat ids are always clean ints."""
    s = str(value).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits or s


def _handle_update(update):
    from . import jobs

    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = (cq.get("message", {}).get("chat", {}) or {}).get("id", "")
        if _normalize_chat_id(chat_id) != _normalize_chat_id(config.TELEGRAM_CHAT_ID):
            return
        data = cq.get("data", "")
        if data.startswith("approve:"):
            approval_id = data.split(":", 1)[1]
            jobs.approve_and_publish(approval_id)
            _answer_callback(cq["id"], "Approved — creating images and posting.")
        elif data.startswith("reject:"):
            approval_id = data.split(":", 1)[1]
            approval = jobs.reject_approval(approval_id)
            if approval:
                send_message(f"❌ Rejected: {approval['question']}")
            _answer_callback(cq["id"], "Rejected.")
        return

    if "message" in update:
        msg = update["message"]
        chat_id = (msg.get("chat", {}) or {}).get("id", "")
        if _normalize_chat_id(chat_id) != _normalize_chat_id(config.TELEGRAM_CHAT_ID):
            return
        text = (msg.get("text") or "").strip()
        if text.startswith("/"):
            try:
                _handle_command(text)
            except Exception as exc:
                send_message(f"⚠️ Command failed: {exc}")


def start_polling():
    if not is_configured():
        return None
    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()
    return thread


def _poll_loop():
    offset = 0
    while True:
        try:
            r = requests.get(
                _url("getUpdates"),
                params={"timeout": 30, "offset": offset},
                timeout=60,
            )
            r.raise_for_status()
            updates = r.json().get("result", [])
            for update in updates:
                offset = max(offset, update["update_id"] + 1)
                try:
                    _handle_update(update)
                except Exception as exc:
                    send_message(f"⚠️ Update handling failed: {exc}")
        except requests.RequestException:
            time.sleep(5)
