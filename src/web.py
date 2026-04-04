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

from dotenv import load_dotenv
from peewee import SqliteDatabase

from src.core.repositories import PeeweeAlertRepository
from src.infrastructure.db import init_database
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

# ── Application factory ──────────────────────────────────────

os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
_db = SqliteDatabase(DB_PATH)
init_database(_db)
_repo = PeeweeAlertRepository(_db)

_app = create_app(alert_repo=_repo, api_token=API_TOKEN)


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
