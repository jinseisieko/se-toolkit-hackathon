# LogSentinel V1 — Senior Developer Implementation Plan

> **Goal**: Deliver a production-ready, extendable security monitoring system with real-time log parsing, auto-blocking, Telegram alerts, and a web dashboard — built with maintainability and testability as first-class concerns.

---

## 🏗️ Architecture Overview (Design Patterns Applied)

```
┌─────────────────────────────────────────────────────┐
│                 Application Core                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Observer   │  │  Strategy   │  │  Factory    │  │
│  │  Pattern    │  │  Pattern    │  │  Pattern    │  │
│  │  (Events)   │  │  (Blocking) │  │  (Commands) │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                 │         │
│  ┌──────▼────────────────▼─────────────────▼──────┐ │
│  │              Command Handler Layer              │ │
│  │  (Abstract interface: CLI / Telegram / Webhook)│ │
│  └─────────────────┬──────────────────────────────┘ │
│                    │                                │
│  ┌─────────────────▼─────────────────┐             │
│  │        Repository Pattern          │             │
│  │  (Peewee models + Data Access Layer)│            │
│  └─────────────────┬─────────────────┘             │
│                    │                                │
│  ┌─────────────────▼─────────────────┐             │
│  │        External Adapters           │             │
│  │  • LogTailAdapter (tail -f)        │             │
│  │  • FirewallAdapter (ufw/iptables)  │             │
│  │  • TelegramAdapter (python-telegram-bot) │       │
│  │  • FlaskAdapter (web dashboard)    │             │
│  └────────────────────────────────────┘             │
└─────────────────────────────────────────────────────┘
```

### Key Patterns & Why

| Pattern | Application | Benefit |
|---------|------------|---------|
| **Observer** | LogWorker publishes `SecurityEvent` → AlertService, BlockService, TelegramService subscribe | Decouples detection from actions; easy to add new responders |
| **Strategy** | `FirewallStrategy` interface: `UFWStrategy`, `IPTablesStrategy`, `NoOpStrategy` (for test) | Swap blocking mechanisms without changing core logic |
| **Factory** | `CommandFactory` creates handler instances from command strings | Centralized command routing; easy to extend with new admin commands |
| **Repository** | `AlertRepository`, `BlockRepository` wrap Peewee models | Isolates ORM; simplifies testing and future DB migrations |
| **Adapter** | `TelegramInputAdapter`, `CLIInputAdapter` implement `CommandInputPort` | Enables test mode: same handlers, different input sources |
| **Template Method** | `BaseLogParser` defines parsing workflow; `SSHAuthLogParser` implements regex rules | Standardize log parsing while allowing format-specific extensions |

---

## 📦 Component Implementation Plan (V1 Scope)

### Phase 1: Foundation & Core Patterns (Week 1)

#### 1.1 Project Skeleton & Dependency Management
```bash
logsentinel/
├── pyproject.toml          # Poetry for dependency management
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── src/
    ├── __init__.py
    ├── core/               # Domain logic (pattern implementations)
    ├── adapters/           # External integrations
    ├── infrastructure/     # DB, config, logging setup
    ├── interfaces/         # CLI, Telegram, Web entrypoints
    └── utils/              # Helpers (regex, time, validation)
```

#### 1.2 Core Domain Models (Peewee + Repository Pattern)
```python
# src/core/models.py
class Alert(Model):
    ip = CharField()
    attempts = IntegerField()
    first_seen = DateTimeField()
    last_seen = DateTimeField()
    blocked = BooleanField(default=False)
    
class BlockedIP(Model):
    ip = CharField(unique=True)
    blocked_at = DateTimeField()
    reason = CharField()
    strategy_used = CharField()  # 'ufw', 'iptables', 'noop'
```

```python
# src/core/repositories.py
class AlertRepository:
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, ip: str, attempts: int) -> Alert:
        # ...
    
    def get_recent(self, limit: int = 50) -> List[Alert]:
        # ...
```

