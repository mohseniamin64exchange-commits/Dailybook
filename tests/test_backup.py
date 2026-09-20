import sqlite3

from app.services.backup import create_backup, restore_backup


def test_backup_falls_back_when_preferred_directory_fails(tmp_path):
    database = tmp_path / "source.db"
    with sqlite3.connect(database) as conn:
        conn.execute("create table marker (value text)")
        conn.execute("insert into marker values ('ok')")

    preferred = tmp_path / "preferred-file"
    preferred.write_text("not a directory")
    fallback = tmp_path / "fallback"
    result = create_backup(f"sqlite:///{database}", preferred, fallback)

    assert result["used_fallback"] is True
    assert result["path"].parent == fallback
    assert result["path"].exists()


def test_restore_backup_replaces_database(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    target = tmp_path / "target.db"
    with sqlite3.connect(source) as conn:
        conn.execute("create table marker (value text)")
        conn.execute("insert into marker values ('restored')")
    with sqlite3.connect(backup) as conn:
        conn.execute("create table marker (value text)")
        conn.execute("insert into marker values ('backup')")

    result = restore_backup(backup, f"sqlite:///{target}")
    assert result == target
    with sqlite3.connect(target) as conn:
        assert conn.execute("select value from marker").fetchone()[0] == "backup"
