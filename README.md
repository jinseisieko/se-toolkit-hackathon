# LogSentinel

A real-time server security monitor that parses authentication logs, auto-blocks malicious IPs, enriches alerts with GeoIP data, and serves a web dashboard for incident tracking.

---

## Quick Start

```bash
git clone https://github.com/jinseisieko/se-toolkit-hackathon.git
cd se-toolkit-hackathon
docker compose up --build -d
```

Dashboard: **http://\<VM_IP\>:5000**

---

## Context

### End Users

System administrators and DevOps engineers who manage Linux servers and need real-time visibility into authentication-related security threats without setting up complex SIEM tools.

### Problem

Servers are constantly probed by automated brute-force attacks targeting SSH. Admins often don't notice until it's too late, and existing tools like fail2ban provide no web visibility or structured alerting.

### Solution

LogSentinel tails `/var/log/auth.log` in real time, detects brute-force patterns, enriches alerts with geographic data, and surfaces everything through a web dashboard with JSON API and Prometheus metrics.

---

## Features

- **SSH Log Parsing** — Monitors `/var/log/auth.log` for failed SSH login attempts (password + publickey, valid + invalid users)
- **Sliding-Window Detection** — Per-IP threshold aggregation; triggers after N failures within a configurable time window
- **Auto-Blocking** — Blocks offending IPs via `ufw` (production) or logs-only mode (test)
- **GeoIP Enrichment** — Adds country/city metadata to alerts via mock or MaxMind provider
- **SQLite Database** — Persists alerts and blocked IPs with Repository pattern for future PostgreSQL migration
- **Web Dashboard** — Dark-themed UI with stats cards, alert table, and live polling
- **JSON API** — `/api/alerts`, `/api/blocked` endpoints for programmatic access
- **Prometheus Metrics** — `/metrics` endpoint with alert counts, block counts, processing times
- **Plugin System** — `LogParserPlugin` ABC + `ParserRegistry` for adding new log sources
- **CLI Test Mode** — Interactive stdin-based command interface for safe development
- **Docker Compose** — Single container deployment, monitors host auth.log via volume mount

---

## How Alerts Work

An alert triggers when:
1. **N failed SSH attempts** (default: 5) from the **same IP** within a **5-minute sliding window**
2. The IP is automatically blocked (or logged in test mode)
3. Alert is persisted to the database and displayed on the dashboard
4. Metrics are updated for Prometheus scraping
5. Console alert is emitted with severity, location, and timestamp

```
tail /var/log/auth.log → parse SSH failures → count per IP
  → threshold breached → SecurityEvent published
    → enrich with GeoIP → block IP → persist to DB → console alert
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Ubuntu VM                     │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │          LogSentinel Container            │  │
│  │                                           │  │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐  │  │
│  │  │  Flask  │  │  Worker  │  │ Metrics │  │  │
│  │  │ (Web)   │  │ (Parser) │  │ (/metrics)│ │  │
│  │  └────┬────┘  └────┬─────┘  └────┬────┘  │  │
│  │       │             │              │       │  │
│  │       └─────────────┼──────────────┘       │  │
│  │                     │                      │  │
│  │            ┌────────▼────────┐             │  │
│  │            │  SQLite (DB)    │             │  │
│  │            │  /app/data/     │             │  │
│  │            └─────────────────┘             │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  Volume: /var/log/auth.log → /var/log/auth.log  │
│  Port:   0.0.0.0:5000 → 5000                    │
└─────────────────────────────────────────────────┘
```

### Design Patterns

| Pattern | Component | Benefit |
|---------|-----------|---------|
| **Observer** | EventBroker → Detector, BlockService, Alert Channel | Decouples detection from actions |
| **Strategy** | FirewallStrategy (UFW/NoOp), GeoIP Provider, Enricher | Swap implementations without code changes |
| **Factory** | ParserRegistry, CommandFactory | Dynamic plugin discovery and instantiation |
| **Repository** | AlertRepository ABC → Peewee implementation | Isolates ORM, enables DB migration |
| **Adapter** | TelegramInputAdapter, CLIInputAdapter, ConsoleChannel | Same logic, different I/O protocols |
| **Template Method** | LogParserPlugin ABC → SSHAuthPlugin | Standardize parsers, add formats easily |
| **Application Factory** | create_app(repo) → Flask app | Testable, injectable dependencies |

---

## Deployment

### Requirements

- **OS:** Ubuntu 22.04/24.04
- **Installed:** Docker & Docker Compose
- **Access:** Read access to `/var/log/auth.log`

### Deploy

```bash
git clone https://github.com/jinseisieko/se-toolkit-hackathon.git
cd se-toolkit-hackathon
cp .env.example .env   # customize if needed
docker compose up --build -d
```

### Manage

