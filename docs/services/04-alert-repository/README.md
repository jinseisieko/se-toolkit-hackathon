# 4. AlertRepository + Peewee Models

**Pattern:** Repository  
**Files:** `src/infrastructure/models.py`, `src/infrastructure/db.py`, `src/core/repositories.py`  
**Tests:** `tests/unit/test_repositories.py` (8 tests)

---

## Purpose

Provides data access for alerts through a clean abstraction. The `AlertRepository` ABC lives in `core/` (business logic), while the Peewee implementation lives in `infrastructure/`. This keeps ORM imports out of business logic.

---

## Database Models

| Model | Table | Fields |
|-------|-------|--------|
| `Alert` | `alerts` | `id`, `ip`, `attempts`, `service`, `first_seen`, `last_seen`, `blocked` |
| `BlockedIP` | `blocked_ips` | `id`, `ip` (unique), `blocked_at`, `reason`, `strategy`, `is_blocked` |

---

## Alert Dataclass (core)

```python
@dataclass
class Alert:
    id: Optional[int]
    ip: str
    attempts: int
    service: str
    first_seen: datetime
    last_seen: datetime
    blocked: bool
```

---

## PeeweeAlertRepository API

```python
from src.core.repositories import PeeweeAlertRepository
from src.infrastructure.db import init_database
from peewee import SqliteDatabase

db = SqliteDatabase("sentinel.db")
init_database(db)

repo = PeeweeAlertRepository(db)

# Create
alert = repo.create(ip="192.0.2.1", attempts=5, service="ssh")

# Query (newest first, default limit 50)
alerts: Sequence[Alert] = repo.get_recent(limit=50)

# Update
repo.mark_blocked(alert.id)

# Lookup
alert = repo.get_by_id(42)  # returns None if not found
```

---

## Database Initialization

```python
# Production — file-based SQLite
db = SqliteDatabase("/app/data/sentinel.db")

# Testing — in-memory
db = SqliteDatabase(":memory:")

init_database(db)  # binds DB to all models and creates tables
```

---

## Design Decisions

- **Peewee over SQLAlchemy:** Peewee is lightweight, has zero configuration, and works well for single-file SQLite databases. The Repository pattern allows migrating to PostgreSQL later without changing core logic.
- **In-memory SQLite for tests:** Tests use `:memory:` databases — real SQL operations, no mocking, fast execution.
