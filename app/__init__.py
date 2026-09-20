from pathlib import Path
import secrets

from flask import Flask, redirect, request, url_for

from config import Config
from .extensions import csrf, db, login_manager


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    data_dir = Path(app.config.get("DATA_DIR", app.instance_path))
    data_dir.mkdir(parents=True, exist_ok=True)
    if not app.config.get("SECRET_KEY"):
        secret_file = data_dir / "secret.key"
        if secret_file.exists():
            app.config["SECRET_KEY"] = secret_file.read_text(encoding="utf-8").strip()
        else:
            app.config["SECRET_KEY"] = secrets.token_urlsafe(48)
            secret_file.write_text(app.config["SECRET_KEY"], encoding="utf-8")
            try:
                secret_file.chmod(0o600)
            except OSError:
                pass
    Path(app.config["DEFAULT_BACKUP_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "لطفاً ابتدا وارد شوید."

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .auth import auth_bp
    from .entries import entries_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(entries_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def ui_context():
        # The full management sidebar belongs to the server console only.
        # Normal LAN clients, even when signed in with an admin account, keep
        # the compact no-sidebar shell. The server shortcut opens localhost.
        remote_addr = (request.remote_addr or "").split("%", 1)[0]
        is_server_console = remote_addr in {"127.0.0.1", "::1"}
        return {"is_server_console": is_server_console}

    @app.get("/")
    def index():
        if not User.query.first():
            return redirect(url_for("auth.setup_admin"))
        return redirect(url_for("entries.dashboard"))

    with app.app_context():
        db.create_all()
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
            with db.engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.exec_driver_sql("PRAGMA busy_timeout=30000")
                connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    @app.before_request
    def daily_backup_check():
        from datetime import datetime, timezone
        from .services.backup import run_daily_auto_backup

        today = datetime.now(timezone.utc).date().isoformat()
        if app.extensions.get("dailybook_backup_checked") != today:
            result = run_daily_auto_backup(app)
            if result is not None:
                app.extensions["dailybook_backup_checked"] = today

    return app
