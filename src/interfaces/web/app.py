"""Flask dashboard application.

Serves the LogSentinel web dashboard and JSON API for alert data.
Uses the Application Factory pattern for testability.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, TYPE_CHECKING

from flask import Flask, jsonify, render_template

from src.core.repositories import Alert

if TYPE_CHECKING:
    from src.core.repositories import PeeweeAlertRepository

logger = logging.getLogger(__name__)


def _alert_to_dict(alert: Alert) -> Dict[str, Any]:
    """Convert an Alert dataclass to a JSON-serialisable dict."""
    return {
        "id": alert.id,
        "ip": alert.ip,
        "attempts": alert.attempts,
        "service": alert.service,
        "first_seen": alert.first_seen.isoformat() if alert.first_seen else "",
        "last_seen": alert.last_seen.isoformat() if alert.last_seen else "",
        "blocked": alert.blocked,
    }


def create_app(alert_repo: "PeeweeAlertRepository") -> Flask:
    """Create and configure a Flask application.

    Args:
        alert_repo: The AlertRepository instance for querying data.

    Returns:
        A configured Flask application.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="../../static",
        static_url_path="/static",
    )
    app.config["alert_repo"] = alert_repo

    @app.route("/")
    def dashboard() -> str:
        """Render the main dashboard page."""
        alerts = alert_repo.get_recent(limit=50)
        active = sum(1 for a in alerts if not a.blocked)
        blocked = sum(1 for a in alerts if a.blocked)

        return render_template(
            "dashboard.html",
            alerts=alerts,
            active_count=active,
            blocked_count=blocked,
            total_count=len(alerts),
        )

    @app.route("/api/alerts")
    def api_alerts() -> Any:
        """Return recent alerts as JSON."""
        alerts = alert_repo.get_recent(limit=50)
        return jsonify([_alert_to_dict(a) for a in alerts])

    @app.route("/api/blocked")
    def api_blocked() -> Any:
        """Return blocked alerts as JSON."""
        alerts = alert_repo.get_recent(limit=200)
        blocked = [a for a in alerts if a.blocked]
        return jsonify([_alert_to_dict(a) for a in blocked])

    return app
