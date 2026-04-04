# 2. ThresholdDetector

**Pattern:** Aggregator + Observer publisher  
**File:** `src/core/detector.py`  
**Tests:** `tests/unit/test_detector.py` (6 tests)

---

## Purpose

Aggregates failed login attempts per IP within a sliding time window. When the count reaches the configured threshold, it publishes a `SecurityEvent` via the `EventBroker` and resets the counter for that IP.

---

## API

```python
detector = ThresholdDetector(threshold=5, window_seconds=300)
detector.register_broker(broker)

# Called by the log parser for each failed attempt
detector.record_attempt(ip="192.0.2.1", timestamp=datetime.now(timezone.utc))
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | `int` | required | Attempts needed to fire an event |
| `window_seconds` | `int` | `300` (5 min) | Sliding window width |

---

## Behavior

- Each IP has its own independent counter (deque of timestamps).
- On each `record_attempt`, stale entries outside the window are pruned.
- When count >= threshold, a `SecurityEvent` is published and the counter is cleared.
- After firing, new attempts start counting from zero — it takes a full threshold to fire again.

---

## Design Decisions

- **Sliding window vs fixed window:** Sliding window prevents attackers from "gaming" the system by spacing attempts just outside fixed boundaries.
- **Counter reset after fire:** Prevents duplicate events for the same attack burst. A new burst requires fresh attempts.

---

## Example

```python
from datetime import datetime, timedelta, timezone

detector = ThresholdDetector(threshold=3, window_seconds=60)
detector.register_broker(broker)

now = datetime.now(timezone.utc)

detector.record_attempt("10.0.0.1", now)
detector.record_attempt("10.0.0.1", now + timedelta(seconds=10))
# Nothing published yet (2/3)

detector.record_attempt("10.0.0.1", now + timedelta(seconds=20))
# → SecurityEvent published! Counter reset.
```
