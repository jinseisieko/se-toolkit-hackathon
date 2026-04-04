"""Unit tests for Flask dashboard.

Covers:
- GET / renders dashboard HTML with alert count
- GET /api/alerts returns JSON list of alerts
- GET /api/blocked returns JSON list of blocked IPs
- Empty DB renders with zero counts
- Dashboard template receives correct context
"""

from __future__ import annotations

import pytest
from peewee import SqliteDatabase

from src.infrastructure.db import init_database
from src.core.repositories import PeeweeAlertRepository
from src.interfaces.web.app import create_app


@pytest.fixture
def db() -> SqliteDatabase:
    return SqliteDatabase(":memory:")


@pytest.fixture
def alert_repo(db: SqliteDatabase) -> PeeweeAlertRepository:
    init_database(db)
    return PeeweeAlertRepository(db)


@pytest.fixture
def client(alert_repo: PeeweeAlertRepository):
    app = create_app(alert_repo=alert_repo)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Happy path ────────────────────────────────────────────────


class TestDashboardHappyPath:
    def test_root_renders_dashboard(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"LogSentinel" in resp.data

    def test_api_alerts_returns_json(self, client, alert_repo) -> None:
        alert_repo.create(ip="192.0.2.1", attempts=5, service="ssh")

        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["ip"] == "192.0.2.1"
        assert data[0]["attempts"] == 5

    def test_api_blocked_returns_json(self, client, alert_repo) -> None:
        alert = alert_repo.create(ip="10.0.0.1", attempts=3, service="ssh")
        alert_repo.mark_blocked(alert.id)

        resp = client.get("/api/blocked")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["ip"] == "10.0.0.1"
        assert data[0]["blocked"] is True


# ── Edge cases ────────────────────────────────────────────────


class TestDashboardEdgeCases:
    def test_empty_dashboard_shows_zeroes(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        # Template context should contain empty alerts list
        assert b"0 alerts" in resp.data or b"No alerts" in resp.data

    def test_api_alerts_empty_db(self, client) -> None:
        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_api_alerts_respects_limit(self, client, alert_repo) -> None:
        for i in range(60):
            alert_repo.create(ip=f"10.0.{i}.1", attempts=5, service="ssh")

        resp = client.get("/api/alerts")
        data = resp.get_json()
        assert len(data) == 50  # default limit

    def test_api_blocked_empty(self, client) -> None:
        resp = client.get("/api/blocked")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ── Dashboard UI: Token input + block/unblock buttons ─────────


class TestDashboardUI:
    def test_dashboard_has_token_input(self, client) -> None:
        resp = client.get("/")
        html = resp.data.decode()
        assert 'id="api-token"' in html or "api-token" in html

    def test_dashboard_has_block_buttons(self, client, alert_repo) -> None:
        alert_repo.create(ip="192.0.2.1", attempts=5, service="ssh")
        alert_repo.create(ip="10.0.0.1", attempts=3, service="ssh")
        alert_repo.mark_blocked(2)

        resp = client.get("/")
        html = resp.data.decode()
        # Each row should have a block or unblock button
        assert "btn-block" in html or "block-btn" in html
        assert "btn-unblock" in html or "unblock-btn" in html

    def test_blocked_ips_section(self, client, alert_repo) -> None:
        alert = alert_repo.create(ip="10.0.0.1", attempts=3, service="ssh")
        alert_repo.mark_blocked(alert.id)

        resp = client.get("/")
        html = resp.data.decode()
        assert "Blocked" in html or "blocked" in html

    def test_block_unblock_endpoints_return_message(
        self, client, alert_repo
    ) -> None:
        app = create_app(alert_repo=alert_repo, api_token="test-token")
        app.config["TESTING"] = True

        with app.test_client() as c:
            resp = c.post(
                "/api/block",
                json={"ip": "1.2.3.4", "reason": "test"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["message"] == "Blocked 1.2.3.4"

            resp = c.post(
                "/api/unblock",
                json={"ip": "1.2.3.4"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["message"] == "Unblocked 1.2.3.4"
