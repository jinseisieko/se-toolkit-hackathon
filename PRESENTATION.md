# Slide 1: Title

# LogSentinel

**Real-Time Server Security Monitor**

- **Name:** jinseisieko
- **Email:** jinseisieko@university.edu
- **Group:** [Your Group]

---

# Slide 2: Context

## End Users
System administrators and DevOps engineers managing Linux servers who need real-time visibility into SSH brute-force attacks without deploying complex SIEM infrastructure.

## The Problem
Servers are constantly probed by automated brute-force attacks targeting SSH. Admins often don't notice until it's too late, and existing tools like fail2ban provide no web dashboard, structured alerting, or geographic enrichment.

## The Solution
**LogSentinel** tails `/var/log/auth.log` in real time, detects brute-force patterns, auto-blocks offending IPs, enriches alerts with GeoIP data, and surfaces everything through a dark-themed web dashboard with JSON API and Prometheus metrics.

---

# Slide 3: Implementation

## How It Was Built
- **Python 3.11+** with strict type checking (mypy --strict) and flake8 linting
- **148 unit tests** across 40+ source files
- **7 design patterns:** Observer, Strategy, Factory, Repository, Adapter, Template Method, Application Factory
- **Docker Compose** orchestrates 3 independent containers (worker, web, telegram) sharing a SQLite volume

## Version 1 — Core Services
- EventBroker (pub/sub), ThresholdDetector (sliding-window), FirewallStrategy (UFW/NoOp)
- AlertRepository (Peewee + SQLite), CommandHandler + CLI, Telegram adapter, SSH log parser, Flask dashboard

## Version 2 — Platform Services
- Plugin system (LogParserPlugin ABC + ParserRegistry) for extensible log parsing
- GeoIP enrichment pipeline (mock + MaxMind provider)
- AlertChannel abstraction (console, Telegram-ready)
- Prometheus MetricsCollector + `/metrics` endpoint
- Authenticated block/unblock API (Bearer token RBAC)
- Telegram bot as standalone service with admin commands

---

# Slide 4: Demo

## Pre-Recorded Video Demonstration

> **Insert your 2-minute video with voice-over here**
>
> Recommended coverage:
> 1. Deploy with `docker compose up --build -d`
> 2. Show simulated SSH brute-force attack being detected
> 3. Open dashboard at `http://<VM_IP>:5000` — stats cards, alert table, blocked IPs
> 4. Demonstrate blocking an IP via the dashboard (with token)
> 5. Show `/api/alerts` JSON endpoint and `/metrics` Prometheus output
> 6. Highlight color-coded IPs (green=active, red=blocked) and toast notifications

---

# Slide 5: Links

## GitHub Repository
**https://github.com/jinseisieko/se-toolkit-hackathon**

[QR CODE: Insert QR pointing to the GitHub repo]

## Deployed Product
**Dashboard: `http://<VM_IP>:5000`**
(Deployed on Ubuntu VM via Docker Compose)

[QR CODE: Insert QR pointing to the live dashboard]
