# 12. AlertChannel + ConsoleChannel

**Pattern:** Strategy
**Files:** `src/core/alerting/channel.py`, `src/adapters/alerting/console.py`
**Tests:** `tests/unit/alerting/test_alert_channel.py` (stubbed)

---

## Purpose

`AlertChannel` defines the interface for sending security alerts through different notification channels (console, Telegram, Slack, email, webhook). `ConsoleChannel` is the default implementation — writes formatted alerts to stdout/stderr.

---

## AlertChannel ABC

```python
class AlertChannel(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool: ...

    @abstractmethod
    async def send(
        self, event: EnrichedEvent, config: Dict[str, Any]
    ) -> SendResult: ...
```

### SendResult

```python
@dataclass(frozen=True)
class SendResult:
    success: bool          # Whether the alert was sent successfully
    message: str           # Human-readable result or error message
    channel: str           # Name of the channel used
```

---

## ConsoleChannel

The default alert channel — writes formatted alerts to the console. Used in production deployments where external notification services (Telegram, Slack) are unavailable.

### Output Format

```
🔴 [SSH] failed_auth
   IP: 192.0.2.1 [US, New York]
   Time: 2026-04-04 12:00:01 UTC
   User: root
```

- **Severity icons:** `🔴` for `failed_auth`, `🟡` for `failed_publickey`, `⚪` for unknown.
- **GeoIP data:** Shown in brackets if available (`[US, New York]`).
- **User field:** Only shown if a username was extracted.

### Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `use_stderr` | `False` | Write to stderr instead of stdout |
| `colorize` | TTY auto | Add ANSI color codes (auto-detected) |

### Usage

```python
from src.adapters.alerting.console import ConsoleChannel

channel = ConsoleChannel()
print(channel.name)  # → "console"
print(channel.validate_config({}))  # → True (always valid)

# Async send
result = await channel.send(enriched_event, {"use_stderr": False})
print(result.success)  # → True
```

---

## Implementing a New Channel

```python
class SlackChannel(AlertChannel):
    @property
    def name(self) -> str:
        return "slack"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "webhook_url" in config

    async def send(self, event: EnrichedEvent, config: Dict[str, Any]) -> SendResult:
        webhook_url = config["webhook_url"]
        # Send to Slack API...
        return SendResult(success=True, message="Sent", channel="slack")
```

---

## Design Decisions

- **Async interface:** `send()` is `async` to support HTTP-based channels (Slack, email, webhook) without blocking the worker thread.
- **Always-valid config for console:** The console channel requires no secrets or URLs, so `validate_config()` always returns `True`.
- **Frozen `SendResult`:** Immutable result objects prevent accidental modification and make testing straightforward.
