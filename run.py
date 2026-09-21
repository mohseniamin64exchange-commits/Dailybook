import os

from waitress import serve

from app import create_app
from app.server_config import configure_windows_firewall, resolve_server_port


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("DAILYBOOK_HOST", "0.0.0.0")
    port = resolve_server_port(app)
    # Keep the Windows firewall rule aligned with the saved port on every service start.
    if os.name == "nt" and os.environ.get("DAILYBOOK_SERVICE_MODE") == "1":
        try:
            configure_windows_firewall(port)
        except OSError as exc:
            print(f"DailyBook firewall update failed: {exc}", flush=True)
    print(f"DailyBook: http://127.0.0.1:{port}", flush=True)
    serve(app, host=host, port=port, threads=8)

