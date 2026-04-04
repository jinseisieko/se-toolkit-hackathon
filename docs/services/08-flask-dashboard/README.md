# 8. Flask Dashboard

**Pattern:** Application Factory  
**Files:** `src/interfaces/web/app.py`, `src/interfaces/web/templates/dashboard.html`, `src/static/style.css`  
**Tests:** `tests/unit/test_web_dashboard.py` (7 tests)

---

## Purpose

Serves the LogSentinel web dashboard — a real-time view of alerts and blocked IPs with a JSON API for polling.

---

## Routes

| Route | Method | Response | Description |
|-------|--------|----------|-------------|
| `/` | GET | HTML | Main dashboard page |
| `/api/alerts` | GET | JSON | Recent 50 alerts |
| `/api/blocked` | GET | JSON | All blocked alerts |

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

- **Stats cards:** Total alerts, active count, blocked count.
- **Alerts table:** IP, attempts, service, last seen, status badge (Active/Blocked).
- **Live polling:** JavaScript polls `/api/alerts` every 10 seconds to update stat counters.
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
