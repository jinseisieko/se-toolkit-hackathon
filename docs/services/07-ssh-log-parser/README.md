# 7. SSHAuthLogParser (V1 — Legacy)

> **Deprecated.** This parser inherits from `BaseLogParser` and is kept for
> backward compatibility with test suites. The production worker uses the
> V2 [`SSHAuthPlugin`](../10-ssh-auth-plugin/) which implements
> `LogParserPlugin` and supports the `ParserRegistry`.

**Pattern:** Template Method
**Files:** `src/adapters/log_tail.py`, `src/adapters/parsers/ssh_auth.py`
**Tests:** `tests/unit/test_parsers.py` (11 tests)

---

## Purpose

Parses `/var/log/auth.log` lines for failed SSH login attempts. Extracts IP, username, timestamp, and metadata. `BaseLogParser` handles file tailing via `tail -F`; `SSHAuthLogParser` implements the regex parsing.

---

## ParsedEntry

```python
@dataclass
class ParsedEntry:
    ip: str                          # Source IP address
    user: Optional[str]              # Targeted username
    timestamp: datetime              # When the attempt occurred (UTC)
    raw_line: str                    # Original log line
    metadata: Dict[str, Any]         # Extensible: service, auth_type, port, ip_type
```

---

## SSHAuthLogParser API

```python
parser = SSHAuthLogParser()

# Parse a single line
entry = parser.parse_line(line)

# If entry is not None, feed it to the detector
if entry is not None:
    detector.record_attempt(entry.ip, entry.timestamp)
```

---

## Supported Log Patterns

| Pattern | Example |
|---------|---------|
| Failed password (valid user) | `Failed password for root from 192.0.2.1 port 22 ssh2` |
| Failed password (invalid user) | `Failed password for invalid user admin from 10.0.0.1 port 22 ssh2` |
| Failed publickey | `Failed publickey for deploy from 172.16.0.5 port 22 ssh2` |

---

## Non-Matching Lines (returns None)

- Accepted logins
- Connection closed / disconnected messages
- Empty or whitespace-only lines
- Non-SSH log entries

---

## BaseLogParser.process_stream()

```python
parser = SSHAuthLogParser()

def on_entry(entry: ParsedEntry) -> None:
    detector.record_attempt(entry.ip, entry.timestamp)

parser.process_stream("/var/log/auth.log", callback=on_entry)
# Blocks until Ctrl+C or EOF
```

- Uses `tail -F` to follow log rotation.
- Catches `FileNotFoundError` and `PermissionError` gracefully.

---

## IP Classification

| Type | Behavior |
|------|----------|
| IPv4 | Fully processed |
| IPv6 | Parsed but flagged in `metadata["ip_type"]` — V1 ignores IPv6 in detection |
| Invalid | Skipped |

---

## Timestamp Parsing

- Parses syslog format: `Apr  4 12:00:01`
- Assumes current year (syslog omits it).
- Falls back to `datetime.now(timezone.utc)` on parse failure.

---

## Design Decisions

- **`tail -F` over `watchdog`:** `tail -F` is built into every Linux system, handles log rotation natively, and requires no extra dependencies.
- **Regex-based:** Simple and fast for syslog's structured format. Can be extended with additional patterns without changing the base parser.
