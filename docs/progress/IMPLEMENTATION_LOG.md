# LogSentinel — Implementation Log

Tracks progress through the V1 implementation workflow defined in `task_version_1.md`.

---

## Service 1: EventBroker + SecurityEvent ✅

**Date:** 2026-04-04
**Files:**
- `src/core/events.py` — `SecurityEvent` (frozen dataclass) + `EventBroker` (Observer pattern)
- `tests/unit/test_events.py` — 6 unit tests

### Micro-Plan
- **Responsibility:** Decouple event producers from consumers via pub/sub.
- **Input contract:** `publish(event: SecurityEvent)` — callers pass a fully-formed event.
- **Output contract:** Each subscribed handler receives the event synchronously.
- **Edge cases:** Handler exceptions are caught, logged at ERROR, and do not stop delivery to remaining handlers. No subscribers → no-op. Same handler twice → fires twice.
- **Pattern:** Observer — enables adding new responders without touching core logic.
- **Testing:** Pure unit tests with mock handlers; zero external dependencies.

### Test Coverage
| Test | Status |
|------|--------|
| Single handler receives event | ✅ |
| Multiple handlers receive same event | ✅ |
| Same handler subscribed twice fires twice | ✅ |
| Publish with no subscribers is no-op | ✅ |
| Handler exception doesn't stop remaining handlers | ✅ |
| Exception logged at ERROR level | ✅ |

### Verification
- **pytest:** `6 passed in 0.06s`
- **mypy --strict:** `Success: no issues found in 1 source file`

---

## Service 2: ThresholdDetector ✅

**Date:** 2026-04-04
**Files:**
- `src/core/detector.py` — `ThresholdDetector` (sliding-window aggregator + Observer publisher)
- `tests/unit/test_detector.py` — 6 unit tests

### Micro-Plan
- **Responsibility:** Aggregate failed login attempts per IP within a sliding time window; publish a `SecurityEvent` when threshold is breached.
- **Input contract:** `record_attempt(ip: str, timestamp: datetime)` — called by the log parser for each failed attempt.
- **Output contract:** Publishes `SecurityEvent` via `EventBroker` once `attempt_count >= threshold` within the window, then resets counter.
- **Edge cases:** Counter resets after window expires. Multiple IPs tracked independently. Threshold of 1 fires immediately. Stale timestamps are pruned before each check.
- **Pattern:** Aggregator + Observer — collects raw attempts, decides when to emit events.
- **Testing:** In-memory `EventBroker` with mock handler; deterministic timestamps via `_utc()` helper.

### Test Coverage
| Test | Status |
|------|--------|
| Fires event when threshold reached | ✅ |
| Does NOT fire when below threshold | ✅ |
| Threshold of 1 fires immediately | ✅ |
| Resets counter after window expires | ✅ |
| Tracks multiple IPs independently | ✅ |
| Fires only once per breach cycle (counter resets) | ✅ |

### Verification
- **pytest:** `6 passed in 0.04s`
- **mypy --strict:** `Success: no issues found in 1 source file`

---

## Service 3: FirewallStrategy + BlockService ✅

**Date:** 2026-04-04
**Files:**
- `src/core/blocking.py` — `FirewallStrategy` ABC (Strategy pattern)
- `src/adapters/firewall/ufw.py` — `UFWStrategy` (production, wraps `ufw` CLI)
- `src/adapters/firewall/noop.py` — `NoOpStrategy` (test mode, logs only)
- `src/core/services/block_service.py` — `BlockService` + `BlockRepository` ABC
- `src/utils/validation.py` — `validate_ip()` IP validator
- `tests/unit/test_blocking.py` — 12 tests (strategies + validation)
- `tests/unit/test_block_service.py` — 6 tests (service orchestration)

