"""Unit tests for PeeweeAlertRepository with real in-memory SQLite.

Covers:
- create / get_recent returns inserted alerts
- get_recent respects limit and orders by newest first
- mark_blocked returns False for non-existent ID
- Empty DB returns empty sequence
"""

from __future__ import annotations

import pytest
from peewee import SqliteDatabase

from src.infrastructure.db import init_database
from src.core.repositories import PeeweeAlertRepository


@pytest.fixture
def db() -> SqliteDatabase:
    """In-memory SQLite database — no disk I/O."""
    return SqliteDatabase(":memory:")


@pytest.fixture
def repo(db: SqliteDatabase) -> PeeweeAlertRepository:
    init_database(db)
    return PeeweeAlertRepository(db)


# ── Happy path ────────────────────────────────────────────────


class TestPeeweeAlertRepositoryHappyPath:
    def test_create_and_get_recent(self, repo: PeeweeAlertRepository) -> None:
        repo.create(ip="192.0.2.1", attempts=5, service="ssh")

        alerts = repo.get_recent()
        assert len(alerts) == 1
        assert alerts[0].ip == "192.0.2.1"
        assert alerts[0].attempts == 5
        assert alerts[0].service == "ssh"
        assert alerts[0].blocked is False

    def test_get_recent_respects_limit(self, repo: PeeweeAlertRepository) -> None:
        for i in range(10):
            repo.create(ip=f"10.0.0.{i}", attempts=5, service="ssh")

        alerts = repo.get_recent(limit=3)
        assert len(alerts) == 3

    def test_get_recent_orders_by_newest_first(
        self, repo: PeeweeAlertRepository
    ) -> None:
        repo.create(ip="1.1.1.1", attempts=3, service="ssh")
        repo.create(ip="2.2.2.2", attempts=5, service="http")

        alerts = repo.get_recent()
        assert alerts[0].ip == "2.2.2.2"  # inserted last
        assert alerts[1].ip == "1.1.1.1"

    def test_mark_blocked_sets_flag(self, repo: PeeweeAlertRepository) -> None:
        alert = repo.create(ip="192.0.2.1", attempts=5, service="ssh")
        assert alert.blocked is False

        result = repo.mark_blocked(alert.id)
        assert result is True

        # Verify persistence
        fetched = repo.get_by_id(alert.id)
        assert fetched is not None
        assert fetched.blocked is True


# ── Edge cases ────────────────────────────────────────────────


class TestPeeweeAlertRepositoryEdgeCases:
    def test_empty_db_returns_empty_sequence(
        self, repo: PeeweeAlertRepository
    ) -> None:
        assert list(repo.get_recent()) == []

    def test_limit_larger_than_dataset_returns_all(
        self, repo: PeeweeAlertRepository
    ) -> None:
        repo.create(ip="1.1.1.1", attempts=1, service="ssh")
        alerts = repo.get_recent(limit=100)
        assert len(alerts) == 1

    def test_mark_blocked_nonexistent_id_returns_false(
        self, repo: PeeweeAlertRepository
    ) -> None:
        assert repo.mark_blocked(99999) is False

    def test_get_by_id_returns_none_for_missing(
        self, repo: PeeweeAlertRepository
    ) -> None:
        assert repo.get_by_id(42) is None
