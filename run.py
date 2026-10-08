"""Entrypoint: start the Flask backend, daily scheduler, and Telegram bot.

Usage:
    python run.py
"""
import threading

from backend import scheduler, telegram_bot
from backend.app import app, repair_missing_permalinks
from backend.config import PORT

if __name__ == "__main__":
    threading.Thread(target=repair_missing_permalinks, daemon=True).start()
    scheduler.start()
    telegram_bot.start_polling()
    # debug=False avoids the Werkzeug reloader duplicating the background threads.
    app.run(debug=False, port=PORT)
