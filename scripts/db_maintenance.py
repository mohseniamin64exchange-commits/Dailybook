import argparse
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app.services.backup import create_backup, restore_backup


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--destination", default=str(PROJECT_DIR / "backups"))
    restore = sub.add_parser("restore")
    restore.add_argument("backup_file")
    args = parser.parse_args()
    database_uri = f"sqlite:///{(PROJECT_DIR / 'instance' / 'dailybook.db').as_posix()}"
    if args.command == "backup":
        result = create_backup(database_uri, args.destination, PROJECT_DIR / "backups")
        print(result["path"])
    else:
        print(restore_backup(args.backup_file, database_uri))


if __name__ == "__main__":
    main()
