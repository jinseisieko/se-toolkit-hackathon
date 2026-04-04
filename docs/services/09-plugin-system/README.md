# 9. Plugin System (ParserRegistry + LogParserPlugin)

**Patterns:** Factory + Strategy
**Files:** `src/core/plugins/registry.py`, `src/core/plugins/parser_plugin.py`
**Tests:** `tests/unit/plugins/test_parser_registry.py` (11 tests)

---

## Purpose

Extensible log source architecture. Any log format (SSH, Nginx, Apache, custom) can be added by implementing `LogParserPlugin` and registering it with `ParserRegistry`. This replaces the V1 monolithic parser approach with a dynamic, config-driven plugin system.

---

## LogParserPlugin ABC

The contract all log source plugins must implement:

```python
class LogParserPlugin(ABC):
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...                  # e.g. "ssh_auth", "nginx_access"

    @property
    @abstractmethod
    def default_log_path(self) -> str: ...      # e.g. "/var/log/auth.log"

    @abstractmethod
    def parse_line(self, line: str) -> Optional[ParsedEntry]: ...

    @abstractmethod
    def get_indicators(self) -> List[DetectionRule]: ...
```

### ParsedEntry

Normalised output shared by all plugins:

| Field | Type | Description |
|-------|------|-------------|
| `ip` | `IPv4Address \| IPv6Address` | Source IP address |
| `timestamp` | `datetime` | When the event occurred (UTC) |
| `service` | `str` | Service name, e.g. `"ssh"`, `"nginx"` |
| `event_type` | `str` | Categorical description, e.g. `"failed_auth"` |
| `raw_line` | `str` | Original log line text |
| `user` | `Optional[str]` | Targeted username (if available) |
| `meta` | `Dict[str, Any]` | Extensible plugin-specific metadata |

### DetectionRule

Defines detectable patterns and thresholds:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Human-readable identifier |
| `pattern` | `re.Pattern` | Compiled regex |
| `severity` | `Severity` | `low`, `medium`, `high`, `critical` |
| `threshold` | `int` | Match count to trigger |
| `window_seconds` | `int` | Sliding window width |

---

## ParserRegistry API

```python
from src.core.plugins.registry import ParserRegistry

registry = ParserRegistry()

# Register a plugin class under a unique name
registry.register("ssh_auth", SSHAuthPlugin)

# Instantiate with injected config
plugin = registry.create("ssh_auth", {"log_path": "/var/log/auth.log"})

# List available plugins (sorted alphabetically)
names = registry.list_available()  # → ["ssh_auth"]
```

### Error Handling

| Exception | When |
|-----------|------|
| `PluginNotFoundError` | `create()` called with unregistered name |
| `PluginAlreadyRegisteredError` | Same name registered twice |
| `PluginInstantiationError` | Plugin's `__init__` raises |

### Plugin Isolation

A failing plugin does not crash the registry or affect other plugins. Each plugin's instantiation is independently wrapped.

---

## Design Decisions

- **Explicit registration over auto-discovery:** Plugins are registered by name (e.g. `registry.register("ssh_auth", SSHAuthPlugin)`) rather than scanned from directories. This gives full control and avoids import side-effects. Auto-discovery via `importlib` is reserved for future V2.
- **Config injection:** The registry passes a `config` dict to each plugin's `__init__`, enabling per-instance configuration (log path, thresholds) without hardcoding.
- **`ParsedEntry` uses `ipaddress` objects:** Unlike V1's string-based `ParsedEntry`, the V2 version stores `IPv4Address`/`IPv6Address` natively for type safety.

---

## Example: Adding a New Log Source

```python
class NginxAccessPlugin(LogParserPlugin):
    @property
    def name(self) -> str:
        return "nginx_access"

    @property
    def default_log_path(self) -> str:
        return "/var/log/nginx/access.log"

    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        # ... parse Nginx combined log format ...
        pass

    def get_indicators(self) -> List[DetectionRule]:
        return [
            DetectionRule(
                name="path_traversal",
                pattern=re.compile(r"\.\./|\.\.\\|%2e%2e"),
                severity=Severity.HIGH,
                threshold=3,
                window_seconds=60,
            ),
        ]

# Register and use
registry.register("nginx_access", NginxAccessPlugin)
plugin = registry.create("nginx_access", {})
```
