# 15. Worker (Service Wiring)

**Pattern:** Composition + Application Entry Point
**Files:** `src/worker.py`
**Tests:** Integration-level (Docker Compose deployment)

---

## Purpose

The main production entrypoint. Wires all LogSentinel services together into a coherent monitoring pipeline and runs the continuous log-monitoring loop.

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
    ┌────┴────────────────────┐
    ▼                         ▼
┌──────────────┐    ┌─────────────────┐
│ BlockService │    │ on_security_event│
│ handle_event │    │ (subscriber)     │
└──────────────┘    └────────┬─────────┘
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
| 10 | Event subscriber (enrich → block → alert → metric) | Inline in `worker.py` |
| 11 | CommandHandler | `src/interfaces/commands/factory.py` |
| 12 | Flask Dashboard | `src/interfaces/web/app.py` |
| 13 | CLI Input Adapter (optional) | `src/interfaces/commands/cli.py` |
| 14 | Log parser main loop | `SSHAuthPlugin.process_stream()` |

---

## Configuration

All configuration comes from environment variables (via `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `data/sentinel.db` | SQLite database path |
| `LOG_PATH` | `/var/log/auth.log` | Log file to monitor |
| `BLOCK_THRESHOLD` | `5` | Failed attempts before alert |
| `FIREWALL_STRATEGY` | `noop` | `noop` or `ufw` |
| `TEST_MODE` | `true` | Restricts destructive actions |
| `GEOIP_PROVIDER` | `mock` | `mock` or `maxmind` |
| `WEB_HOST` | `0.0.0.0` | Dashboard bind address |
| `WEB_PORT` | `5000` | Dashboard port |
| `CLI_MODE` | `true` | Enable interactive CLI commands |
| `API_TOKEN` | `None` | Bearer token for block/unblock API |

---

## Concurrency Model

| Thread | Purpose |
|--------|---------|
| **Main** | `process_stream()` — blocks on `tail -F`, calls `on_entry()` per parsed line |
| **Web** | Flask development server in a daemon thread |
| **CLI** | stdin reader (if `CLI_MODE=true`), daemon thread |

Signal handlers (`SIGINT`, `SIGTERM`) set a `threading.Event` to trigger graceful shutdown.

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

- **Single process, multiple threads:** The worker runs as one process with Flask and CLI in daemon threads. This keeps deployment simple (single Docker container).
- **EventBroker as coordination hub:** All cross-service communication flows through the broker, making it easy to add new subscribers without touching the worker.
- **Inline subscriber vs. dedicated service:** The `on_security_event` function is defined inline rather than as a separate class. This is intentional — it's the composition root, not a reusable component. If the pipeline grows more complex, it can be extracted into a `PipelineService`.
- **Async event loop in sync context:** The alert channel uses `asyncio.new_event_loop()` + `run_until_complete()` because the worker is synchronous but `AlertChannel.send()` is async. This bridges the sync/async gap without converting the entire worker to asyncio.
