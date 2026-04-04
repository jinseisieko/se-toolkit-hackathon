# LogSentinel

A real-time server security monitor that parses authentication logs, auto-blocks malicious IPs, and sends instant Telegram alerts with a web dashboard for incident tracking.

---

## Features

- **Threat Detection** — Parses `/var/log/auth.log` for brute-force SSH attempts and suspicious activity
- **Automated Response** — Blocks malicious IPs via `ufw`/`iptables`
- **Telegram Alerts** — Real-time notifications and admin commands (`/status`, `/unblock <IP>`, `/stats`)
- **Web Dashboard** — View alerts, blocked IPs, attack timeline, and configure settings
- **Test Mode** — Safely develop and demo with restricted access and no destructive actions

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
│  Blocks: ufw / iptables                         │
└─────────────────────────────────────────────────┘
```

### Components

| Component | Tech | Role |
|-----------|------|------|
| **Backend / Web** | Flask + Jinja2 | Dashboard, REST API, config panel |
| **Log Worker** | Python + `tail` + `re` | Tails auth.log, detects patterns, triggers blocks |
| **Telegram Bot** | `python-telegram-bot` | Pushes alerts, accepts admin commands |
| **Database** | Peewee + SQLite | Stores alerts, blocked IPs, bot logs |
| **Deployment** | Docker Compose | Single-VM orchestration |

---

## Stack

- **Language:** Python 3.11+
- **Web Framework:** Flask + Jinja2
- **ORM / DB:** Peewee + SQLite
- **Telegram Bot:** `python-telegram-bot` (v20+)
- **Deployment:** Docker Compose

---

## Quick Start

### Prerequisites

- Ubuntu VM (or any Linux host)
- Docker & Docker Compose
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))

### Setup

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd se-toolkit-hackathon
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your bot token and chat ID
   ```

3. **Run**
   ```bash
   docker compose up -d --build
   ```

4. **Access**
   - Web UI: `http://<VM_IP>:5000`
   - Telegram: send `/start` to your bot

---

## Configuration

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token |
| `TEST_MODE` | `true` to restrict access to `TEST_CHAT_ID` only |
| `TEST_CHAT_ID` | Your Telegram chat ID (required when `TEST_MODE=true`) |
| `BLOCK_THRESHOLD` | Number of failed attempts before blocking (default: `5`) |
| `DB_PATH` | Path to SQLite database (default: `/app/data/sentinel.db`) |

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot |
| `/status` | Show active and blocked IP counts |
| `/stats` | View detailed attack statistics |
| `/unblock <IP>` | Unblock a specific IP |

---

## Project Structure

```
.
├── app.py              # Flask web server + API
├── worker.py           # Log parser + auto-block logic
├── models.py           # Peewee database models
├── bot/
│   └── main.py         # Telegram bot handlers
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── data/               # SQLite database (gitignored)
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Why This Project?

- **Cybersecurity-focused** — Real log analysis, threat detection, and automated response
- **Single VM** — Everything runs on one machine, no cloud dependencies
- **Practical & Demoable** — Easy to demonstrate with simulated attacks
- **Extensible** — Start with SSH brute-force, expand to web logs, API abuse, threat-feed enrichment
