"""Start HireLens AI: FastAPI dashboard + Telegram bot.

Usage:
  python run.py              # API + bot together
  python run.py --api        # FastAPI only
  python run.py --bot        # Telegram only
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def run_api() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8080, reload=False)


def run_bot() -> None:
    from backend.telegram_bot import run_bot as start_polling

    start_polling()


def main() -> None:
    parser = argparse.ArgumentParser(description="HireLens AI")
    parser.add_argument("--api", action="store_true", help="Run FastAPI only")
    parser.add_argument("--bot", action="store_true", help="Run Telegram bot only")
    args = parser.parse_args()

    if args.api:
        run_api()
        return
    if args.bot:
        run_bot()
        return

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    try:
        run_bot()
    except RuntimeError as exc:
        print(exc)
        print("FastAPI is still running at http://127.0.0.1:8080")
        api_thread.join()


if __name__ == "__main__":
    main()
