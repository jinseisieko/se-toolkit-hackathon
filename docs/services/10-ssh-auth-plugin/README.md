# 10. SSHAuthPlugin (V2 SSH Log Parser)

**Pattern:** Strategy (via `LogParserPlugin`)
**Files:** `src/adapters/parsers/plugins/ssh_auth.py`
**Tests:** `tests/unit/plugins/test_ssh_plugin.py` (17 tests)

---

## Purpose

V2 replacement for `SSHAuthLogParser`. Parses `/var/log/auth.log` for failed SSH login attempts and emits normalised `ParsedEntry` objects. Implements `LogParserPlugin` so it plugs into the `ParserRegistry`.

---

## SSHAuthPlugin API

```python
from src.adapters.parsers.plugins.ssh_auth import SSHAuthPlugin

# Standalone usage
plugin = SSHAuthPlugin()
entry = plugin.parse_line("Apr  4 12:00:01 server sshd[1]: Failed password for root from 192.0.2.1 port 22 ssh2")

# Via ParserRegistry (recommended)
registry = ParserRegistry()
registry.register("ssh_auth", SSHAuthPlugin)
plugin = registry.create("ssh_auth", {"log_path": "/var/log/auth.log"})
```

### Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `log_path` | `/var/log/auth.log` | Path to the log file to monitor |

### Plugin Properties

| Property | Value |
|----------|-------|
| `name` | `"ssh_auth"` |
| `default_log_path` | Configurable via `log_path` |

---

## Supported Log Patterns

| Pattern | Example |
|---------|---------|
| Failed password (valid user) | `Failed password for root from 192.0.2.1 port 22 ssh2` |
| Failed password (invalid user) | `Failed password for invalid user admin from 10.0.0.1 port 22 ssh2` |
| Failed publickey | `Failed publickey for deploy from 172.16.0.5 port 22 ssh2` |

### Event Types

| SSH Pattern | `event_type` |
|-------------|-------------|
| `Failed password` | `"failed_auth"` |
| `Failed publickey` | `"failed_publickey"` |

---

## Non-Matching Lines (returns `None`)

- Accepted logins
- Connection closed / disconnected messages
- Empty or whitespace-only lines
- Non-SSH log entries

---

## Detection Rules (`get_indicators()`)

| Rule | Severity | Threshold | Window |
|------|----------|-----------|--------|
| `ssh_failed_password` | HIGH | 5 | 300s |
| `ssh_failed_publickey` | MEDIUM | 10 | 600s |

---

## process_stream()

```python
def on_entry(entry: ParsedEntry) -> None:
    print(f"SSH failure from {entry.ip}")

plugin.process_stream("/var/log/auth.log", callback=on_entry)
# Blocks until Ctrl+C
```

- Uses `tail -F` to follow log rotation.
- Catches `FileNotFoundError` and `PermissionError` gracefully.

---

## IP Classification

| Type | Behavior |
|------|----------|
| IPv4 | Fully processed, stored as `IPv4Address` in `ParsedEntry.ip` |
| IPv6 | Parsed, flagged in `meta["ip_type"]`, stored as `IPv6Address` |
| Invalid | Skipped |

---

## V1 vs V2 Comparison

| Aspect | V1 `SSHAuthLogParser` | V2 `SSHAuthPlugin` |
|--------|----------------------|-------------------|
| Base class | `BaseLogParser` | `LogParserPlugin` |
| IP type | `str` | `IPv4Address \| IPv6Address` |
| Config | Hardcoded path | Injected via `config` dict |
| Registry | Not supported | `ParserRegistry` |
| Event type | `metadata["service"]` | `event_type` field |
| Status | Deprecated | Production |

---

## Design Decisions

- **Typed IP addresses:** Uses `ipaddress.IPv4Address`/`IPv6Address` objects instead of strings, eliminating parsing errors downstream.
- **Separate `event_type`:** Distinguishes password from publickey failures explicitly, enabling different detection thresholds.
- **Inherits `LogParserPlugin.__init__`:** Receives config from registry automatically, no manual wiring needed.
