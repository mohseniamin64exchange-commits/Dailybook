import sqlite3

from windows import launcher


def test_launcher_uses_default_port_without_database(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "data_dir", lambda: tmp_path)
    assert launcher.saved_port() == 4000


def test_launcher_reads_saved_port(monkeypatch, tmp_path):
    database = tmp_path / "dailybook.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE settings (key TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("server_port", "4789"),
        )
    monkeypatch.setattr(launcher, "data_dir", lambda: tmp_path)
    assert launcher.saved_port() == 4789
