# 8. Flask Dashboard

**Pattern:** Application Factory  
**Files:** `src/interfaces/web/app.py`, `src/interfaces/web/templates/dashboard.html`, `src/static/style.css`  
**Tests:** `tests/unit/test_web_dashboard.py` (11 tests), `tests/unit/test_api_auth.py` (9 tests)

---

## Purpose

Serves the LogSentinel web dashboard — a real-time view of alerts and blocked IPs with a JSON API for polling.

---

## Routes

### Public (No Authentication)

| Route | Method | Response | Description |
|-------|--------|----------|-------------|
| `/` | GET | HTML | Main dashboard page |
| `/api/alerts` | GET | JSON | Recent 50 alerts |
| `/api/blocked` | GET | JSON | All blocked alerts |
| `/metrics` | GET | Plain text | Prometheus-format metrics (added by worker) |

### Authenticated (Bearer Token Required)

These routes are only available when `api_token` is set in `create_app()`.

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/api/block` | POST | `Authorization: Bearer <token>` | Block an IP address |
| `/api/unblock` | POST | `Authorization: Bearer <token>` | Unblock an IP address |

### Block/Unblock Request Format

```bash
curl -X POST http://localhost:5000/api/block \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"ip": "10.0.0.1", "reason": "manual block"}'
# → {"blocked": true, "ip": "10.0.0.1", "reason": "manual block", "message": "Blocked 10.0.0.1"}

curl -X POST http://localhost:5000/api/unblock \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"ip": "10.0.0.1"}'
# → {"blocked": false, "ip": "10.0.0.1", "message": "Unblocked 10.0.0.1"}
```

| Status | Meaning |
|--------|---------|
| 401 | No `Authorization` header or token missing |
| 403 | Token does not match the configured `api_token` |
| 200 | Success |
| 404 | `api_token` not configured (endpoints not registered) |

---

## JSON Response Format

```json
[
  {
    "id": 1,
    "ip": "192.0.2.1",
    "attempts": 5,
    "service": "ssh",
    "first_seen": "2026-04-04T12:00:00+00:00",
    "last_seen": "2026-04-04T12:00:30+00:00",
    "blocked": false
  }
]
```

---

## Dashboard Features

- **API Token input:** Password field with localStorage persistence; required for block/unblock actions.
- **Stats cards:** Total alerts, active count, blocked count.
- **Alerts table:** IP, attempts, service, last seen, status badge, and **Block/Unblock button** per row.
- **Blocked IPs section:** Dedicated table of blocked IPs with Unblock buttons.
- **Live polling:** JavaScript polls `/api/alerts` and `/api/blocked` every 10 seconds to update stats and tables.
- **Toast notifications:** Success/error toasts appear on block/unblock actions.
- **Empty state:** Shows "No alerts yet. Waiting for activity…" when the DB is empty.
- **Dark theme:** Uses CSS custom properties for easy theming.

---

## Application Factory

```python
from src.interfaces.web.app import create_app
from src.core.repositories import PeeweeAlertRepository

app = create_app(alert_repo=repo)
app.config["TESTING"] = True

with app.test_client() as client:
    resp = client.get("/api/alerts")
    data = resp.get_json()
```

---

## Running Standalone

```python
from src.interfaces.web.app import create_app

app = create_app(alert_repo=repo)
app.run(host="0.0.0.0", port=5000)
```

---

## Design Decisions

- **Polling over SSE/WebSockets (V1):** Simple polling every 10s is sufficient for V1. Server-Sent Events can be added in V2 without changing the API.
- **Injected repository:** The Flask app accepts an `AlertRepository` in its factory function, making it trivial to test with in-memory SQLite and swap databases in production.
- **Minimal template:** Jinja2 template with no JavaScript frameworks. Easy to extend with charts, timelines, or geo-IP maps in V2.
