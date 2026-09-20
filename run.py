import os

from waitress import serve

from app import create_app
from app.server_config import resolve_server_port


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("DAILYBOOK_HOST", "0.0.0.0")
    port = resolve_server_port(app)
    print(f"DailyBook: http://127.0.0.1:{port}", flush=True)
    serve(app, host=host, port=port, threads=8)