#### 1.3 Event System (Observer Pattern)
```python
# src/core/events.py
class SecurityEvent:
    def __init__(self, ip: str, attempt_count: int, log_line: str):
        self.ip = ip
        self.attempt_count = attempt_count
        self.timestamp = datetime.utcnow()
        self.log_line = log_line

class EventBroker:
    def __init__(self):
        self._subscribers: List[Callable[[SecurityEvent], None]] = []
    
    def subscribe(self, handler: Callable):
        self._subscribers.append(handler)
    
    def publish(self, event: SecurityEvent):
        for handler in self._subscribers:
            handler(event)  # Could add async/queue later
```

---

### Phase 2: Log Parsing & Detection Engine (Week 2)

#### 2.1 Log Adapter with Template Method
```python
# src/adapters/log_tail.py
class BaseLogParser(ABC):
    @abstractmethod
    def parse_line(self, line: str) -> Optional[Dict]:
        pass
    
    def process_stream(self, callback: Callable[[Dict], None]):
        """Tail file and call callback for each parsed entry"""
        # Implementation using subprocess.Popen(['tail', '-F', ...])
```

```python
# src/adapters/parsers/ssh_auth.py
class SSHAuthLogParser(BaseLogParser):
    FAILED_PATTERN = re.compile(
        r'Failed\s+(password|publickey)\s+for\s+(?:invalid\s+user\s+)?(\S+)\s+from\s+(\d+\.\d+\.\d+\.\d+)'
    )
    
    def parse_line(self, line: str) -> Optional[Dict]:
        match = self.FAILED_PATTERN.search(line)
        if match:
            return {
                'user': match.group(2),
                'ip': match.group(3),
                'timestamp': self._extract_timestamp(line),
                'raw': line
            }
        return None
```

#### 2.2 Threshold Aggregator & Event Publisher
```python
# src/core/detector.py
class ThresholdDetector:
    def __init__(self, threshold: int, window_seconds: int = 300):
        self.threshold = threshold
        self.window = window_seconds
        self._attempts: Dict[str, Deque] = defaultdict(deque)
        self._broker: EventBroker = None
    
    def register_broker(self, broker: EventBroker):
        self._broker = broker
    
    def record_attempt(self, ip: str, timestamp: datetime):
        # Clean old entries outside window
        # Add new attempt
        # If count >= threshold: publish SecurityEvent & reset counter
```

---

### Phase 3: Action Services (Observer Subscribers) (Week 2-3)

#### 3.1 Blocking Strategy Pattern
```python
# src/core/blocking.py
class FirewallStrategy(ABC):
    @abstractmethod
    def block(self, ip: str, reason: str) -> bool:
        pass
    
    @abstractmethod
    def unblock(self, ip: str) -> bool:
        pass

class UFWStrategy(FirewallStrategy):
    def block(self, ip: str, reason: str) -> bool:
        # subprocess.run(['ufw', 'deny', 'from', ip], ...)
        return True

class NoOpStrategy(FirewallStrategy):
    """For test mode - logs instead of blocking"""
    def block(self, ip: str, reason: str) -> bool:
        logger.info(f"[TEST MODE] Would block {ip}: {reason}")
        return True
```

```python
# src/core/services/block_service.py
class BlockService:
    def __init__(self, strategy: FirewallStrategy, repo: BlockRepository):
        self.strategy = strategy
        self.repo = repo
    
    def handle_event(self, event: SecurityEvent):
        if self.strategy.block(event.ip, f"SSH brute-force: {event.attempt_count} attempts"):
            self.repo.create(ip=event.ip, reason="auto-block", strategy=strategy.__class__.__name__)
```

#### 3.2 Alert Service (Telegram + Dashboard)
```python
# src/core/services/alert_service.py
class AlertService:
    def __init__(self, telegram_adapter, alert_repo):
        self.telegram = telegram_adapter
        self.repo = alert_repo
    
    def handle_event(self, event: SecurityEvent):
        alert = self.repo.create(ip=event.ip, attempts=event.attempt_count)
        self.telegram.send_alert(alert)  # Abstracted call
```

---

### Phase 4: Unified Command Handler (Test Mode Ready) (Week 3)

