"""Database initialisation helper.

Keeps Peewee setup isolated so repositories can inject the DB instance.
"""

from __future__ import annotations

from peewee import Database  # type: ignore[import-untyped]

from src.infrastructure.models import Alert, BlockedIP

_ALL_MODELS = [Alert, BlockedIP]


def init_database(db: Database) -> None:
    """Bind *db* to all models and create tables.

    Args:
        db: A Peewee Database instance (SQLite, PostgreSQL, …).
    """
    for model in _ALL_MODELS:
        model._meta.database = db

    db.connect()
    db.create_tables(_ALL_MODELS, safe=True)
