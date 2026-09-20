import os
import sqlite3
import time
import urllib.request
import webbrowser
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("DAILYBOOK_DATA_DIR") or
                Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "DailyBook")


def saved_port() -> int:
    database = data_dir() / "dailybook.db"
    if not database.exists():
        return 4000
    try:
        with sqlite3.connect(database, timeout=2) as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?", ("server_port",)
            ).fetchone()
        port = int(row[0]) if row and row[0] else 4000
        return port if 1024 <= port <= 65535 else 4000
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return 4000


def main():
    port = saved_port()
    url = f"http://127.0.0.1:{port}"
    for _ in range(20):
        try:
            urllib.request.urlopen(url, timeout=1).close()
            break
        except Exception:
            time.sleep(0.25)
    webbrowser.open(url)


if __name__ == "__main__":
    main()
