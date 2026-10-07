"""Entrypoint: start the Flask backend.

Usage:
    python run.py
"""
import threading

from backend.app import app, repair_missing_permalinks
from backend.config import PORT

if __name__ == "__main__":
    threading.Thread(target=repair_missing_permalinks, daemon=True).start()
    app.run(debug=True, port=PORT)
