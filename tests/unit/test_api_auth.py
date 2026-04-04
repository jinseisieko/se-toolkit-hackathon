"""Unit tests for API block/unblock endpoints with Bearer auth.

Covers:
- POST /api/block without auth → 401
- POST /api/block with wrong token → 403
- POST /api/block with valid token → 200, blocks IP
- POST /api/unblock without auth → 401
- POST /api/unblock with valid token → 200, unblocks IP
- GET endpoints remain unauthenticated
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
    app = create_app(alert_repo=alert_repo, api_token="test-secret-token")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Auth tests ────────────────────────────────────────────────


class TestApiBlockAuth:
    def test_block_without_auth_returns_401(self, client) -> None:
        resp = client.post("/api/block", json={"ip": "1.2.3.4"})
        assert resp.status_code == 401

    def test_block_with_wrong_token_returns_403(self, client) -> None:
        resp = client.post(
            "/api/block",
            json={"ip": "1.2.3.4"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403

    def test_block_with_valid_token(self, client) -> None:
        resp = client.post(
            "/api/block",
            json={"ip": "10.0.0.1", "reason": "manual"},
            headers={"Authorization": "Bearer test-secret-token"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ip"] == "10.0.0.1"


class TestApiUnblockAuth:
    def test_unblock_without_auth_returns_401(self, client) -> None:
        resp = client.post("/api/unblock", json={"ip": "1.2.3.4"})
        assert resp.status_code == 401

    def test_unblock_with_wrong_token_returns_403(self, client) -> None:
        resp = client.post(
            "/api/unblock",
            json={"ip": "1.2.3.4"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 403

    def test_unblock_with_valid_token(self, client) -> None:
        resp = client.post(
            "/api/unblock",
            json={"ip": "1.2.3.4"},
            headers={"Authorization": "Bearer test-secret-token"},
        )
        # Returns 200 even if IP not found (idempotent)
        assert resp.status_code in (200, 204)


class TestPublicEndpoints:
    def test_dashboard_no_auth_required(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200

    def test_alerts_api_no_auth_required(self, client) -> None:
        resp = client.get("/api/alerts")
        assert resp.status_code == 200

    def test_blocked_api_no_auth_required(self, client) -> None:
        resp = client.get("/api/blocked")
        assert resp.status_code == 200
