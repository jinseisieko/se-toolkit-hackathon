# LogSentinel — Service Documentation

Complete documentation for all 8 core services.

---

## Services

| # | Service | Pattern | Tests | Docs |
|---|---------|---------|-------|------|
| 1 | [EventBroker + SecurityEvent](01-event-broker/) | Observer | 6 | [README](01-event-broker/README.md) |
| 2 | [ThresholdDetector](02-threshold-detector/) | Aggregator + Observer | 6 | [README](02-threshold-detector/README.md) |
| 3 | [FirewallStrategy + BlockService](03-firewall-strategy/) | Strategy + Composition | 18 | [README](03-firewall-strategy/README.md) |
| 4 | [AlertRepository + Peewee Models](04-alert-repository/) | Repository | 8 | [README](04-alert-repository/README.md) |
| 5 | [CommandHandler + CLIInputAdapter](05-command-handler/) | Factory + Adapter | 11 | [README](05-command-handler/README.md) |
| 6 | [TelegramInputAdapter](06-telegram-adapter/) | Adapter | 7 | [README](06-telegram-adapter/README.md) |
| 7 | [SSHAuthLogParser](07-ssh-log-parser/) | Template Method | 11 | [README](07-ssh-log-parser/README.md) |
| 8 | [Flask Dashboard](08-flask-dashboard/) | Application Factory | 7 | [README](08-flask-dashboard/README.md) |

**Total:** 74 tests across all services.

---

## Architecture Overview

```
src/core/          → Observer (EventBroker), Strategy (Firewall ABC), Repository ABCs
src/adapters/      → UFW/NoOp strategies, Telegram bot, SSH log parser
src/interfaces/    → Command handler, CLI adapter, Flask dashboard
src/infrastructure/ → Peewee models, DB init
src/utils/         → IP validation
tests/unit/        → 74 tests across all 8 services
```

---

## Wiring Everything Together

The recommended production wiring uses `NoOpStrategy` for development and `UFWStrategy` for production:

```python
# Configuration
from src.core.events import EventBroker
from src.core.detector import ThresholdDetector
from src.adapters.firewall.ufw import UFWStrategy
from src.adapters.firewall.noop import NoOpStrategy
from src.core.services.block_service import BlockService
from src.core.repositories import PeeweeAlertRepository
from src.infrastructure.db import init_database
from src.adapters.parsers.ssh_auth import SSHAuthLogParser
from src.interfaces.commands.handler import CommandHandler
from src.interfaces.commands.factory import create_command_handler
from src.adapters.telegram import TelegramInputAdapter
from src.interfaces.web.app import create_app
from peewee import SqliteDatabase

# 1. Database
db = SqliteDatabase("/app/data/sentinel.db")
init_database(db)
alert_repo = PeeweeAlertRepository(db)

# 2. Event system
broker = EventBroker()

# 3. Detector
detector = ThresholdDetector(threshold=5, window_seconds=300)
detector.register_broker(broker)

# 4. Firewall (swap UFWStrategy for NoOpStrategy in test mode)
strategy = UFWStrategy()
block_repo = ...  # implement BlockRepository
block_svc = BlockService(strategy=strategy, repo=block_repo)

# 5. Command handler
cmd_handler = create_command_handler(block_svc, alert_repo)

# 6. Telegram bot
tg = TelegramInputAdapter(token="...", test_mode=False)
tg.set_handler(cmd_handler)

# 7. Log parser
parser = SSHAuthLogParser()
def on_entry(entry):
    detector.record_attempt(entry.ip, entry.timestamp)

# 8. Start services
parser.process_stream("/var/log/auth.log", callback=on_entry)
tg.build_app().run_polling()

# 9. Web dashboard
app = create_app(alert_repo=alert_repo)
app.run(host="0.0.0.0", port=5000)
```
