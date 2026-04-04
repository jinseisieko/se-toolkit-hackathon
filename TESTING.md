# Testing LogSentinel

## Prerequisites

```bash
# Ensure you are in the virtual environment
source .venv/bin/activate

# Or create it if it doesn't exist
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 1. Quick Verification

Run all unit tests and type checks in one line:

```bash
pytest tests/unit/ -q && mypy src/ --strict
```

Expected output:
```
74 passed in 0.XXs
Success: no issues found in 28 source files
```

---

## 2. Run All Unit Tests

```bash
pytest tests/unit/ -v
```

This runs **74 tests** across 9 test files:

| Test File | Tests | What it verifies |
|-----------|-------|-----------------|
| `test_events.py` | 6 | EventBroker pub/sub, exception handling |
| `test_detector.py` | 6 | Sliding window, threshold firing, multi-IP |
| `test_blocking.py` | 12 | UFWStrategy subprocess calls, NoOpStrategy safety, IP validation |
| `test_block_service.py` | 6 | Block/unblock orchestration, NoOp end-to-end |
| `test_repositories.py` | 8 | Real SQLite operations, limits, ordering |
| `test_command_handler.py` | 11 | Command routing, permissions, CLI parsing |
| `test_telegram_adapter.py` | 7 | Chat auth, message handling, async reply |
| `test_parsers.py` | 11 | SSH log regex, timestamps, IPv4/IPv6 |
| `test_web_dashboard.py` | 7 | HTML rendering, JSON API, empty state |

### Run a Single Service's Tests

```bash
pytest tests/unit/test_events.py -v        # EventBroker
pytest tests/unit/test_detector.py -v       # ThresholdDetector
pytest tests/unit/test_blocking.py -v       # FirewallStrategy
pytest tests/unit/test_block_service.py -v  # BlockService
pytest tests/unit/test_repositories.py -v   # AlertRepository
pytest tests/unit/test_command_handler.py -v # CommandHandler + CLI
pytest tests/unit/test_telegram_adapter.py -v # TelegramInputAdapter
pytest tests/unit/test_parsers.py -v        # SSHAuthLogParser
pytest tests/unit/test_web_dashboard.py -v  # Flask Dashboard
```

---

## 3. Type Checking

```bash
mypy src/ --strict
```

All 28 source files must pass `mypy --strict` with zero errors.

---

## 4. Interactive Demo

Run the full end-to-end demo that simulates an SSH brute-force attack:

```bash
python demo.py
```

This shows:
1. Database initialization
2. EventBroker subscription
3. ThresholdDetector configuration
4. NoOpStrategy (safe test mode)
5. SSH log parser processing 11 fake log lines
6. 3 threshold breaches detected (192.0.2.1, 10.0.0.1, 172.16.0.5)
7. Alerts stored in SQLite and queryable
8. Command handler: status, unblock, block, permission denied
9. Flask dashboard HTML + JSON API responses

---

## 5. Linting

```bash
flake8 src/ tests/ --max-line-length=100
```

---

## Test Architecture

### No External Dependencies

All tests are fully isolated:
- **No real auth.log** — parsed from hardcoded strings
- **No real Telegram** — mocked `Update` and `Message` objects
- **No real firewall** — `NoOpStrategy` never calls `subprocess.run`
- **No real web server** — Flask test client with in-memory SQLite
- **No real database files** — `SqliteDatabase(":memory:")` for every test

### Running Individual Tests

```bash
# Specific test class
pytest tests/unit/test_detector.py::TestThresholdDetectorHappyPath -v

# Specific test method
pytest tests/unit/test_detector.py::TestThresholdDetectorEdgeCases::test_resets_counter_after_window_expires -v

# Tests matching a keyword
pytest tests/unit/ -k "unblock" -v

# Show print output
pytest tests/unit/ -s -k "status"

# Coverage (if installed)
pytest tests/unit/ --cov=src --cov-report=term-missing
```

---

## What the Tests Cover

### Happy Path
- Normal operations: correct input produces correct output
- Events are published and received
- Commands are routed to correct handlers
- Database stores and retrieves data

### Edge Cases
- **Empty input**: Empty database, empty log lines, no subscribers
- **Invalid input**: Malformed IPs, bad timestamps, unknown commands
- **Permission denied**: Restricted users cannot execute destructive commands
- **Strategy safety**: NoOpStrategy never touches `subprocess.run`
- **Failure propagation**: Handler exceptions don't crash the broker