### Micro-Plan
- **Responsibility:** `FirewallStrategy` defines block/unblock/is_blocked interface. `UFWStrategy` wraps `ufw` subprocess. `NoOpStrategy` logs only. `BlockService` composes strategy + repo to coordinate.
- **Input contract:** `BlockService.block_ip(ip, reason)` / `unblock_ip(ip)` / `handle_event(event)`.
- **Output contract:** Returns `True`/`False`. `NoOpStrategy` never calls `subprocess.run`.
- **Edge cases:** Invalid IP rejected early. Strategy failure propagates. Idempotent: already-blocked IP is safe. `NoOpStrategy` never touches subprocess.
- **Pattern:** Strategy + Composition — `BlockService` *has a* `FirewallStrategy`.
- **Testing:** Mock `subprocess.run` for UFW. Assert NoOp never calls it.

### Test Coverage
| Test | Status |
|------|--------|
| NoOpStrategy.block() never calls subprocess | ✅ |
| NoOpStrategy.unblock() never calls subprocess | ✅ |
| NoOpStrategy.is_blocked() always False | ✅ |
| UFWStrategy.block() calls correct ufw command | ✅ |
| UFWStrategy.block() returns False on failure | ✅ |
| UFWStrategy.unblock() calls correct ufw command | ✅ |
| UFWStrategy.unblock() returns False on failure | ✅ |
| UFWStrategy.is_blocked() parses status output | ✅ |
| UFWStrategy.is_blocked() handles ufw error | ✅ |
| IP validation accepts valid IPv4 | ✅ |
| IP validation rejects invalid strings | ✅ |
| IP validation rejects out-of-range octets | ✅ |
| BlockService.handle_event() blocks + records | ✅ |
| BlockService skips already-blocked IP | ✅ |
| BlockService.block_ip() returns False on strategy fail | ✅ |
| BlockService.unblock_ip() returns False when not found | ✅ |
| BlockService.unblock_ip() calls strategy then repo | ✅ |
| NoOpStrategy path never calls subprocess (end-to-end) | ✅ |

### Verification
- **pytest:** `18 passed in 0.07s` (Service 3), `30 passed in 0.08s` (full suite)
- **mypy --strict:** `Success: no issues found in 5 source files`

---

## Service 4: AlertRepository + Peewee Models ✅

**Date:** 2026-04-04
**Files:**
- `src/infrastructure/models.py` — Peewee models (`Alert`, `BlockedIP`) with `BaseModel`
- `src/infrastructure/db.py` — `init_database()` helper for runtime DB binding
- `src/core/repositories.py` — `Alert` dataclass, `AlertRepository` ABC, `PeeweeAlertRepository`
- `tests/unit/test_repositories.py` — 8 tests (real in-memory SQLite, no mocking)

### Micro-Plan
- **Responsibility:** `PeeweeAlertRepository` provides data access — create alerts, query recent, mark blocked.
- **Input contract:** `create(ip, attempts, service)`, `get_recent(limit)`, `mark_blocked(alert_id)`, `get_by_id(id)`.
- **Output contract:** Returns plain `Alert` dataclass instances. ORM isolated behind repository.
- **Edge cases:** Empty DB → empty sequence. Limit clamps to available rows. `mark_blocked` on non-existent ID → False. `get_by_id` missing → None.
- **Pattern:** Repository — isolates Peewee from core logic, enables future DB migration.
- **Testing:** Real in-memory SQLite — no mocking, actual DB operations.

### Test Coverage
| Test | Status |
|------|--------|
| create + get_recent returns inserted alert | ✅ |
| get_recent respects limit | ✅ |
| get_recent orders by newest first | ✅ |
| mark_blocked sets flag and persists | ✅ |
| Empty DB returns empty sequence | ✅ |
| Limit larger than dataset returns all | ✅ |
| mark_blocked on non-existent ID returns False | ✅ |
| get_by_id returns None for missing | ✅ |

### Verification
- **pytest:** `8 passed in 0.07s` (Service 4), `38 passed in 0.14s` (full suite)
- **mypy --strict:** `Success: no issues found in 3 source files`

---

## Service 5: CommandHandler + CLIInputAdapter ⏳

**Status:** Pending

---

## Service 6: TelegramInputAdapter ⏳

**Status:** Pending

---

## Service 7: SSHAuthLogParser ⏳

**Status:** Pending

---

## Service 8: Flask Dashboard ⏳

**Status:** Pending
