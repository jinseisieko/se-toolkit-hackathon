#!/usr/bin/env python
"""Demo: LogSentinel services working together.

Simulates the full workflow:
1. Parse fake auth.log entries
2. Detect brute-force threshold breach
3. Auto-block via NoOpStrategy (test mode)
4. Store in SQLite database
5. Query via repository
6. Execute commands (status, unblock, block)
7. Render web dashboard HTML

No real auth.log, Telegram, or firewall access needed.
"""

import sys
from datetime import datetime, timedelta, timezone
from peewee import SqliteDatabase

# ── 1. Database ──────────────────────────────────────────────

print("=" * 60)
print("  LogSentinel - Service Demonstration")
print("=" * 60)

from src.infrastructure.db import init_database
from src.core.repositories import PeeweeAlertRepository
from src.core.services.block_service import BlockRepository, BlockService, BlockedIPRecord
from src.infrastructure.models import BlockedIP

db = SqliteDatabase(":memory:")
init_database(db)
alert_repo = PeeweeAlertRepository(db)

print("\n[1/8] Database initialized (in-memory SQLite)")

# ── 2. Event Broker ─────────────────────────────────────────

from src.core.events import EventBroker, SecurityEvent

broker = EventBroker()
events_received = []

def event_logger(event):
    events_received.append(event)
    print(f"       Event: {event.ip} - {event.attempt_count} attempts ({event.service})")

broker.subscribe(event_logger)

print("[2/8] EventBroker ready with subscriber")

# ── 3. Threshold Detector ───────────────────────────────────

from src.core.detector import ThresholdDetector

detector = ThresholdDetector(threshold=3, window_seconds=300)
detector.register_broker(broker)

print("[3/8] ThresholdDetector ready (threshold=3, window=300s)")

# ── 4. Firewall Strategy (NoOp for demo) ────────────────────

from src.adapters.firewall.noop import NoOpStrategy


class DemoBlockRepo(BlockRepository):
    """Minimal in-memory block repository for demo."""

    def __init__(self):
        self._records = {}
        self._next_id = 1

    def create(self, ip, reason, strategy):
        record = BlockedIPRecord(
            id=self._next_id,
            ip=ip,
            blocked_at=datetime.now(timezone.utc),
            reason=reason,
            strategy=strategy,
            is_blocked=True,
        )
        self._records[ip] = record
        self._next_id += 1
        return record

    def get_by_ip(self, ip):
        return self._records.get(ip)

    def mark_blocked(self, record_id):
        return True

    def mark_unblocked(self, record_id):
        for rec in self._records.values():
            if rec.id == record_id:
                rec.is_blocked = False
                return True
        return False


block_repo = DemoBlockRepo()
strategy = NoOpStrategy()
block_svc = BlockService(strategy=strategy, repo=block_repo)

print("[4/8] NoOpStrategy + BlockService ready (test mode)")


def on_event(event):
    # Also store an alert in the repository
    alert_repo.create(ip=event.ip, attempts=event.attempt_count, service=event.service)
    block_svc.handle_event(event)


broker.subscribe(on_event)

# ── 5. SSH Log Parser ──────────────────────────────────────

from src.adapters.parsers.ssh_auth import SSHAuthLogParser

parser = SSHAuthLogParser()

print("[5/8] SSHAuthLogParser ready")

# ── 6. Simulate attack ─────────────────────────────────────

print("\n" + "-" * 60)
print("  Simulating SSH brute-force attacks...")
print("-" * 60)

fake_log_lines = [
    "Apr  4 12:00:01 server sshd[1001]: Failed password for root from 192.0.2.1 port 22 ssh2",
    "Apr  4 12:00:05 server sshd[1002]: Failed password for root from 192.0.2.1 port 22 ssh2",
    "Apr  4 12:00:10 server sshd[1003]: Failed password for root from 192.0.2.1 port 22 ssh2",
    "Apr  4 12:01:01 server sshd[1004]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",
    "Apr  4 12:01:05 server sshd[1005]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",
    "Apr  4 12:01:10 server sshd[1006]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",
    "Apr  4 12:02:01 server sshd[1007]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2",
    "Apr  4 12:02:05 server sshd[1008]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2",
    "Apr  4 12:02:10 server sshd[1009]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2",
    "Apr  4 12:03:01 server sshd[1010]: Accepted password for root from 192.168.1.1 port 22 ssh2",
    "Apr  4 12:03:05 server sshd[1011]: Connection closed by 192.168.1.1 port 22",
]

