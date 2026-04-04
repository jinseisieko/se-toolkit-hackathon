# 3. FirewallStrategy + BlockService

**Patterns:** Strategy + Composition  
**Files:** `src/core/blocking.py`, `src/adapters/firewall/ufw.py`, `src/adapters/firewall/noop.py`, `src/core/services/block_service.py`  
**Tests:** `tests/unit/test_blocking.py` (12 tests), `tests/unit/test_block_service.py` (6 tests)

---

## Purpose

`FirewallStrategy` defines the interface for blocking/unblocking IPs. `UFWStrategy` is the production implementation (wraps `ufw` CLI). `NoOpStrategy` is for testing (logs only, never touches subprocess). `BlockService` composes a strategy with a repository to coordinate blocking decisions.

---

## FirewallStrategy ABC

```python
class FirewallStrategy(ABC):
    @abstractmethod
    def block(self, ip: str, reason: str, duration: int | None = None) -> bool: ...

    @abstractmethod
    def unblock(self, ip: str) -> bool: ...

    @abstractmethod
    def is_blocked(self, ip: str) -> bool: ...
```

---

## Implementations

| Strategy | File | Behavior |
|----------|------|----------|
| `UFWStrategy` | `src/adapters/firewall/ufw.py` | Runs `ufw deny/delete from <IP>` via subprocess. Checks `ufw status` for `is_blocked()`. |
| `NoOpStrategy` | `src/adapters/firewall/noop.py` | Logs actions at INFO level. Always returns `True`. Never calls subprocess. |

---

## BlockService API

```python
service = BlockService(strategy=ufw_strategy, repo=block_repo)

# Called automatically when a SecurityEvent fires
service.handle_event(event: SecurityEvent) -> bool

# Manual blocking
service.block_ip(ip="10.0.0.1", reason="manual block") -> bool

# Manual unblocking
service.unblock_ip(ip="10.0.0.1") -> bool
```

---

## BlockRepository ABC

```python
class BlockRepository(ABC):
    def create(self, ip: str, reason: str, strategy: str) -> BlockedIPRecord: ...
    def get_by_ip(self, ip: str) -> BlockedIPRecord | None: ...
    def mark_blocked(self, record_id: int) -> bool: ...
    def mark_unblocked(self, record_id: int) -> bool: ...
```

---

## Behavior

- `handle_event()` checks if a record already exists for the IP. If so, it marks it blocked (no duplicate firewall call). If not, it calls the strategy and creates a new record.
- `block_ip()` always creates a new record.
- `unblock_ip()` requires an existing record — returns `False` if none found.
- All methods validate IP addresses before execution.

---

## Design Decisions

- **Composition over inheritance:** `BlockService` *has a* strategy, not *is a* strategy. This makes it trivial to swap strategies without changing service code.
- **IP validation at boundary:** `validate_ip()` is called inside strategy methods, preventing command injection through malformed IPs.
