"""Peewee database models for LogSentinel.

Models live here — the Repository layer (core/repositories.py) wraps them
to keep ORM imports out of business logic.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict

from peewee import (  # type: ignore[import-untyped]
    BooleanField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
)


class BaseModel(Model):  # type: ignore[misc]
    """Shared base — allows swapping the database at runtime."""

    class Meta:
        database: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise model to a plain dict (useful for JSON APIs)."""
        return {
            field_name: getattr(self, field_name)
            for field_name in self._meta.sorted_field_names
            if field_name != "id"
        }


class Alert(BaseModel):
    """A detected brute-force alert."""

    ip = CharField()
    attempts = IntegerField()
    service = CharField(default="ssh")
    first_seen = DateTimeField(default=datetime.datetime.now)
    last_seen = DateTimeField(default=datetime.datetime.now)
    blocked = BooleanField(default=False)

    class Meta:
        table_name = "alerts"
        indexes = ((("ip",), False),)


class BlockedIP(BaseModel):
    """A record of a blocked IP address."""

    ip = CharField(unique=True)
    blocked_at = DateTimeField(default=datetime.datetime.now)
    reason = CharField()
    strategy = CharField()
    is_blocked = BooleanField(default=True)

    class Meta:
        table_name = "blocked_ips"
