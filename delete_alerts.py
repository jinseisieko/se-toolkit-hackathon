#!/usr/bin/env python3
"""Delete all alerts from the LogSentinel database."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from peewee import SqliteDatabase
from src.infrastructure.db import init_database
from src.infrastructure.models import Alert, BlockedIP


def delete_all_alerts(db_path: str = "data/sentinel.db", force: bool = False):
    """Delete all alerts and blocked IPs from the database."""
    db_path_obj = Path(db_path)
    
    if not db_path_obj.exists():
        print(f"Database file not found: {db_path_obj.absolute()}")
        sys.exit(1)
    
    db = SqliteDatabase(str(db_path_obj))
    init_database(db)
    
    # Count before deletion
    alert_count = Alert.select().count()
    blocked_count = BlockedIP.select().count()
    
    print(f"Found {alert_count} alert(s) and {blocked_count} blocked IP record(s)")
    
    if alert_count == 0 and blocked_count == 0:
        print("Nothing to delete.")
        return
    
    if not force:
        confirm = input("Delete all alerts and blocked IP records? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
    
    # Delete records
    with db.atomic():
        deleted_alerts = Alert.delete().execute()
        deleted_blocked = BlockedIP.delete().execute()
    
    print(f"Deleted {deleted_alerts} alert(s) and {deleted_blocked} blocked IP record(s)")
    print("Done.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Delete all alerts from LogSentinel database")
    parser.add_argument("db_path", nargs="?", default="data/sentinel.db", help="Path to SQLite database")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    delete_all_alerts(args.db_path, force=args.yes)
