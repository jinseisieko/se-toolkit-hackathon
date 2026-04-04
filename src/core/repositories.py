"""Repository pattern — data-access abstractions for the core layer.

Concrete implementations live in ``infrastructure/`` and wrap Peewee models.
This keeps ORM imports out of business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from peewee import Database  # type: ignore[import-untyped]


@dataclass
class Alert:
    """Plain data object — decoupled from any ORM."""

    id: Optional[int]
    ip: str
    attempts: int
    service: str
    first_seen: datetime
    last_seen: datetime
    blocked: bool


class AlertRepository(ABC):
    """Abstract contract for alert data access."""

    @abstractmethod
    def create(self, ip: str, attempts: int, service: str) -> Alert:
        """Persist a new alert and return it with an assigned ID."""
        ...

    @abstractmethod
    def get_recent(self, limit: int = 50) -> Sequence[Alert]:
        """Return the most recent alerts, newest first."""
        ...

    @abstractmethod
    def mark_blocked(self, alert_id: int) -> bool:
        """Set ``blocked=True`` on the alert.  Returns False if not found."""
        ...

    @abstractmethod
    def get_by_id(self, alert_id: int) -> Alert | None:
        """Fetch a single alert by ID."""
        ...


class PeeweeAlertRepository(AlertRepository):
    """Peewee-backed implementation of AlertRepository.

    Args:
        db: The Peewee Database instance (must already have models created).
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, ip: str, attempts: int, service: str) -> Alert:
        from src.infrastructure.models import Alert as AlertModel

        record = AlertModel.create(
            ip=ip,
            attempts=attempts,
            service=service,
        )
        return self._to_entity(record)

    def get_recent(self, limit: int = 50) -> Sequence[Alert]:
        from src.infrastructure.models import Alert as AlertModel

        query = (
            AlertModel.select()
            .order_by(AlertModel.last_seen.desc())
            .limit(limit)
        )
        return [self._to_entity(r) for r in query]

    def mark_blocked(self, alert_id: int) -> bool:
        from src.infrastructure.models import Alert as AlertModel

        updated: int = (
            AlertModel.update(blocked=True)
            .where(AlertModel.id == alert_id)
            .execute()
        )
        return bool(updated > 0)

    def get_by_id(self, alert_id: int) -> Alert | None:
        from src.infrastructure.models import Alert as AlertModel

        try:
            record = AlertModel.get_by_id(alert_id)
        except AlertModel.DoesNotExist:
            return None
        return self._to_entity(record)

    # ── Internal ──────────────────────────────────────────────

    @staticmethod
    def _to_entity(record: object) -> Alert:
        """Convert a Peewee model instance to a plain Alert entity."""
        from src.infrastructure.models import Alert as AlertModel

        m: AlertModel = record  # type: ignore[assignment]
        return Alert(
            id=m.id,
            ip=m.ip,
            attempts=m.attempts,
            service=m.service,
            first_seen=m.first_seen,
            last_seen=m.last_seen,
            blocked=m.blocked,
        )