#### 4.1 Command Input Abstraction (Key for Test Mode)
```python
# src/interfaces/command_port.py
class CommandInputPort(ABC):
    """Abstract input source for admin commands"""
    @abstractmethod
    def start_listening(self, handler: 'CommandHandler'):
        pass

class CommandHandler:
    """Central command router - works with any input source"""
    def __init__(self, block_service, alert_service, config):
        self.block_service = block_service
        self.alert_service = alert_service
        self.config = config
    
    def handle(self, command: str, args: List[str], user_id: Optional[str] = None):
        # Factory pattern: route to specific handler
        if command == 'unblock':
            return self._handle_unblock(args, user_id)
        elif command == 'status':
            return self._handle_status()
        # ...
```

#### 4.2 Telegram Adapter (Production)
```python
# src/adapters/telegram_adapter.py
class TelegramInputAdapter(CommandInputPort):
    def __init__(self, token: str, test_mode: bool, test_chat_id: Optional[str]):
        self.app = Application.builder().token(token).build()
        self.test_mode = test_mode
        self.test_chat_id = test_chat_id
    
    def start_listening(self, handler: CommandHandler):
        # Register handlers: /start, /status, /unblock
        # In test_mode: validate chat_id before processing
        self.app.run_polling()
```

#### 4.3 CLI Adapter (Test Mode)
```python
# src/adapters/cli_adapter.py
class CLIInputAdapter(CommandInputPort):
    def start_listening(self, handler: CommandHandler):
        print("🧪 TEST MODE: Type commands like '/status' or '/unblock 1.2.3.4'")
        while True:
            line = input("❯ ").strip()
            if line.startswith('/'):
                parts = line[1:].split(maxsplit=1)
                cmd = parts[0]
                args = parts[1].split() if len(parts) > 1 else []
                result = handler.handle(cmd, args, user_id="cli_test_user")
                print(f"✅ {result}")
```

#### 4.4 Bootstrapper: Choose Adapter at Runtime
```python
# src/interfaces/bootstrap.py
def create_input_adapter(config: Config) -> CommandInputPort:
    if config.test_mode and config.cli_test:
        return CLIInputAdapter()
    return TelegramInputAdapter(
        token=config.bot_token,
        test_mode=config.test_mode,
        test_chat_id=config.test_chat_id
    )
```

---

### Phase 5: Web Dashboard (Flask) (Week 4)

#### 5.1 Flask App Structure
```python
# src/interfaces/web/app.py
def create_app(config: Config):
    app = Flask(__name__)
    
    # Register repositories as app context
    db = Database(config.db_path)
    app.config['db'] = db
    
    @app.route('/api/alerts')
    def get_alerts():
        repo = AlertRepository(app.config['db'])
        return jsonify([a.to_dict() for a in repo.get_recent()])
    
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')
    
    return app
```

#### 5.2 Real-time Updates (Simple Polling for V1)
```javascript
// static/js/dashboard.js
setInterval(() => {
  fetch('/api/alerts')
    .then(r => r.json())
    .then(data => renderAlerts(data));
}, 5000);
```

> ✅ V1 uses polling. V2 can upgrade to Server-Sent Events or WebSockets.

---

### Phase 6: Dockerization & Deployment (Week 4)

#### 6.1 Multi-Service Docker Compose
```yaml
# docker-compose.yml
services:
  web:
    build: .
    command: python -m src.interfaces.web
    ports: ["5000:5000"]
    volumes: ["./data:/app/data"]
    env_file: .env
    depends_on: [worker]
  
  worker:
    build: .
    command: python -m src.interfaces.worker
    volumes: 
      - "/var/log/auth.log:/var/log/auth.log:ro"  # Host log access
      - "./data:/app/data"
    env_file: .env
    cap_add: ["NET_ADMIN"]  # Only needed in prod for firewall commands
  
  # Telegram bot runs inside worker or as separate service
```

#### 6.2 Dockerfile (Multi-stage for size optimization)
```dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry export -f requirements.txt --output requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install -r requirements.txt && \
    apt-get update && apt-get install -y iptables ufw && \
    rm -rf /var/lib/apt/lists/*
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/
```

---

## 🧪 Testing Strategy

