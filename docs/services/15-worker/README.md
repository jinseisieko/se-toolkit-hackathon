# 15. Worker (Log Monitoring Pipeline)

**Pattern:** Composition + Pipeline
**Files:** `src/worker.py`
**Tests:** Integration-level (Docker Compose deployment)

---

## Purpose

The core monitoring pipeline. Tails the auth log, detects brute-force threshold breaches, blocks offending IPs, enriches alerts with GeoIP, and stores everything in the shared SQLite database. **No web server, no CLI, no Telegram** — those run as separate containers.

---

## Pipeline Flow

```
/var/log/auth.log
        │
        ▼
┌─────────────────────┐
│  ParserRegistry     │  → SSHAuthPlugin
│  process_stream()   │
└────────┬────────────┘
         │ ParsedEntry
         ▼
┌─────────────────────┐
│  ThresholdDetector  │  → sliding-window aggregation
│  record_attempt()   │
└────────┬────────────┘
         │ SecurityEvent (on breach)
         ▼
┌─────────────────────┐
│  EventBroker        │  → publishes to subscribers
│  publish()          │
└────────┬────────────┘
         │
    ┌────┴────────────────────────┐
    ▼                             ▼
┌──────────────┐    ┌─────────────────────┐
│ BlockService │    │ on_security_event    │
│ handle_event │    │ (subscriber)         │
└──────────────┘    └────────┬─────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              ┌──────────┐    ┌──────────────┐
              │ GeoIP     │    │ AlertChannel │
              │ Enricher  │    │ send()       │
              └──────────┘    └──────┬───────┘
                                     │
                              ┌──────▼──────┐
                              │ Metrics      │
                              │ Collector    │
                              └─────────────┘
```

All data is persisted to the shared SQLite database. The web service and Telegram bot read from the same database independently.

---

## Components Wired

| Step | Component | Source File |
|------|-----------|-------------|
| 1 | Database (SQLite + Peewee) | `src/infrastructure/db.py`, `src/infrastructure/models.py` |
| 2 | MetricsCollector | `src/core/observability/metrics.py` |
| 3 | EventBroker | `src/core/events.py` |
| 4 | ParserRegistry + SSHAuthPlugin | `src/core/plugins/registry.py`, `src/adapters/parsers/plugins/ssh_auth.py` |
| 5 | GeoIPEnricher | `src/adapters/geoip/geo_ip.py` |
| 6 | FirewallStrategy (UFW/NoOp) | `src/adapters/firewall/ufw.py`, `src/adapters/firewall/noop.py` |
| 7 | BlockService | `src/core/services/block_service.py` |
| 8 | AlertChannel (Console) | `src/adapters/alerting/console.py` |
| 9 | ThresholdDetector | `src/core/detector.py` |
| 10 | Event subscriber (persist → block → enrich → alert → metric) | Inline in `worker.py` |
| 11 | Log parser main loop | `SSHAuthPlugin.process_stream()` |

---

## Configuration

All configuration comes from environment variables (via `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `data/sentinel.db` | SQLite database path |
| `LOG_PATH` | `/var/log/auth.log` | Log file to monitor |
| `BLOCK_THRESHOLD` | `5` | Failed attempts before alert |
| `FIREWALL_STRATEGY` | `noop` | `noop` or `ufw` |
| `GEOIP_PROVIDER` | `mock` | `mock` or `maxmind` |
| `API_TOKEN` | `None` | Bearer token for block/unblock API |

---

## Concurrency Model

The worker runs as a **single process, single thread**:
- `process_stream()` blocks on `tail -F`, calling `on_entry()` synchronously per parsed line.
- `on_entry()` records the attempt, which may trigger `ThresholdDetector` to publish a `SecurityEvent`.
- The event subscriber runs synchronously in the same thread.
- `asyncio` is used only for calling the async `AlertChannel.send()` — wrapped in `new_event_loop().run_until_complete()`.

Shutdown is triggered by `SIGINT`/`SIGTERM` which sets a `threading.Event` (used by `tail -F` subprocess termination).

---

## Event Subscriber (`on_security_event`)

The core wiring function — called every time `ThresholdDetector` publishes a `SecurityEvent`:

```python
def on_security_event(event: SecurityEvent) -> None:
    # 1. Log the breach
    # 2. Persist to database (alert_repo.create)
    # 3. Block the IP (block_svc.handle_event)
    # 4. Record block metric (metrics.record_block)
    # 5. Enrich with GeoIP (geoip.enrich)
    # 6. Send alert via channel (alert_channel.send)
    # 7. Record alert metric (metrics.record_alert)
```

---

## Design Decisions

- **Pipeline-only responsibility:** The worker does one thing — monitor logs, detect threats, store alerts. Web, CLI, and Telegram are separate services that read the same data.
- **Single process, single thread:** Keeps deployment simple (one Docker container for monitoring). No locks or queues needed.
- **EventBroker as coordination hub:** All cross-service communication flows through the broker, making it easy to add new subscribers without touching the worker.
- **Inline subscriber:** The `on_security_event` function is defined inline rather than as a separate class. This is the composition root, not a reusable component.
- **Sync/async bridge:** The alert channel uses `asyncio.new_event_loop()` + `run_until_complete()` because the worker is synchronous but `AlertChannel.send()` is async.
