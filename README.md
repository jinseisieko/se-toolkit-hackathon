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

- **Log Parsing** — Tails `/var/log/auth.log` and detects failed SSH login attempts using regex
- **Threshold Detection** — Aggregates failures per IP; triggers an alert after a configurable threshold (default: 5 attempts)
- **Auto-Block** — Blocks offending IPs via `ufw` / `iptables`
- **SQLite Database** — Stores alerts, blocked IPs, and bot interaction logs (Peewee ORM)
- **Web Dashboard** — View real-time alert feed, blocked IP table, and basic stats
- **Telegram Bot** — Receive alerts and run `/start`, `/status` commands

### Planned (Version 2)

- **Telegram Admin Commands** — `/unblock <IP>`, `/stats` with detailed attack breakdown
- **Attack Timeline View** — Visual timeline of attacks on the web dashboard
- **Geo-IP Enrichment** — Show attacker location on the dashboard
- **Test Mode** — Restrict bot access to a specific chat ID, disable destructive commands for safe development
- **Docker Compose Deployment** — All services containerized and deployable with one command

---

## Usage

### Telegram Bot

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/status` | Show active and blocked IP counts |
| `/stats` | View detailed attack statistics |
| `/unblock <IP>` | Unblock a specific IP |

### Web Dashboard

Navigate to `http://<VM_IP>:5000` to view the dashboard, browse alerts, see blocked IPs, and configure the block threshold.

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

## Deployment

### Requirements

- **OS:** Ubuntu 24.04 (or any recent Ubuntu/Debian-based system)
- **Installed on VM:**
  - Docker & Docker Compose
  - `sudo` access (for log reading and firewall rules)
  - A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Step-by-Step

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/se-toolkit-hackathon.git
   cd se-toolkit-hackathon
   ```

2. **Create data directory**
   ```bash
   mkdir -p data
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   BOT_TOKEN=your:telegram_bot_token
   TEST_MODE=true
   TEST_CHAT_ID=your_telegram_chat_id
   BLOCK_THRESHOLD=5
   DB_PATH=/app/data/sentinel.db
   ```

4. **Start services**
   ```bash
   docker compose up -d --build
   ```

5. **Access the product**
   - **Web Dashboard:** `http://<VM_IP>:5000`
   - **Telegram Bot:** Send `/start` to your bot

6. **Switch to production** (optional)
   - Set `TEST_MODE=false` in `.env`
   - Add `--cap-add=NET_ADMIN` to the `worker` service in `docker-compose.yml` to enable auto-blocking via `ufw`/`iptables`
   - Restart: `docker compose down && docker compose up -d`

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
├── LICENSE             # MIT License
└── README.md
```
