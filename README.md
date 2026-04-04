# LogSentinel

A real-time server security monitor that parses authentication logs, auto-blocks malicious IPs, and sends instant Telegram alerts with a web dashboard for incident tracking.

---

## Demo

<!-- Add screenshots here -->
<!-- Example: Screenshot of the web dashboard showing the alerts table -->
<!-- Example: Screenshot of the Telegram bot receiving a real-time alert -->

---

## Context

### End Users

System administrators and DevOps engineers who manage Linux servers and need visibility into authentication-related security threats without setting up complex SIEM tools.

### Problem

Servers are constantly probed by automated brute-force attacks targeting SSH and other authentication services. Admins often don't notice these attacks until it's too late, and existing tools like fail2ban provide no real-time visibility or remote alerting.

### Solution

LogSentinel watches authentication logs in real time, automatically blocks malicious IPs, and sends instant alerts to your Telegram phone — plus a simple web dashboard for reviewing incidents and managing blocks.

---

## Features

### Implemented (Version 1)

- **SSH Log Parsing** — Tails `/var/log/auth.log` and detects failed SSH login attempts (password + publickey)
- **Threshold Detection** — Sliding-window aggregation per IP; publishes events when configurable threshold is breached
- **Auto-Block** — Blocks offending IPs via `ufw` (production) or log-only mode (test)
- **SQLite Database** — Stores alerts and blocked IPs (Peewee ORM, Repository pattern)
- **Web Dashboard** — Dark-themed UI with alert table, stats cards, and JSON API (`/api/alerts`, `/api/blocked`)
- **Telegram Bot** — `/start`, `/status`, `/unblock <IP>`, `/block <IP>` with test mode chat restriction
- **CLI Test Mode** — Interactive stdin-based command interface for safe development without Telegram or firewall side effects
- **Design Patterns** — Observer, Strategy, Repository, Factory, Adapter, Template Method, Application Factory

### Planned (Version 2)

- **Attack Timeline View** — Visual timeline of attacks on the web dashboard
- **Geo-IP Enrichment** — Show attacker location on the dashboard
- **Additional Log Parsers** — Apache, Nginx, custom formats
- **Advanced Alert Channels** — Slack, email, webhook
- **Docker Compose Deployment** — All services containerized and deployable with one command

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Ubuntu VM                     │
│                                                 │
│  ┌──────────┐   ┌──────────┐   ┌─────────────┐  │
│  │  Flask   │   │  Worker  │   │  Telegram   │  │
│  │  (Web)   │   │ (Parser) │   │    Bot      │  │
│  └────┬─────┘   └────┬─────┘   └──────┬──────┘  │
│       │              │                 │         │
│       └──────────────┼─────────────────┘         │
│                      │                           │
│              ┌───────▼───────┐                   │
│              │  SQLite (DB)  │                   │
│              └───────────────┘                   │
│                                                 │
│  Reads: /var/log/auth.log                       │
│  Blocks: ufw / iptables (or NoOp for testing)   │
└─────────────────────────────────────────────────┘
```

### Design Patterns

| Pattern | Component | Benefit |
|---------|-----------|---------|
| **Observer** | EventBroker → Detector, BlockService, Telegram | Decouples detection from actions; easy to add new responders |
| **Strategy** | FirewallStrategy: UFWStrategy / NoOpStrategy | Swap blocking mechanisms without changing core logic |
| **Factory** | CommandFactory creates handlers from command strings | Centralized routing; easy to extend with new commands |
| **Repository** | AlertRepository ABC → PeeweeAlertRepository | Isolates ORM; simplifies testing and future DB migrations |
| **Adapter** | TelegramInputAdapter, CLIInputAdapter | Same handlers, different input sources (test mode ready) |
| **Template Method** | BaseLogParser → SSHAuthLogParser | Standardize log parsing while allowing format-specific rules |
| **Application Factory** | create_app(alert_repo) → Flask app | Testable with in-memory DB, swappable databases in prod |

---

## Usage

### Telegram Bot

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with available commands |
| `/status` | Show active and blocked IP counts |
| `/unblock <IP>` | Unblock a specific IP |
| `/block <IP> [reason]` | Manually block an IP |

### CLI Test Mode

```bash
# Run the worker with NoOpStrategy (test mode)
# Then in another terminal, interact via stdin:
# ❯ /status
# ✅ Active: 5 | Blocked: 2
# ❯ /unblock 192.0.2.1
# ✅ Unblocked 192.0.2.1
# ❯ quit
```

### Web Dashboard

Navigate to `http://<VM_IP>:5000` to view the dashboard. The JSON API is available at `/api/alerts` and `/api/blocked`.

