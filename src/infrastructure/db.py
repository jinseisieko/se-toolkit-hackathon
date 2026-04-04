"""Database initialisation helper.

Keeps Peewee setup isolated so repositories can inject the DB instance.
"""

from __future__ import annotations

from peewee import Database  # type: ignore[import-untyped]

from src.infrastructure.models import Alert, BlockedIP

_ALL_MODELS = [Alert, BlockedIP]


def init_database(db: Database) -> None:
    """Bind *db* to all models and create tables.

    For SQLite, enables WAL mode to allow concurrent readers
    with a single writer (multi-process access).

    Args:
        db: A Peewee Database instance (SQLite, PostgreSQL, …).
    """
    for model in _ALL_MODELS:
        model._meta.database = db

    db.connect()

    # Enable WAL mode for SQLite — allows concurrent readers + single writer
    if db.__class__.__name__ == "SqliteDatabase":
        db.execute_sql("PRAGMA journal_mode=WAL")

    db.create_tables(_ALL_MODELS, safe=True)
