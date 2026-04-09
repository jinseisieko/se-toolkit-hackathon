"""LogSentinel web service — standalone Flask entrypoint.

Serves the dashboard HTML, JSON API, Prometheus metrics, and
authenticated block/unblock endpoints.  Reads from the shared
SQLite database written to by the worker service.

Usage:
    python -m src.web              # development
    gunicorn src.web:app -b 0.0.0.0:5000  # production
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from peewee import SqliteDatabase

from src.adapters.firewall.noop import NoOpStrategy
from src.adapters.firewall.ufw import UFWStrategy
from src.core.blocking import FirewallStrategy
from src.core.repositories import PeeweeAlertRepository
from src.core.services.block_service import BlockRepository, BlockService
from src.infrastructure.db import init_database
from src.infrastructure.models import BlockedIP
from src.interfaces.web.app import create_app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ── Configuration ────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "data/sentinel.db")
API_TOKEN = os.getenv("API_TOKEN") or None
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
FIREWALL_STRATEGY = os.getenv("FIREWALL_STRATEGY", "noop")

# ── BlockRepository (Peewee-backed) ──────────────────────────


class PeeweeBlockRepo(BlockRepository):
    """Production BlockRepository backed by Peewee BlockedIP model."""

    def create(self, ip: str, reason: str, strategy: str) -> object:
        from src.core.services.block_service import BlockedIPRecord

        record = BlockedIP.create(
            ip=ip,
            reason=reason,
            strategy=strategy,
            blocked_at=datetime.now(timezone.utc),
        )
        return BlockedIPRecord(
            id=record.id,
            ip=record.ip,
            blocked_at=record.blocked_at,
            reason=record.reason,
            strategy=record.strategy,
            is_blocked=record.is_blocked,
        )

    def get_by_ip(self, ip: str):  # type: ignore[override]
        from src.core.services.block_service import BlockedIPRecord

        try:
            rec = BlockedIP.get(BlockedIP.ip == ip)
        except BlockedIP.DoesNotExist:
            return None
        return BlockedIPRecord(
            id=rec.id,
            ip=rec.ip,
            blocked_at=rec.blocked_at,
            reason=rec.reason,
            strategy=rec.strategy,
            is_blocked=rec.is_blocked,
        )

    def mark_blocked(self, record_id: int) -> bool:
        return (
            BlockedIP.update(is_blocked=True)
            .where(BlockedIP.id == record_id)
            .execute()
            > 0
        )

    def mark_unblocked(self, record_id: int) -> bool:
        return (
            BlockedIP.update(is_blocked=False)
            .where(BlockedIP.id == record_id)
            .execute()
            > 0
        )


# ── Application factory ──────────────────────────────────────

os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
_db = SqliteDatabase(DB_PATH)
init_database(_db)
_repo = PeeweeAlertRepository(_db)

# Firewall strategy (same config as worker)
_strategy: FirewallStrategy
if FIREWALL_STRATEGY == "ufw":
    _strategy = UFWStrategy()
    logging.getLogger(__name__).info(
        "Web: Firewall strategy = UFW (production)"
    )
else:
    _strategy = NoOpStrategy()
    logging.getLogger(__name__).info(
        "Web: Firewall strategy = NoOp (test mode)"
    )

_block_svc = BlockService(
    strategy=_strategy, repo=PeeweeBlockRepo()
)

_app = create_app(
    alert_repo=_repo, api_token=API_TOKEN, block_service=_block_svc
)


@_app.route("/metrics")
def _metrics_endpoint():  # type: ignore[no-untyped-def]
    """Prometheus-format metrics read from shared file."""
    from flask import Response
    import os as _os
    metrics_file = _os.path.join(
        _os.path.dirname(DB_PATH) or ".", "metrics.prom"
    )
    try:
        with open(metrics_file) as f:
            content = f.read()
        if content.strip():
            return Response(content, mimetype="text/plain")
    except FileNotFoundError:
        pass
    return Response("# no metrics available\n", mimetype="text/plain")


app = _app  # gunicorn-compatible WSGI entry point


def main() -> None:
    """CLI entry point."""
    _app.run(host=WEB_HOST, port=WEB_PORT, use_reloader=False)


if __name__ == "__main__":
    main()