---

## Stack

- **Language:** Python 3.11+
- **Web Framework:** Flask + Jinja2
- **ORM / DB:** Peewee + SQLite
- **Telegram Bot:** `python-telegram-bot` (v20+)
- **Testing:** pytest + pytest-asyncio, in-memory SQLite
- **Type Checking:** mypy --strict

---

## Project Structure

```
src/
├── core/                          # Domain logic (patterns, ABCs)
│   ├── events.py                  # EventBroker, SecurityEvent (Observer)
│   ├── detector.py                # ThresholdDetector (sliding window)
│   ├── blocking.py                # FirewallStrategy ABC (Strategy)
│   ├── repositories.py            # Alert dataclass, AlertRepository ABC
│   └── services/
│       └── block_service.py       # BlockService + BlockRepository ABC
├── adapters/                      # External integrations
│   ├── firewall/
│   │   ├── ufw.py                 # UFWStrategy (production)
│   │   └── noop.py                # NoOpStrategy (test mode)
│   ├── parsers/
│   │   └── ssh_auth.py            # SSHAuthLogParser (Template Method)
│   ├── log_tail.py                # BaseLogParser + ParsedEntry
│   └── telegram.py                # TelegramInputAdapter
├── infrastructure/                # DB, models, config
│   ├── db.py                      # init_database() helper
│   └── models.py                  # Peewee models (Alert, BlockedIP)
├── interfaces/                    # CLI, Telegram, Web entrypoints
│   ├── commands/
│   │   ├── handler.py             # CommandHandler, CommandContext
│   │   ├── cli.py                 # CLIInputAdapter (stdin reader)
│   │   └── factory.py             # create_command_handler()
│   └── web/
│       ├── app.py                 # Flask application factory
│       ├── templates/
│       │   └── dashboard.html     # Jinja2 dashboard
│       └── static/
│           └── style.css          # Dark theme
├── utils/
│   └── validation.py              # IP validator
tests/
├── conftest.py
└── unit/
    ├── test_events.py             # EventBroker (6 tests)
    ├── test_detector.py           # ThresholdDetector (6 tests)
    ├── test_blocking.py           # FirewallStrategy (12 tests)
    ├── test_block_service.py      # BlockService (6 tests)
    ├── test_repositories.py       # PeeweeAlertRepository (8 tests)
    ├── test_command_handler.py    # CommandHandler + CLI (11 tests)
    ├── test_telegram_adapter.py   # TelegramInputAdapter (7 tests)
    ├── test_parsers.py            # SSHAuthLogParser (11 tests)
    └── test_web_dashboard.py      # Flask dashboard (7 tests)
docs/
├── progress/
│   └── IMPLEMENTATION_LOG.md      # Per-service implementation log
└── services/                      # Per-service documentation
    ├── README.md                  # Index + wiring guide
    ├── 01-event-broker/
    ├── 02-threshold-detector/
    ├── 03-firewall-strategy/
    ├── 04-alert-repository/
    ├── 05-command-handler/
    ├── 06-telegram-adapter/
    ├── 07-ssh-log-parser/
    └── 08-flask-dashboard/
```

---

## Quality Metrics

| Metric | Value |
|--------|-------|
| **Unit tests** | 74 passing |
| **Type checking** | mypy --strict clean (28 source files) |
| **Services implemented** | 8/8 |
| **Design patterns used** | 7 |

---

## Development

### Setup

```bash
git clone https://github.com/<your-username>/se-toolkit-hackathon.git
cd se-toolkit-hackathon
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/unit/ -v
```

### Type Check

```bash
mypy src/ --strict
```

### Service Documentation

Per-service documentation is in [`docs/services/`](docs/services/README.md).
Implementation progress is tracked in [`docs/progress/IMPLEMENTATION_LOG.md`](docs/progress/IMPLEMENTATION_LOG.md).
