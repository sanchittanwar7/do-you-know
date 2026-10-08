"""Tiny daily scheduler that fires the approval job at a fixed local time."""
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config

_last_run_date = None


def start():
    if not config.SCHEDULE_ENABLED:
        return None
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread


def _run_if_due():
    global _last_run_date
    now = datetime.now(ZoneInfo(config.SCHEDULE_TZ))
    scheduled = now.replace(
        hour=config.SCHEDULE_HOUR,
        minute=config.SCHEDULE_MINUTE,
        second=0,
        microsecond=0,
    )
    if now < scheduled:
        return
    if _last_run_date == now.date():
        return
    _last_run_date = now.date()

    from . import jobs
    from . import telegram_bot

    try:
        jobs.create_approval(question=None, source="scheduled")
    except Exception as exc:
        telegram_bot.send_message(f"⚠️ Scheduled draft failed: {exc}")


def _loop():
    while True:
        try:
            _run_if_due()
        except Exception:
            pass
        time.sleep(20)
