# LogSentinel — Implementation Log

Tracks progress through the V1 and V2 implementation workflows.

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

## Service 5: CommandHandler + CLIInputAdapter ✅

**Date:** 2026-04-04
**Files:**
- `src/interfaces/commands/handler.py` — `CommandHandler`, `CommandContext`, `CommandResult`, Protocol types
- `src/interfaces/commands/cli.py` — `CLIInputAdapter` (stdin reader with `_parse_command()`)
- `src/interfaces/commands/factory.py` — `create_command_handler()` wiring helper
- `tests/unit/test_command_handler.py` — 11 tests

### Micro-Plan
- **Responsibility:** `CommandHandler` routes commands (`status`, `unblock`, `block`) to services. `CLIInputAdapter` reads stdin for test mode.
- **Input contract:** `CommandHandler.handle(command, args, context)` → `CommandResult`. `CLIInputAdapter._parse_command(line)` → `(cmd, args) | None`.
- **Output contract:** `CommandResult(success, message)`. Context carries `user_id`, `is_test_mode`, `allowed_actions`.
- **Edge cases:** Unknown command → error. Action not in `allowed_actions` → denied. Missing args → usage hint. Empty input → ignored.
- **Pattern:** Factory + Adapter + Protocol-based duck typing (structural subtyping for deps).
- **Testing:** Pure unit tests for routing logic. Mock BlockService + AlertRepo. Test CLI adapter parses `/cmd arg1 arg2` correctly.

### Test Coverage
| Test | Status |
|------|--------|
| /status returns alert and blocked counts | ✅ |
| /unblock calls block_service.unblock_ip | ✅ |
| /block calls block_service.block_ip | ✅ |
| Unknown command returns error result | ✅ |
| Missing IP argument returns error | ✅ |
| Action not in allowed_actions → denied | ✅ |
| Strategy failure propagates error | ✅ |
| Empty alert list shows zeroes | ✅ |
| CLIInputAdapter._parse_command handles all formats | ✅ |
| CLIInputAdapter._parse_command ignores non-slash input | ✅ |
| CLIInputAdapter._parse_command strips leading slash | ✅ |

### Verification
- **pytest:** `11 passed in 0.05s` (Service 5), `49 passed in 0.16s` (full suite)
- **mypy --strict:** `Success: no issues found in 3 source files`

---

## Service 6: TelegramInputAdapter ✅

**Date:** 2026-04-04
**Files:**
- `src/adapters/telegram.py` — `TelegramInputAdapter` (python-telegram-bot bridge)
- `tests/unit/test_telegram_adapter.py` — 7 tests (async, with pytest-asyncio)

### Micro-Plan
- **Responsibility:** Connect `python-telegram-bot` to `CommandHandler`. Receive updates, parse commands, forward to handler, reply.
- **Input contract:** Telegram `Update` → `_handle_message()` → `CommandHandler.handle()` → `_reply()`.
- **Output contract:** `reply_text()` with ✅/❌ prefix. Test mode: restrict to `TEST_CHAT_ID`, log unauthorized attempts.
- **Edge cases:** Unauthorized chat → ignored + DEBUG log. Non-text message → ignored. Missing bot token → warning logged. Handler exception → error result.
- **Pattern:** Adapter — translates Telegram API to our command interface.
- **Testing:** Async tests with `pytest-asyncio`. Mock `Update`, `Message`, `reply_text`.

### Test Coverage
| Test | Status |
|------|--------|
| Authorized chat forwards to handler | ✅ |
| Handler result replied to user | ✅ |
| Unauthorized chat ignored and logged | ✅ |
| Non-text message ignored | ✅ |
| /start command sends welcome | ✅ |
| Handler failure returns error reply | ✅ |
| build_app() creates Application | ✅ |

### Verification
- **pytest:** `7 passed in 0.25s` (Service 6), `56 passed in 0.47s` (full suite)
- **mypy --strict:** `Success: no issues found in 1 source file`

---

## Service 7: SSHAuthLogParser ✅

**Date:** 2026-04-04
**Files:**
- `src/adapters/log_tail.py` — `BaseLogParser` (Template Method) + `ParsedEntry` dataclass + `process_stream()`
- `src/adapters/parsers/ssh_auth.py` — `SSHAuthLogParser` with regex for failed SSH attempts
- `tests/unit/test_parsers.py` — 11 tests

