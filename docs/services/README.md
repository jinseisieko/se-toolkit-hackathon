# LogSentinel — Service Documentation

Complete documentation for all 15 core services.

---

## V1 — Core Services

| # | Service | Pattern | Tests | Docs |
|---|---------|---------|-------|------|
| 1 | [EventBroker + SecurityEvent](01-event-broker/) | Observer | 6 | [README](01-event-broker/README.md) |
| 2 | [ThresholdDetector](02-threshold-detector/) | Aggregator + Observer | 6 | [README](02-threshold-detector/README.md) |
| 3 | [FirewallStrategy + BlockService](03-firewall-strategy/) | Strategy + Composition | 18 | [README](03-firewall-strategy/README.md) |
| 4 | [AlertRepository + Peewee Models](04-alert-repository/) | Repository | 8 | [README](04-alert-repository/README.md) |
| 5 | [CommandHandler + CLIInputAdapter](05-command-handler/) | Factory + Adapter | 11 | [README](05-command-handler/README.md) |
| 6 | [TelegramInputAdapter](06-telegram-adapter/) | Adapter | 7 | [README](06-telegram-adapter/README.md) |
| 7 | [SSHAuthLogParser](07-ssh-log-parser/) (V1 legacy) | Template Method | 11 | [README](07-ssh-log-parser/README.md) |
| 8 | [Flask Dashboard](08-flask-dashboard/) | Application Factory | 16 | [README](08-flask-dashboard/README.md) |

## V2 — Platform Services

| # | Service | Pattern | Tests | Docs |
|---|---------|---------|-------|------|
| 9 | [ParserRegistry + LogParserPlugin](09-plugin-system/) | Factory + Strategy | 11 | [README](09-plugin-system/README.md) |
| 10 | [SSHAuthPlugin](10-ssh-auth-plugin/) | Strategy | 17 | [README](10-ssh-auth-plugin/README.md) |
| 11 | [GeoIPEnricher](11-geoip-enricher/) | Strategy | 8 | [README](11-geoip-enricher/README.md) |
| 12 | [AlertChannel + ConsoleChannel](12-alert-channel/) | Strategy | — | [README](12-alert-channel/README.md) |
| 13 | [MetricsCollector](13-observability/) | Collector | — | [README](13-observability/README.md) |
| 14 | [Enrichment Pipeline](14-enrichment-pipeline/) | Strategy + Pipeline | — | [README](14-enrichment-pipeline/README.md) |
| 15 | [Worker](15-worker/) | Composition | — | [README](15-worker/README.md) |

**Total:** 110+ tests across V1 and V2 services.

---

## Architecture Overview

```
src/core/            → Observer (EventBroker), Strategy (Firewall ABC, Enricher ABC),
                       Repository ABCs, Plugin ABC (LogParserPlugin), MetricsCollector
src/core/plugins/    → ParserRegistry (Factory), LogParserPlugin ABC, ParsedEntry (V2)
src/core/enrichment/ → EnrichedEvent, GeoLocation, ThreatInfo, Enricher ABC
src/core/alerting/   → AlertChannel ABC, SendResult
src/core/observability/ → MetricsCollector (Prometheus format)
src/adapters/        → UFW/NoOp strategies, SSHAuthPlugin, GeoIPEnricher, ConsoleChannel, Telegram bot
src/interfaces/      → Command handler, CLI adapter, Flask dashboard
src/infrastructure/  → Peewee models, DB init
src/utils/           → IP validation
tests/unit/          → 110+ tests across all services
```

---

## Wiring Everything Together

The production wiring uses `SSHAuthPlugin` via `ParserRegistry`, `NoOpStrategy` for development, and `ConsoleChannel` for alerts:

```python
# Configuration
import os
from dotenv import load_dotenv
from peewee import SqliteDatabase

from src.infrastructure.db import init_database
from src.core.repositories import PeeweeAlertRepository
from src.core.services.block_service import BlockService
from src.core.events import EventBroker
from src.core.detector import ThresholdDetector
from src.adapters.firewall.noop import NoOpStrategy
from src.adapters.geoip.geo_ip import GeoIPEnricher
from src.adapters.alerting.console import ConsoleChannel
from src.adapters.parsers.plugins.ssh_auth import SSHAuthPlugin
from src.core.plugins.registry import ParserRegistry
from src.core.observability.metrics import MetricsCollector
from src.interfaces.commands.factory import create_command_handler
from src.interfaces.web.app import create_app

load_dotenv()

# 1. Database
db = SqliteDatabase(os.getenv("DB_PATH", "data/sentinel.db"))
init_database(db)
alert_repo = PeeweeAlertRepository(db)

# 2. Metrics
metrics = MetricsCollector()

# 3. Event system
broker = EventBroker()

# 4. Plugin registry
registry = ParserRegistry()
registry.register("ssh_auth", SSHAuthPlugin)
parser = registry.create("ssh_auth", {"log_path": "/var/log/auth.log"})

# 5. Enrichment pipeline
geoip = GeoIPEnricher(provider="mock")

# 6. Firewall (swap UFWStrategy for NoOpStrategy in test mode)
strategy = NoOpStrategy()
block_repo = ...  # implement BlockRepository (see Service 3)
block_svc = BlockService(strategy=strategy, repo=block_repo)

# 7. Alert channel
alert_channel = ConsoleChannel()

# 8. Detector
detector = ThresholdDetector(threshold=5, window_seconds=300)
detector.register_broker(broker)

# 9. Wire event subscriber
def on_security_event(event):
    alert_repo.create(ip=event.ip, attempts=event.attempt_count, service=event.service)
    block_svc.handle_event(event)
    # ... enrich, alert, record metrics ...

broker.subscribe(on_security_event)

# 10. Command handler
cmd_handler = create_command_handler(block_svc, alert_repo)

# 11. Log parser
def on_entry(entry):
    detector.record_attempt(str(entry.ip), entry.timestamp)

parser.process_stream("/var/log/auth.log", callback=on_entry)

# 12. Web dashboard
app = create_app(alert_repo=alert_repo, api_token=os.getenv("API_TOKEN"))
app.run(host="0.0.0.0", port=5000)
```
