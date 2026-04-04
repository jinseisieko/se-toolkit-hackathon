# LogSentinel — Service Documentation

Complete documentation for all 8 core services.

---

## Table of Contents

1. [EventBroker + SecurityEvent](#1-eventbroker--securityevent)
2. [ThresholdDetector](#2-thresholddetector)
3. [FirewallStrategy + BlockService](#3-firewallstrategy--blockservice)
4. [AlertRepository + Peewee Models](#4-alertrepository--peewee-models)
5. [CommandHandler + CLIInputAdapter](#5-commandhandler--cliinputadapter)
6. [TelegramInputAdapter](#6-telegraminputadapter)
7. [SSHAuthLogParser](#7-sshauthlogparser)
8. [Flask Dashboard](#8-flask-dashboard)

---

## 1. EventBroker + SecurityEvent

**Pattern:** Observer
**File:** `src/core/events.py`

### Purpose

Decouples event producers (log parser, detector) from consumers (alert service, block service, Telegram alerts). Any component can publish a `SecurityEvent` and any number of subscribers react to it without knowing each other.

### SecurityEvent

A frozen dataclass representing a detected security incident.

| Field | Type | Description |
|-------|------|-------------|
| `ip` | `str` | Source IP address of the attacker |
| `attempt_count` | `int` | Number of failed attempts that triggered this event |
| `timestamp` | `datetime` | When the event was created (UTC) |
| `log_line` | `str` | The raw log line that contributed to detection |
| `service` | `str` | Service name, e.g. `"ssh"`, `"http"` |

### EventBroker API

```python
broker = EventBroker()

# Subscribe a handler — called for every published event
broker.subscribe(handler: Callable[[SecurityEvent], None])

# Dispatch an event to all subscribers
broker.publish(event: SecurityEvent)
```

### Behavior

- Handlers are called synchronously in subscription order.
- If a handler raises an exception, it is logged at ERROR level and the broker continues with the next handler.
- Publishing with no subscribers is a no-op (safe).
- The same handler can be subscribed multiple times (fires once per subscription).

### Design Decisions

- **No async queue (V1):** Synchronous delivery keeps the system simple and predictable. A queue-based approach can be added later by wrapping the broker.
- **No unsubscribe (V1):** Handlers are registered at startup and live for the process lifetime. Unsubscribe can be added if dynamic plugin loading is needed.

### Example

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

---

## 2. ThresholdDetector

**Pattern:** Aggregator + Observer publisher
**File:** `src/core/detector.py`

### Purpose

Aggregates failed login attempts per IP within a sliding time window. When the count reaches the configured threshold, it publishes a `SecurityEvent` via the `EventBroker` and resets the counter for that IP.

### API

```python
detector = ThresholdDetector(threshold=5, window_seconds=300)
detector.register_broker(broker)

# Called by the log parser for each failed attempt
detector.record_attempt(ip="192.0.2.1", timestamp=datetime.now(timezone.utc))
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | `int` | required | Attempts needed to fire an event |
| `window_seconds` | `int` | `300` (5 min) | Sliding window width |

### Behavior

- Each IP has its own independent counter (deque of timestamps).
- On each `record_attempt`, stale entries outside the window are pruned.
- When count >= threshold, a `SecurityEvent` is published and the counter is cleared.
- After firing, new attempts start counting from zero — it takes a full threshold to fire again.

### Design Decisions

- **Sliding window vs fixed window:** Sliding window prevents attackers from "gaming" the system by spacing attempts just outside fixed boundaries.
- **Counter reset after fire:** Prevents duplicate events for the same attack burst. A new burst requires fresh attempts.

### Example

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

---

## 3. FirewallStrategy + BlockService

**Patterns:** Strategy + Composition
**Files:** `src/core/blocking.py`, `src/adapters/firewall/ufw.py`, `src/adapters/firewall/noop.py`, `src/core/services/block_service.py`

### Purpose

`FirewallStrategy` defines the interface for blocking/unblocking IPs. `UFWStrategy` is the production implementation (wraps `ufw` CLI). `NoOpStrategy` is for testing (logs only, never touches subprocess). `BlockService` composes a strategy with a repository to coordinate blocking decisions.

### FirewallStrategy ABC

```python
class FirewallStrategy(ABC):
    @abstractmethod
    def block(self, ip: str, reason: str, duration: int | None = None) -> bool: ...

    @abstractmethod
    def unblock(self, ip: str) -> bool: ...

    @abstractmethod
    def is_blocked(self, ip: str) -> bool: ...
```

### Implementations

| Strategy | File | Behavior |
|----------|------|----------|
| `UFWStrategy` | `src/adapters/firewall/ufw.py` | Runs `ufw deny/delete from <IP>` via subprocess. Checks `ufw status` for `is_blocked()`. |
| `NoOpStrategy` | `src/adapters/firewall/noop.py` | Logs actions at INFO level. Always returns `True`. Never calls subprocess. |

### BlockService API

```python
service = BlockService(strategy=ufw_strategy, repo=block_repo)

# Called automatically when a SecurityEvent fires
service.handle_event(event: SecurityEvent) -> bool

# Manual blocking
service.block_ip(ip="10.0.0.1", reason="manual block") -> bool

# Manual unblocking
service.unblock_ip(ip="10.0.0.1") -> bool
```

### BlockRepository ABC

```python
class BlockRepository(ABC):
    def create(self, ip: str, reason: str, strategy: str) -> BlockedIPRecord: ...
    def get_by_ip(self, ip: str) -> BlockedIPRecord | None: ...
    def mark_blocked(self, record_id: int) -> bool: ...
    def mark_unblocked(self, record_id: int) -> bool: ...
```

### Behavior

- `handle_event()` checks if a record already exists for the IP. If so, it marks it blocked (no duplicate firewall call). If not, it calls the strategy and creates a new record.
- `block_ip()` always creates a new record.
- `unblock_ip()` requires an existing record — returns `False` if none found.
- All methods validate IP addresses before execution.

### Design Decisions

- **Composition over inheritance:** `BlockService` *has a* strategy, not *is a* strategy. This makes it trivial to swap strategies without changing service code.
- **IP validation at boundary:** `validate_ip()` is called inside strategy methods, preventing command injection through malformed IPs.

---

## 4. AlertRepository + Peewee Models

**Pattern:** Repository
**Files:** `src/infrastructure/models.py`, `src/infrastructure/db.py`, `src/core/repositories.py`

### Purpose

Provides data access for alerts through a clean abstraction. The `AlertRepository` ABC lives in `core/` (business logic), while the Peewee implementation lives in `infrastructure/`. This keeps ORM imports out of business logic.

### Database Models

| Model | Table | Fields |
|-------|-------|--------|
| `Alert` | `alerts` | `id`, `ip`, `attempts`, `service`, `first_seen`, `last_seen`, `blocked` |
| `BlockedIP` | `blocked_ips` | `id`, `ip` (unique), `blocked_at`, `reason`, `strategy`, `is_blocked` |

### Alert Dataclass (core)

```python
@dataclass
class Alert:
    id: Optional[int]
    ip: str
    attempts: int
    service: str
    first_seen: datetime
    last_seen: datetime
    blocked: bool
```

### PeeweeAlertRepository API

```python
from src.core.repositories import PeeweeAlertRepository
from src.infrastructure.db import init_database
from peewee import SqliteDatabase

db = SqliteDatabase("sentinel.db")
init_database(db)

repo = PeeweeAlertRepository(db)

# Create
alert = repo.create(ip="192.0.2.1", attempts=5, service="ssh")

# Query (newest first, default limit 50)
alerts: Sequence[Alert] = repo.get_recent(limit=50)

# Update
repo.mark_blocked(alert.id)

# Lookup
alert = repo.get_by_id(42)  # returns None if not found
```

### Database Initialization

```python
# Production — file-based SQLite
db = SqliteDatabase("/app/data/sentinel.db")

# Testing — in-memory
db = SqliteDatabase(":memory:")

init_database(db)  # binds DB to all models and creates tables
```

### Design Decisions

- **Peewee over SQLAlchemy:** Peewee is lightweight, has zero configuration, and works well for single-file SQLite databases. The Repository pattern allows migrating to PostgreSQL later without changing core logic.
- **In-memory SQLite for tests:** Tests use `:memory:` databases — real SQL operations, no mocking, fast execution.

---

## 5. CommandHandler + CLIInputAdapter

**Patterns:** Factory + Adapter + Result object
**Files:** `src/interfaces/commands/handler.py`, `src/interfaces/commands/cli.py`, `src/interfaces/commands/factory.py`

### Purpose

`CommandHandler` is the central command router. It routes commands (`status`, `unblock`, `block`) to services. `CLIInputAdapter` reads stdin for safe test mode. `CommandFactory` creates wired handler instances.

### CommandContext

```python
@dataclass(frozen=True)
class CommandContext:
    user_id: str                          # chat ID or CLI username
    is_test_mode: bool                    # whether destructive cmds are restricted
    allowed_actions: Set[str]             # e.g. {"status", "block", "unblock"}
```

### CommandResult

```python
@dataclass(frozen=True)
class CommandResult:
    success: bool
    message: str                          # human-readable output
```

### CommandHandler API

```python
handler = CommandHandler(block_service=block_svc, alert_repo=alert_repo)

result = handler.handle("status", [], context)
# → CommandResult(success=True, message="Active: 5 | Blocked: 2")

result = handler.handle("unblock", ["192.0.2.1"], context)
# → CommandResult(success=True, message="Unblocked 192.0.2.1")

result = handler.handle("block", ["10.0.0.1", "suspicious"], context)
# → CommandResult(success=True, message="Blocked 10.0.0.1: suspicious")
```

### Supported Commands

| Command | Args | Permission | Description |
|---------|------|------------|-------------|
| `status` | none | `status` | Show active and blocked alert counts |
| `unblock` | `<IP>` | `unblock` | Unblock a specific IP |
| `block` | `<IP> [reason]` | `block` | Manually block an IP |

### CLIInputAdapter

```python
from src.interfaces.commands.cli import CLIInputAdapter

adapter = CLIInputAdapter(prompt="❯ ")
adapter.start_listening(handler)

# In the terminal:
# ❯ /status
# ✅ Active: 5 | Blocked: 2
# ❯ /unblock 192.0.2.1
# ✅ Unblocked 192.0.2.1
# ❯ quit
```

- Lines starting with `/` are parsed as commands.
- Non-slash lines are silently ignored.
- `quit` / `exit` / empty input / EOF / Ctrl+C stops the loop.

### Design Decisions

- **Protocol-based typing:** Uses `typing.Protocol` for structural subtyping of dependencies instead of concrete classes. This allows mocking in tests without inheritance.
- **Stateless handler:** No internal state — all data lives in services. This makes the handler trivially testable and thread-safe.

---

## 6. TelegramInputAdapter

**Pattern:** Adapter
**File:** `src/adapters/telegram.py`

### Purpose

Connects `python-telegram-bot` to `CommandHandler`. Receives Telegram updates, parses commands, forwards to the handler, and sends back results. Supports test mode with chat ID filtering.

### API

```python
from src.adapters.telegram import TelegramInputAdapter

adapter = TelegramInputAdapter(
    token="123456:ABC-DEF...",
    test_mode=False,
    test_chat_id=None,  # only relevant when test_mode=True
)

adapter.set_handler(command_handler)
app = adapter.build_app()
app.run_polling()  # blocks, runs forever
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | Telegram bot token from @BotFather |
| `test_mode` | `bool` | If True, only `test_chat_id` can interact |
| `test_chat_id` | `str \| None` | The only allowed chat ID in test mode |

### Supported Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with available commands |
| `/status` | Show active and blocked counts |
| `/unblock <IP>` | Unblock an IP |
| `/block <IP> [reason]` | Block an IP |

### Behavior

- **Test mode:** Only messages from `test_chat_id` are processed. Other chats are silently ignored (DEBUG log).
- **Non-text messages:** (photos, stickers) are ignored.
- **Reply format:** `✅ <message>` for success, `❌ <message>` for failure.
- **Permission model:** Test mode restricts `allowed_actions` to `{"status"}` only. Production mode allows all actions.

### Internal Dispatch

```
Telegram Update
    → _handle_message() (async)
        → _check_authorized() (test mode filter)
        → Parse command from text
        → CommandHandler.handle(command, args, context)
        → _reply(update, result) (async)
```

### Design Decisions

- **Async handlers:** All telegram-bot handlers are async because the library requires it. The `CommandHandler` itself is sync — the adapter bridges the async/sync boundary.
- **Separate `/start` handler:** Sends a welcome message with instructions, independent of the command router.

---

## 7. SSHAuthLogParser

**Pattern:** Template Method
**Files:** `src/adapters/log_tail.py`, `src/adapters/parsers/ssh_auth.py`

### Purpose

Parses `/var/log/auth.log` lines for failed SSH login attempts. Extracts IP, username, timestamp, and metadata. `BaseLogParser` handles file tailing via `tail -F`; `SSHAuthLogParser` implements the regex parsing.

### ParsedEntry

```python
@dataclass
class ParsedEntry:
    ip: str                          # Source IP address
    user: Optional[str]              # Targeted username
    timestamp: datetime              # When the attempt occurred (UTC)
    raw_line: str                    # Original log line
    metadata: Dict[str, Any]         # Extensible: service, auth_type, port, ip_type
```

### SSHAuthLogParser API

```python
parser = SSHAuthLogParser()

# Parse a single line
entry = parser.parse_line(line)

# If entry is not None, feed it to the detector
if entry is not None:
    detector.record_attempt(entry.ip, entry.timestamp)
```

### Supported Log Patterns

| Pattern | Example |
|---------|---------|
| Failed password (valid user) | `Failed password for root from 192.0.2.1 port 22 ssh2` |
| Failed password (invalid user) | `Failed password for invalid user admin from 10.0.0.1 port 22 ssh2` |
| Failed publickey | `Failed publickey for deploy from 172.16.0.5 port 22 ssh2` |

### Non-Matching Lines (returns None)

- Accepted logins
- Connection closed / disconnected messages
- Empty or whitespace-only lines
- Non-SSH log entries

### BaseLogParser.process_stream()

```python
parser = SSHAuthLogParser()

def on_entry(entry: ParsedEntry) -> None:
    detector.record_attempt(entry.ip, entry.timestamp)

parser.process_stream("/var/log/auth.log", callback=on_entry)
# Blocks until Ctrl+C or EOF
```

- Uses `tail -F` to follow log rotation.
- Catches `FileNotFoundError` and `PermissionError` gracefully.

### IP Classification

| Type | Behavior |
|------|----------|
| IPv4 | Fully processed |
| IPv6 | Parsed but flagged in `metadata["ip_type"]` — V1 ignores IPv6 in detection |
| Invalid | Skipped |

### Timestamp Parsing

- Parses syslog format: `Apr  4 12:00:01`
- Assumes current year (syslog omits it).
- Falls back to `datetime.now(timezone.utc)` on parse failure.

### Design Decisions

- **`tail -F` over `watchdog`:** `tail -F` is built into every Linux system, handles log rotation natively, and requires no extra dependencies.
- **Regex-based:** Simple and fast for syslog's structured format. Can be extended with additional patterns without changing the base parser.

---

## 8. Flask Dashboard

**Pattern:** Application Factory
**Files:** `src/interfaces/web/app.py`, `src/interfaces/web/templates/dashboard.html`, `src/static/style.css`

### Purpose

Serves the LogSentinel web dashboard — a real-time view of alerts and blocked IPs with a JSON API for polling.

### Routes

| Route | Method | Response | Description |
|-------|--------|----------|-------------|
| `/` | GET | HTML | Main dashboard page |
| `/api/alerts` | GET | JSON | Recent 50 alerts |
| `/api/blocked` | GET | JSON | All blocked alerts |

### JSON Response Format

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

### Dashboard Features

- **Stats cards:** Total alerts, active count, blocked count.
- **Alerts table:** IP, attempts, service, last seen, status badge (Active/Blocked).
- **Live polling:** JavaScript polls `/api/alerts` every 10 seconds to update stat counters.
- **Empty state:** Shows "No alerts yet. Waiting for activity…" when the DB is empty.
- **Dark theme:** Uses CSS custom properties for easy theming.

### Application Factory

```python
from src.interfaces.web.app import create_app
from src.core.repositories import PeeweeAlertRepository

app = create_app(alert_repo=repo)
app.config["TESTING"] = True

with app.test_client() as client:
    resp = client.get("/api/alerts")
    data = resp.get_json()
```

### Running Standalone

```python
from src.interfaces.web.app import create_app

app = create_app(alert_repo=repo)
app.run(host="0.0.0.0", port=5000)
```

### Design Decisions

- **Polling over SSE/WebSockets (V1):** Simple polling every 10s is sufficient for V1. Server-Sent Events can be added in V2 without changing the API.
- **Injected repository:** The Flask app accepts an `AlertRepository` in its factory function, making it trivial to test with in-memory SQLite and swap databases in production.
- **Minimal template:** Jinja2 template with no JavaScript frameworks. Easy to extend with charts, timelines, or geo-IP maps in V2.

---

## Wiring Everything Together

The recommended production wiring uses `NoOpStrategy` for development and `UFWStrategy` for production:

```python
# Configuration
from src.core.events import EventBroker
from src.core.detector import ThresholdDetector
from src.adapters.firewall.ufw import UFWStrategy
from src.adapters.firewall.noop import NoOpStrategy
from src.core.services.block_service import BlockService
from src.core.repositories import PeeweeAlertRepository
from src.infrastructure.db import init_database
from src.adapters.parsers.ssh_auth import SSHAuthLogParser
from src.interfaces.commands.handler import CommandHandler
from src.interfaces.commands.factory import create_command_handler
from src.adapters.telegram import TelegramInputAdapter
from src.interfaces.web.app import create_app
from peewee import SqliteDatabase

# 1. Database
db = SqliteDatabase("/app/data/sentinel.db")
init_database(db)
alert_repo = PeeweeAlertRepository(db)

# 2. Event system
broker = EventBroker()

# 3. Detector
detector = ThresholdDetector(threshold=5, window_seconds=300)
detector.register_broker(broker)

# 4. Firewall (swap UFWStrategy for NoOpStrategy in test mode)
strategy = UFWStrategy()
block_repo = ...  # implement BlockRepository
block_svc = BlockService(strategy=strategy, repo=block_repo)

# 5. Command handler
cmd_handler = create_command_handler(block_svc, alert_repo)

# 6. Telegram bot
tg = TelegramInputAdapter(token="...", test_mode=False)
tg.set_handler(cmd_handler)

# 7. Log parser
parser = SSHAuthLogParser()
def on_entry(entry):
    detector.record_attempt(entry.ip, entry.timestamp)

# 8. Start services
parser.process_stream("/var/log/auth.log", callback=on_entry)
tg.build_app().run_polling()

# 9. Web dashboard
app = create_app(alert_repo=alert_repo)
app.run(host="0.0.0.0", port=5000)
```