### Micro-Plan
- **Responsibility:** Parse auth.log lines for failed SSH login attempts. Extract IP, user, timestamp.
- **Input contract:** `parse_line(line) -> ParsedEntry | None`. `process_stream(file_path, callback)` — tails file via `tail -F`.
- **Output contract:** `ParsedEntry(ip, user, timestamp, raw_line, metadata)`. Non-matching → None.
- **Edge cases:** Malformed lines → None. Invalid timestamps → fallback to now. IPv6 → flagged (V1 IPv4 only). Multiple failure patterns (password, publickey, invalid user).
- **Pattern:** Template Method — `BaseLogParser` defines stream processing, subclass implements regex.
- **Testing:** Pure unit tests on `parse_line()` with real auth.log samples.

### Test Coverage
| Test | Status |
|------|--------|
| Failed password for valid user | ✅ |
| Failed password for invalid user | ✅ |
| Failed publickey attempt | ✅ |
| Non-matching line returns None | ✅ |
| Empty line returns None | ✅ |
| Whitespace-only returns None | ✅ |
| Malformed timestamp uses fallback | ✅ |
| Metadata contains service info | ✅ |
| IPv6 address flagged | ✅ |
| Connection closed line ignored | ✅ |
| Disconnect line ignored | ✅ |

### Verification
- **pytest:** `11 passed in 0.04s` (Service 7), `67 passed in 0.30s` (full suite)
- **mypy --strict:** `Success: no issues found in 2 source files`

---

## Service 8: Flask Dashboard ✅

**Date:** 2026-04-04
**Files:**
- `src/interfaces/web/app.py` — Flask application factory with dashboard + JSON API
- `src/interfaces/web/templates/dashboard.html` — Jinja2 dashboard template
- `src/static/style.css` — Dark theme CSS styles
- `tests/unit/test_web_dashboard.py` — 7 tests (Flask test client)

### Micro-Plan
- **Responsibility:** Serve web UI with alert list, blocked IPs, stats. Expose JSON API.
- **Input contract:** Routes: `GET /`, `GET /api/alerts`, `GET /api/blocked`. Accepts injected `AlertRepository`.
- **Output contract:** HTML via Jinja2. JSON API endpoints.
- **Edge cases:** Empty DB → shows empty tables. API respects default limit of 50.
- **Pattern:** Application Factory.
- **Testing:** Flask test client with in-memory SQLite.

### Test Coverage
| Test | Status |
|------|--------|
| GET / renders dashboard HTML | ✅ |
| GET /api/alerts returns JSON | ✅ |
| GET /api/blocked returns JSON | ✅ |
| Empty dashboard shows zero counts | ✅ |
| API returns empty list on empty DB | ✅ |
| API respects default limit | ✅ |
| API blocked returns only blocked | ✅ |

### Verification
- **pytest:** `7 passed in 0.25s` (Service 8), `74 passed in 0.61s` (full suite)
- **mypy --strict:** `Success: no issues found in 1 source file`

---

## Summary

### V1 — Core Services

| Service | Tests | Status |
|---------|-------|--------|
| 1. EventBroker + SecurityEvent | 6 | ✅ |
| 2. ThresholdDetector | 6 | ✅ |
| 3. FirewallStrategy + BlockService | 18 | ✅ |
| 4. AlertRepository + Peewee Models | 8 | ✅ |
| 5. CommandHandler + CLIInputAdapter | 11 | ✅ |
| 6. TelegramInputAdapter | 7 | ✅ |
| 7. SSHAuthLogParser | 11 | ✅ |
| 8. Flask Dashboard (block/unblock UI + API) | 11 | ✅ |
| **V1 Total** | **78** | **✅** |

### V2 — Platform Services

| Service | Tests | Status |
|---------|-------|--------|
| 1. LogParserPlugin + ParserRegistry | 11 | ✅ |
| 2. SSHAuthPlugin migration | 17 | ✅ |
| 3. GeoIPEnricher + MaxMind adapter | 8 | ✅ |
| 4. AlertChannel + ConsoleChannel | 10 | ✅ |
| 5. MetricsCollector + /metrics endpoint | 15 | ✅ |
| 6. Worker entrypoint + Docker Compose deployment | — | ✅ |
| 7. API v2 auth + RBAC (block/unblock + Bearer) | 9 | ✅ |
| 8. Attack Map component | — | Pending |
| **V2 Total** | **70** | 🔄 In progress |

### Grand Total: **152 tests passing**, `flake8` clean

### Deployment

- **Deployed:** `se-toolkit-vm` via Docker Compose (3 services: worker, web, telegram)
- **Dashboard:** `http://10.93.25.13:5000`
- **Worker:** `logsentinel-worker` — tails real `/var/log/auth.log`
- **Web:** `logsentinel-web` — Flask dashboard + REST API
- **Telegram:** `logsentinel-telegram` — bot for alerts and commands
- **Verified:** Simulated SSH attack detected, alerted, blocked, persisted, and displayed on dashboard
