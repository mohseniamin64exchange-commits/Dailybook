import os
import subprocess


MIN_PORT = 1024
MAX_PORT = 65535
FIREWALL_RULE_NAME = "DailyBook Server"
WINDOWS_SERVICE_NAME = "DailyBook"


def validate_port(value) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("پورت باید یک عدد صحیح باشد.") from None
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError("پورت باید بین ۱۰۲۴ و ۶۵۵۳۵ باشد.")
    return port


def resolve_server_port(app) -> int:
    """Resolve startup port; environment override wins over saved UI value."""
    environment_port = os.environ.get("DAILYBOOK_PORT")
    if environment_port:
        return validate_port(environment_port)

    from .models import Setting

    with app.app_context():
        setting = Setting.query.filter_by(key="server_port").first()
        if setting and setting.value:
            try:
                return validate_port(setting.value)
            except ValueError:
                app.logger.warning("Invalid saved server port; using the default port.")
        return validate_port(app.config.get("DEFAULT_PORT", 4000))


def configure_windows_firewall(port: int) -> None:
    """Keep the private/domain Windows firewall rule aligned with the saved port."""
    if os.name != "nt":
        return
    port = validate_port(port)
    subprocess.run(
        ["netsh", "advfirewall", "firewall", "delete", "rule",
         f"name={FIREWALL_RULE_NAME}"],
        check=False,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "add", "rule",
         f"name={FIREWALL_RULE_NAME}", "dir=in", "action=allow",
         "protocol=TCP", f"localport={port}", "profile=private,domain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or result.stdout.strip() or
                      "به‌روزرسانی فایروال ویندوز ناموفق بود.")



def configure_windows_service_autostart(enabled: bool) -> bool:
    """Set the installed DailyBook Windows service to Automatic or Manual startup."""
    if os.name != "nt" or os.environ.get("DAILYBOOK_SERVICE_MODE") != "1":
        return False
    start_mode = "auto" if enabled else "demand"
    result = subprocess.run(
        ["sc.exe", "config", WINDOWS_SERVICE_NAME, "start=", start_mode],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or result.stdout.strip() or
                      "تغییر حالت اجرای خودکار سرویس ویندوز ناموفق بود.")
    return True

def schedule_windows_service_restart() -> bool:
    """Restart the installed service after the current response has completed."""
    if os.name != "nt" or os.environ.get("DAILYBOOK_SERVICE_MODE") != "1":
        return False
    command = (
        "timeout /t 4 /nobreak >nul & "
        f'sc.exe stop "{WINDOWS_SERVICE_NAME}" >nul & '
        "timeout /t 2 /nobreak >nul & "
        f'sc.exe start "{WINDOWS_SERVICE_NAME}" >nul'
    )
    creation_flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
    )
    try:
        subprocess.Popen(
            ["cmd.exe", "/d", "/s", "/c", command],
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError:
        return False
    return True
