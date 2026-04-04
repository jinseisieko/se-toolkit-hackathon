# 5. CommandHandler + CLIInputAdapter

**Patterns:** Factory + Adapter + Result object  
**Files:** `src/interfaces/commands/handler.py`, `src/interfaces/commands/cli.py`, `src/interfaces/commands/factory.py`  
**Tests:** `tests/unit/test_command_handler.py` (11 tests)

---

## Purpose

`CommandHandler` is the central command router. It routes commands (`status`, `unblock`, `block`) to services. `CLIInputAdapter` reads stdin for safe test mode. `CommandFactory` creates wired handler instances.

---

## CommandContext

```python
@dataclass(frozen=True)
class CommandContext:
    user_id: str                          # chat ID or CLI username
    is_test_mode: bool                    # whether destructive cmds are restricted
    allowed_actions: Set[str]             # e.g. {"status", "block", "unblock"}
```

---

## CommandResult

```python
@dataclass(frozen=True)
class CommandResult:
    success: bool
    message: str                          # human-readable output
```

---

## CommandHandler API

```python
handler = CommandHandler(block_service=block_svc, alert_repo=alert_repo)

result = handler.handle("status", [], context)
# → CommandResult(success=True, message="Active: 5 | Blocked: 2")

result = handler.handle("unblock", ["192.0.2.1"], context)
# → CommandResult(success=True, message="Unblocked 192.0.2.1")

result = handler.handle("block", ["10.0.0.1", "suspicious"], context)
# → CommandResult(success=True, message="Blocked 10.0.0.1: suspicious")
```

---

## Supported Commands

| Command | Args | Permission | Description |
|---------|------|------------|-------------|
| `status` | none | `status` | Show active and blocked alert counts |
| `unblock` | `<IP>` | `unblock` | Unblock a specific IP |
| `block` | `<IP> [reason]` | `block` | Manually block an IP |

---

## CLIInputAdapter

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

---

## Design Decisions

- **Protocol-based typing:** Uses `typing.Protocol` for structural subtyping of dependencies instead of concrete classes. This allows mocking in tests without inheritance.
- **Stateless handler:** No internal state — all data lives in services. This makes the handler trivially testable and thread-safe.
