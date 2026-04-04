# 1. EventBroker + SecurityEvent

**Pattern:** Observer  
**File:** `src/core/events.py`  
**Tests:** `tests/unit/test_events.py` (6 tests)

---

## Purpose

Decouples event producers (log parser, detector) from consumers (alert service, block service, Telegram alerts). Any component can publish a `SecurityEvent` and any number of subscribers react to it without knowing each other.

---

## SecurityEvent

A frozen dataclass representing a detected security incident.

| Field | Type | Description |
|-------|------|-------------|
| `ip` | `str` | Source IP address of the attacker |
| `attempt_count` | `int` | Number of failed attempts that triggered this event |
| `timestamp` | `datetime` | When the event was created (UTC) |
| `log_line` | `str` | The raw log line that contributed to detection |
| `service` | `str` | Service name, e.g. `"ssh"`, `"http"` |

---

## EventBroker API

```python
broker = EventBroker()

# Subscribe a handler — called for every published event
broker.subscribe(handler: Callable[[SecurityEvent], None])

# Dispatch an event to all subscribers
broker.publish(event: SecurityEvent)
```

---

## Behavior

- Handlers are called synchronously in subscription order.
- If a handler raises an exception, it is logged at ERROR level and the broker continues with the next handler.
- Publishing with no subscribers is a no-op (safe).
- The same handler can be subscribed multiple times (fires once per subscription).

---

## Design Decisions

- **No async queue (V1):** Synchronous delivery keeps the system simple and predictable. A queue-based approach can be added later by wrapping the broker.
- **No unsubscribe (V1):** Handlers are registered at startup and live for the process lifetime. Unsubscribe can be added if dynamic plugin loading is needed.

---

## Example

```python
from src.core.events import EventBroker, SecurityEvent
from datetime import datetime, timezone

broker = EventBroker()

def alert_handler(event: SecurityEvent) -> None:
    print(f"ALERT: {event.ip} — {event.attempt_count} attempts")

broker.subscribe(alert_handler)

event = SecurityEvent(
    ip="192.0.2.1",
    attempt_count=5,
    timestamp=datetime.now(timezone.utc),
    log_line="Failed password for root from 192.0.2.1",
    service="ssh",
)

broker.publish(event)  # → "ALERT: 192.0.2.1 — 5 attempts"
```