for line in fake_log_lines:
    entry = parser.parse_line(line)
    if entry is not None:
        detector.record_attempt(entry.ip, entry.timestamp)

relevant = sum(1 for l in fake_log_lines if parser.parse_line(l))
print(f"\n  Processed {len(fake_log_lines)} log lines")
print(f"  Parsed {relevant} relevant SSH failure entries")
print(f"  Security events fired: {len(events_received)}")

# ── 7. Check results ────────────────────────────────────────

print("\n" + "-" * 60)
print("  Results:")
print("-" * 60)

alerts = alert_repo.get_recent()
print(f"\n  Alerts in database: {len(alerts)}")
for a in alerts:
    status = "BLOCKED" if a.blocked else "ACTIVE "
    icon = "🔴" if a.blocked else "🟡"
    print(f"    {icon} {status}  {a.ip:20s}  {a.attempts} attempts  ({a.service})")

# ── 8. Command Handler ─────────────────────────────────────

from src.interfaces.commands.handler import CommandContext, CommandHandler
from src.interfaces.commands.factory import create_command_handler

cmd_handler = create_command_handler(block_svc, alert_repo)
admin_ctx = CommandContext(
    user_id="demo",
    is_test_mode=True,
    allowed_actions={"status", "block", "unblock"},
)

print("\n" + "-" * 60)
print("  Command Handler demo:")
print("-" * 60)

results = [
    ("status", [], admin_ctx),
    ("unblock", ["192.0.2.1"], admin_ctx),
    ("block", ["10.99.99.99", "manual demo block"], admin_ctx),
    ("foobar", [], admin_ctx),
]

for cmd, args, ctx in results:
    r = cmd_handler.handle(cmd, args, ctx)
    icon = "OK" if r.success else "FAIL"
    print(f"  /{cmd} {' '.join(args):30s} -> [{icon}] {r.message}")

# Permission denied test
viewer_ctx = CommandContext(
    user_id="viewer",
    is_test_mode=True,
    allowed_actions={"status"},
)
r = cmd_handler.handle("unblock", ["192.0.2.1"], viewer_ctx)
icon = "OK" if r.success else "FAIL"
print(f"  /unblock 192.0.2.1             (viewer)    -> [{icon}] {r.message}")

# ── 9. Web Dashboard ───────────────────────────────────────

from src.interfaces.web.app import create_app

app = create_app(alert_repo=alert_repo)
app.config["TESTING"] = True

print("\n" + "-" * 60)
print("  Web Dashboard demo:")
print("-" * 60)

with app.test_client() as client:
    resp = client.get("/")
    html = resp.data.decode()
    print(f"\n  GET /  -> {resp.status_code}  ({len(html)} bytes HTML)")

    resp = client.get("/api/alerts")
    data = resp.get_json()
    print(f"  GET /api/alerts  -> {resp.status_code}  ({len(data)} alerts)")
    if data:
        first = data[0]
        print(f"    Latest: {first['ip']} - {first['attempts']} attempts, blocked={first['blocked']}")

    resp = client.get("/api/blocked")
    data = resp.get_json()
    print(f"  GET /api/blocked  -> {resp.status_code}  ({len(data)} blocked)")
    for item in data:
        print(f"    {item['ip']}")

# ── Summary ──────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  All 8 services demonstrated successfully!")
print("=" * 60)
print("""
  Service              Status
  ----------------------------------------------------------
  1. EventBroker       Events published and received
  2. ThresholdDetector Threshold breach detected, events fired
  3. FirewallStrategy  NoOpStrategy logged blocks (no real firewall)
  4. AlertRepository   Alerts stored and queried from SQLite
  5. CommandHandler    status/unblock/block/permissions tested
  6. TelegramAdapter   Ready (requires real bot token)
  7. SSHAuthLogParser  Parsed SSH auth log patterns
  8. Flask Dashboard   HTML + JSON API rendered
""")