```bash
docker compose logs -f          # Follow logs
docker compose down             # Stop
docker compose restart          # Restart
docker compose up --build -d    # Update to latest code
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `/app/data/sentinel.db` | SQLite database path inside container |
| `LOG_PATH` | `/var/log/auth.log` | Host log file to monitor |
| `BLOCK_THRESHOLD` | `5` | Failed attempts before alert triggers |
| `FIREWALL_STRATEGY` | `noop` | `noop` (log only) or `ufw` (real blocking) |
| `GEOIP_PROVIDER` | `mock` | `mock` (deterministic test data) or `maxmind` (requires .mmdb) |
| `WEB_PORT` | `5000` | Dashboard port |
| `CLI_MODE` | `false` | Enable interactive stdin commands |
| `TEST_MODE` | `true` | Restrict destructive actions |

---

## API Endpoints

### Public (No Authentication)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard (HTML) |
| `/api/alerts` | GET | Recent alerts as JSON (limit 50) |
| `/api/blocked` | GET | Blocked IPs as JSON |
| `/metrics` | GET | Prometheus-format metrics |

### Authenticated (Bearer Token Required)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/block` | POST | `Authorization: Bearer <token>` | Block an IP |
| `/api/unblock` | POST | `Authorization: Bearer <token>` | Unblock an IP |

Set the token via `API_TOKEN` in `.env`. If empty, block/unblock endpoints are disabled (404).

### Example Responses

```json
GET /api/alerts
[
  {
    "ip": "198.51.100.77",
    "attempts": 5,
    "service": "ssh",
    "first_seen": "2026-04-04T10:51:08+00:00",
    "last_seen": "2026-04-04T10:51:08+00:00",
    "blocked": false
  }
]
```

```bash
# Block an IP (requires Bearer token)
curl -X POST http://localhost:5000/api/block \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"ip": "10.0.0.1", "reason": "suspicious activity"}'
# → {"ip": "10.0.0.1", "reason": "suspicious activity", "blocked": true}

# Unblock an IP
curl -X POST http://localhost:5000/api/unblock \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"ip": "10.0.0.1"}'
# → {"ip": "10.0.0.1", "blocked": false}
```

### Example Metrics

```
logsentinel_alerts_total{service="ssh"} 1
logsentinel_blocks_total{strategy="NoOpStrategy"} 1
logsentinel_parse_duration_seconds{parser="ssh_auth",quantile="avg"} 0.005155
```

---

## Project Structure

```
src/
├── core/                          # Domain logic (patterns, ABCs)
│   ├── plugins/                   # Plugin system (V2)
│   │   ├── parser_plugin.py       # LogParserPlugin ABC, ParsedEntry
│   │   └── registry.py            # ParserRegistry (Factory)
│   ├── enrichment/                # Enrichment pipeline (V2)
│   │   └── base.py                # Enricher ABC, EnrichedEvent, GeoLocation
│   ├── alerting/                  # Alert channels (V2)
│   │   └── channel.py             # AlertChannel ABC
│   ├── observability/             # Metrics (V2)
│   │   └── metrics.py             # MetricsCollector (Prometheus format)
│   ├── events.py                  # EventBroker (Observer)
│   ├── detector.py                # ThresholdDetector (sliding window)
│   ├── blocking.py                # FirewallStrategy ABC (Strategy)
│   ├── repositories.py            # AlertRepository ABC
│   └── services/
│       └── block_service.py       # BlockService + BlockRepository ABC
├── adapters/                      # External integrations
│   ├── parsers/plugins/
│   │   └── ssh_auth.py            # SSHAuthPlugin (Template Method)
│   ├── firewall/
│   │   ├── ufw.py                 # UFWStrategy (production)
│   │   └── noop.py                # NoOpStrategy (test mode)
│   ├── geoip/
│   │   └── geo_ip.py              # GeoIPEnricher (mock + MaxMind)
│   ├── alerting/
│   │   └── console.py             # ConsoleChannel (CLI alerts)
│   └── telegram.py                # TelegramInputAdapter
├── infrastructure/                # Database
│   ├── db.py                      # init_database()
│   └── models.py                  # Peewee models
├── interfaces/                    # Entry points
│   ├── commands/
│   │   ├── handler.py             # CommandHandler
│   │   ├── cli.py                 # CLIInputAdapter
│   │   └── factory.py             # create_command_handler()
│   └── web/
│       ├── app.py                 # Flask app factory
│       ├── templates/dashboard.html
│       └── static/style.css
├── utils/
│   └── validation.py              # IP validator
└── worker.py                      # Main entrypoint — wires all services
```

---

## Quality Metrics

| Metric | Value |
|--------|-------|
| **Unit tests** | 110 passing |
| **Type checking** | mypy --strict clean |
| **Linting** | flake8 clean |
| **Source files** | 40+ |
| **Design patterns** | 7 |

### Test

```bash
pytest tests/unit/ -v
mypy src/ --strict
```

---

## Documentation

- **Per-service docs:** [`docs/services/`](docs/services/README.md)
- **Implementation log:** [`docs/progress/IMPLEMENTATION_LOG.md`](docs/progress/IMPLEMENTATION_LOG.md)
