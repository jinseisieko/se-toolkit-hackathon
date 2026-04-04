#!/usr/bin/env python
"""Demo: LogSentinel V2 services working together.

Simulates the core monitoring pipeline:
1. Database initialization
2. Plugin registry + SSHAuthPlugin
3. GeoIP enrichment
4. Threshold detection
5. Auto-block via NoOpStrategy (test mode)
6. Console alert channel
7. Metrics collection

The web dashboard and Telegram bot run as separate services
in production (docker-compose).  They are tested independently
via their own unit tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from ipaddress import IPv4Address

from peewee import SqliteDatabase

from src.adapters.alerting.console import ConsoleChannel
from src.adapters.firewall.noop import NoOpStrategy
from src.adapters.geoip.geo_ip import GeoIPEnricher
from src.adapters.parsers.plugins.ssh_auth import SSHAuthPlugin
from src.core.detector import ThresholdDetector
from src.core.enrichment.base import EnrichedEvent
from src.core.events import EventBroker, SecurityEvent
from src.core.observability.metrics import MetricsCollector
from src.core.plugins.parser_plugin import ParsedEntry
from src.core.plugins.registry import ParserRegistry
from src.core.repositories import PeeweeAlertRepository
from src.core.services.block_service import (
    BlockRepository,
    BlockService,
    BlockedIPRecord,
)
from src.infrastructure.db import init_database


# ── Helpers ───────────────────────────────────────────────────


class DemoBlockRepo(BlockRepository):
    """Minimal in-memory block repository for demo."""

    def __init__(self) -> None:
        self._records: dict[str, BlockedIPRecord] = {}
        self._next_id = 1

    def create(self, ip: str, reason: str, strategy: str) -> BlockedIPRecord:
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

    def get_by_ip(self, ip: str) -> BlockedIPRecord | None:
        return self._records.get(ip)

    def mark_blocked(self, record_id: int) -> bool:
        return True

    def mark_unblocked(self, record_id: int) -> bool:
        for rec in self._records.values():
            if rec.id == record_id:
                rec.is_blocked = False
                return True
        return False


# ── Demo ──────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("  LogSentinel V2 — Monitoring Pipeline Demonstration")
    print("=" * 60)

    # ── 1. Database ───────────────────────────────────────────

    db = SqliteDatabase(":memory:")
    init_database(db)
    alert_repo = PeeweeAlertRepository(db)
    print("\n[1/7] Database initialized (in-memory SQLite)")

    # ── 2. Plugin Registry + SSHAuthPlugin ────────────────────

    registry = ParserRegistry()
    registry.register("ssh_auth", SSHAuthPlugin)
    parser = registry.create("ssh_auth", {})
    print(f"[2/7] ParserRegistry ready — plugins: {registry.list_available()}")

    # ── 3. GeoIP Enrichment ───────────────────────────────────

    geoip = GeoIPEnricher(provider="mock")
    print("[3/7] GeoIPEnricher ready (mock provider)")

    # ── 4. Event Broker ───────────────────────────────────────

    broker = EventBroker()
    events_received: list[SecurityEvent] = []

    def event_logger(event: SecurityEvent) -> None:
        events_received.append(event)
        print(
            f"       Event: {event.ip} — "
            f"{event.attempt_count} attempts ({event.service})"
        )

    broker.subscribe(event_logger)
    print("[4/7] EventBroker ready with subscriber")

    # ── 5. Threshold Detector ─────────────────────────────────

    detector = ThresholdDetector(threshold=3, window_seconds=300)
    detector.register_broker(broker)
    print("[5/7] ThresholdDetector ready (threshold=3, window=300s)")

    # ── 6. Firewall Strategy + Block Service ──────────────────

    block_repo = DemoBlockRepo()
    strategy = NoOpStrategy()
    block_svc = BlockService(strategy=strategy, repo=block_repo)
    print("[6/7] NoOpStrategy + BlockService ready (test mode)")

    # ── 7. Console Alert Channel + Metrics ────────────────────

    alert_channel = ConsoleChannel()
    metrics = MetricsCollector()
    print("[7/7] ConsoleChannel + MetricsCollector ready")

    # ── Wire: event → persist → block → enrich → alert ───────

    def on_event(event: SecurityEvent) -> None:
        alert_repo.create(
            ip=event.ip,
            attempts=event.attempt_count,
            service=event.service,
        )
        block_svc.handle_event(event)

        # Enrich and alert
        ip_obj = IPv4Address(event.ip)
        entry = ParsedEntry(
            ip=ip_obj,
            timestamp=event.timestamp,
            service=event.service,
            event_type="failed_auth",
            raw_line=event.log_line,
        )
        enriched = EnrichedEvent.from_parsed_entry(entry)
        enriched = geoip.enrich(enriched)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                alert_channel.send(enriched, {})
            )
            if result.success:
                metrics.record_alert(enriched, alert_channel.name)
        finally:
            loop.close()

    broker.subscribe(on_event)

    # ── Simulate SSH brute-force attacks ──────────────────────

    print("\n" + "-" * 60)
    print("  Simulating SSH brute-force attacks...")
    print("-" * 60)

    fake_log_lines = [  # fmt: off
        "Apr  4 12:00:01 server sshd[1001]: Failed password for root from 192.0.2.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:00:05 server sshd[1002]: Failed password for root from 192.0.2.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:00:10 server sshd[1003]: Failed password for root from 192.0.2.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:01:01 server sshd[1004]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:01:05 server sshd[1005]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:01:10 server sshd[1006]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:02:01 server sshd[1007]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2",  # noqa: E501
        "Apr  4 12:02:05 server sshd[1008]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2",  # noqa: E501
        "Apr  4 12:02:10 server sshd[1009]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2",  # noqa: E501
        "Apr  4 12:03:01 server sshd[1010]: Accepted password for root from 192.168.1.1 port 22 ssh2",  # noqa: E501
        "Apr  4 12:03:05 server sshd[1011]: Connection closed by 192.168.1.1 port 22",  # noqa: E501
    ]  # fmt: on

    for line in fake_log_lines:
        entry = parser.parse_line(line)
        if entry is not None:
            detector.record_attempt(str(entry.ip), entry.timestamp)
            metrics.observe_processing_time(parser.name, 0.001)

    relevant = sum(1 for line in fake_log_lines if parser.parse_line(line))
    print(f"\n  Processed {len(fake_log_lines)} log lines")
    print(f"  Parsed {relevant} relevant SSH failure entries")
    print(f"  Security events fired: {len(events_received)}")

    # ── Check results ─────────────────────────────────────────

    print("\n" + "-" * 60)
    print("  Results:")
    print("-" * 60)

    alerts = alert_repo.get_recent()
    print(f"\n  Alerts in database: {len(alerts)}")
    for a in alerts:
        status = "BLOCKED" if a.blocked else "ACTIVE "
        icon = "\U0001f534" if a.blocked else "\U0001f7e1"
        print(
            f"    {icon} {status}  {a.ip:20s}  "
            f"{a.attempts} attempts  ({a.service})"
        )

    # ── Metrics Export ────────────────────────────────────────

    print("\n" + "-" * 60)
    print("  Metrics export (Prometheus format):")
    print("-" * 60)
    print()
    print(metrics.render())

    # ── Summary ───────────────────────────────────────────────

    print("=" * 60)
    print("  Pipeline demonstrated successfully!")
    print("=" * 60)
    print("""
  Service              Status
  ----------------------------------------------------------
  1. Database          In-memory SQLite initialized
  2. ParserRegistry    SSHAuthPlugin loaded and parsing
  3. GeoIPEnricher     Mock enrichment applied
  4. EventBroker       Events published and received
  5. ThresholdDetector Breaches detected, events fired
  6. BlockService      NoOpStrategy logged blocks (no real firewall)
  7. ConsoleChannel    Alerts written to stdout
  8. MetricsCollector  Prometheus metrics rendered

  Separate services (tested independently):
  - Web dashboard      Flask + REST API (see src/web.py)
  - Telegram bot       Chat bot (see src/adapters/telegram_worker.py)
""")


if __name__ == "__main__":
    main()