### Unit Tests (pytest)
```bash
tests/
├── unit/
│   ├── test_detector.py          # Threshold logic
│   ├── test_blocking_strategies.py # UFW vs NoOp
│   ├── test_command_handler.py   # CLI/Telegram agnostic
│   └── test_parsers.py           # Log regex validation
├── integration/
│   ├── test_telegram_adapter.py  # Mock bot API
│   └── test_web_api.py           # Flask test client
└── conftest.py                   # Shared fixtures (DB, config)
```

### Test Mode Workflow
```bash
# .env for development
TEST_MODE=true
CLI_TEST=true          # ← Enables CLI input adapter
BLOCK_THRESHOLD=3
FIREWALL_STRATEGY=noop # ← Uses NoOpStrategy

# Run locally without Docker
poetry run python -m src.interfaces.worker
# Then in another terminal:
poetry run python -m src.interfaces.cli_test
# Type: /status → see response without Telegram or firewall side effects
```

---

## 🗓️ V1 Implementation Timeline (4 Weeks)

| Week | Focus | Deliverables |
|------|-------|-------------|
| **1** | Foundation | Project skeleton, Peewee models, Repository pattern, EventBroker |
| **2** | Detection | Log parser, ThresholdDetector, Blocking Strategy pattern |
| **3** | Actions & Commands | AlertService, BlockService, CommandHandler + CLI/Telegram adapters |
| **4** | Dashboard & Deploy | Flask dashboard, Docker Compose, test mode validation, docs |

---

## 🔐 Security & Operational Considerations

1. **Log Access**: Container needs read access to `/var/log/auth.log` → use volume mount + host user permissions
2. **Firewall Commands**: `NET_ADMIN` capability only in production; test mode uses `NoOpStrategy`
3. **Telegram Security**: 
   - Validate `chat_id` in test mode
   - Rate-limit commands
   - Log all bot interactions to DB
4. **Database**: SQLite is fine for V1 (single-server); design Repository layer to allow PostgreSQL migration later
5. **Secrets**: Use `.env` + Docker secrets; never commit tokens

---

## 🚀 Getting Started for Developers

```bash
# 1. Clone & setup
git clone <repo> && cd logsentinel
poetry install

# 2. Configure for test mode
cp .env.example .env
# Edit: BOT_TOKEN=mock, TEST_MODE=true, CLI_TEST=true, FIREWALL_STRATEGY=noop

# 3. Run components separately (for development)
# Terminal 1: Worker (log parsing)
poetry run python -m src.interfaces.worker

# Terminal 2: CLI test interface
poetry run python -m src.interfaces.cli_test
# Type: /status → see mocked response

# Terminal 3: Web dashboard
poetry run python -m src.interfaces.web
# Visit: http://localhost:5000

# 4. Run full stack with Docker (prod-like)
docker compose up -d
```

---

## 🔄 Extension Points for V2 (Designed In)

1. **New Log Formats**: Add `ApacheLogParser`, `NginxLogParser` extending `BaseLogParser`
2. **New Blocking Methods**: Implement `CloudflareStrategy`, `AWS-WAFStrategy`
3. **New Alert Channels**: Add `SlackAlertService`, `EmailAlertService` subscribing to `EventBroker`
4. **Geo-IP**: Decorator pattern around `Alert` enrichment
5. **Advanced Testing**: Replace CLI adapter with `pytest`-driven `MockInputAdapter`

---

## ✅ V1 Success Criteria

- [ ] Real-time detection of 5+ failed SSH attempts from same IP
- [ ] Auto-block via `ufw` (prod) or log-only (test mode)
- [ ] Telegram alert received within 10 seconds of threshold breach
- [ ] Web dashboard shows last 50 alerts + blocked IPs table
- [ ] CLI test mode allows full command testing without Telegram/firewall side effects
- [ ] All services run via `docker compose up` on Ubuntu 24.04
- [ ] Unit test coverage >70% for core logic (detector, strategies, handlers)

---

> 💡 **Senior Dev Note**: The key architectural win here is the **input abstraction layer** (`CommandInputPort`). By decoupling *what* commands do from *where* they come from, we enable safe testing, future webhook integrations, and even a future admin web UI — all reusing the same `CommandHandler` logic. This is the pattern that will save hundreds of hours in V2+.

Let me know if you'd like me to draft the initial `pyproject.toml`, Dockerfile, or any of the core pattern implementations in code. 🛠️