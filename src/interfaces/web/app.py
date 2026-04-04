"""Flask dashboard application.

Serves the LogSentinel web dashboard and JSON API for alert data.
Uses the Application Factory pattern for testability.

Authentication:
- GET endpoints (dashboard, /api/alerts, /api/blocked) are public.
- POST endpoints (/api/block, /api/unblock) require Bearer token
  via ``Authorization: Bearer <token>`` header.
"""

from __future__ import annotations

import hmac
import logging
from functools import wraps
from typing import Any, Dict, Optional, TYPE_CHECKING

from flask import Flask, jsonify, render_template, request

from src.core.repositories import Alert
from src.utils.validation import validate_ip

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


def _require_auth(api_token: str):
    """Decorator: abort with 401/403 if Bearer token is missing or wrong.

    Uses constant-time comparison to prevent timing attacks.
    Also checks Origin/Referer headers as basic CSRF protection.

    Args:
        api_token: The expected API token.

    Returns:
        A decorator that wraps a Flask view function.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "Missing Authorization header"}), 401

            token = auth[7:].strip()
            if not hmac.compare_digest(token, api_token):
                return jsonify({"error": "Invalid API token"}), 403

            # Basic CSRF: reject cross-origin POST/PUT/DELETE requests
            if request.method in ("POST", "PUT", "DELETE"):
                origin = request.headers.get("Origin", "")
                referer = request.headers.get("Referer", "")
                host = request.host
                if origin and host not in origin and host not in referer:
                    return jsonify({"error": "Cross-origin request rejected"}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator


def create_app(
    alert_repo: "PeeweeAlertRepository",
    api_token: Optional[str] = None,
) -> Flask:
    """Create and configure a Flask application.

    Args:
        alert_repo: The AlertRepository instance for querying data.
        api_token: Token for authenticating write operations.
            If None, block/unblock endpoints are disabled.

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
    app.config["api_token"] = api_token

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

    if api_token:
        @app.route("/api/block", methods=["POST"])
        @_require_auth(api_token)
        def api_block() -> Any:
            """Block an IP address. Requires Bearer token authentication."""
            if not request.is_json:
                return jsonify(
                    {"error": "Content-Type must be application/json"}
                ), 415

            data = request.get_json(silent=True) or {}
            ip = data.get("ip", "")
            if not ip:
                return jsonify({"error": "Missing 'ip' in request body"}), 400

            try:
                ip = validate_ip(ip)
            except Exception:
                return jsonify({"error": "Invalid IP address"}), 400

            reason = data.get("reason", "manual block via dashboard")
            if len(reason) > 255:
                reason = reason[:255]

            alert_repo.mark_ip_blocked(ip)
            return jsonify({
                "ip": ip,
                "reason": reason,
                "blocked": True,
                "message": f"Blocked {ip}",
            }), 200

        @app.route("/api/unblock", methods=["POST"])
        @_require_auth(api_token)
        def api_unblock() -> Any:
            """Unblock an IP address. Requires Bearer token authentication."""
            if not request.is_json:
                return jsonify(
                    {"error": "Content-Type must be application/json"}
                ), 415

            data = request.get_json(silent=True) or {}
            ip = data.get("ip", "")
            if not ip:
                return jsonify({"error": "Missing 'ip' in request body"}), 400

            try:
                ip = validate_ip(ip)
            except Exception:
                return jsonify({"error": "Invalid IP address"}), 400

            alert_repo.mark_ip_unblocked(ip)
            return jsonify({
                "ip": ip,
                "blocked": False,
                "message": f"Unblocked {ip}",
            }), 200

    return app
