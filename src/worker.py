"""LogSentinel V2 worker — main entrypoint.

Wires all services together and runs the monitoring pipeline:
1. Parse auth.log via SSHAuthPlugin
2. Enrich events with GeoIP
3. Detect threshold breaches
4. Block IPs via firewall strategy
5. Send alerts via notification channels
6. Serve web dashboard + metrics endpoint
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Optional

from dotenv import load_dotenv
from peewee import SqliteDatabase

from src.adapters.alerting.console import ConsoleChannel
from src.adapters.firewall.noop import NoOpStrategy
from src.adapters.firewall.ufw import UFWStrategy
from src.adapters.geoip.geo_ip import GeoIPEnricher
from src.adapters.parsers.plugins.ssh_auth import SSHAuthPlugin
from src.core.alerting.channel import AlertChannel
from src.core.blocking import FirewallStrategy
from src.core.detector import ThresholdDetector
from src.core.enrichment.base import EnrichedEvent
from src.core.events import EventBroker, SecurityEvent
from src.core.observability.metrics import MetricsCollector
from src.core.plugins.parser_plugin import LogParserPlugin, ParsedEntry
from src.core.plugins.registry import ParserRegistry
from src.core.repositories import PeeweeAlertRepository
from src.core.services.block_service import BlockRepository, BlockService, BlockedIPRecord
from src.infrastructure.db import init_database
from src.infrastructure.models import BlockedIP
from src.interfaces.commands.cli import CLIInputAdapter
from src.interfaces.commands.factory import create_command_handler
from src.interfaces.commands.handler import CommandContext
from src.interfaces.web.app import create_app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("logsentinel")


# ── BlockRepository (Peewee-backed) ──────────────────────────


class PeeweeBlockRepo(BlockRepository):
    """Production BlockRepository backed by Peewee BlockedIP model."""

    def create(
        self, ip: str, reason: str, strategy: str
    ) -> BlockedIPRecord:
        record = BlockedIP.create(
            ip=ip, reason=reason, strategy=strategy,
            blocked_at=datetime.now(timezone.utc),
        )
        return BlockedIPRecord(
            id=record.id, ip=record.ip,
            blocked_at=record.blocked_at,
            reason=record.reason, strategy=record.strategy,
            is_blocked=record.is_blocked,
        )

    def get_by_ip(self, ip: str) -> Optional[BlockedIPRecord]:
        try:
            rec = BlockedIP.get(BlockedIP.ip == ip)
        except BlockedIP.DoesNotExist:
            return None
        return BlockedIPRecord(
            id=rec.id, ip=rec.ip,
            blocked_at=rec.blocked_at,
            reason=rec.reason, strategy=rec.strategy,
            is_blocked=rec.is_blocked,
        )

    def mark_blocked(self, record_id: int) -> bool:
        return BlockedIP.update(is_blocked=True).where(
            BlockedIP.id == record_id
        ).execute() > 0

    def mark_unblocked(self, record_id: int) -> bool:
        return BlockedIP.update(is_blocked=False).where(
            BlockedIP.id == record_id
        ).execute() > 0


# ── Configuration ────────────────────────────────────────────


class Config:
    """Application configuration from environment variables."""

    def __init__(self) -> None:
        self.db_path = os.getenv("DB_PATH", "data/sentinel.db")
        self.log_path = os.getenv("LOG_PATH", "/var/log/auth.log")
        self.block_threshold = int(os.getenv("BLOCK_THRESHOLD", "5"))
        self.firewall_strategy = os.getenv("FIREWALL_STRATEGY", "noop")
        self.test_mode = os.getenv("TEST_MODE", "true").lower() == "true"
        self.geoip_provider = os.getenv("GEOIP_PROVIDER", "mock")
        self.web_host = os.getenv("WEB_HOST", "0.0.0.0")
        self.web_port = int(os.getenv("WEB_PORT", "5000"))
        self.cli_mode = os.getenv("CLI_MODE", "true").lower() == "true"
        self.api_token = os.getenv("API_TOKEN") or None


# ── Worker ────────────────────────────────────────────────────


class Worker:
    """Main LogSentinel worker — wires all services together."""

    def __init__(self) -> None:
        self.config = Config()
        self._shutdown = threading.Event()

    def run(self) -> None:
        """Start all services and block until shutdown."""
        logger.info("Starting LogSentinel V2 worker")
        logger.info("  DB: %s", self.config.db_path)
        logger.info("  Log: %s", self.config.log_path)
        logger.info("  Firewall: %s", self.config.firewall_strategy)
        logger.info("  GeoIP: %s", self.config.geoip_provider)

        # Handle shutdown signals
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: self._shutdown.set())

        # 1. Database
        os.makedirs(os.path.dirname(self.config.db_path) or ".", exist_ok=True)
        db = SqliteDatabase(self.config.db_path)
        init_database(db)
        alert_repo = PeeweeAlertRepository(db)
        block_repo = PeeweeBlockRepo()

        # 2. Metrics
        metrics = MetricsCollector()

        # 3. Event broker
        broker = EventBroker()

        # 4. Plugin registry
        registry = ParserRegistry()
        registry.register("ssh_auth", SSHAuthPlugin)
        logger.info("Registered plugins: %s", registry.list_available())

        # 5. Enrichment pipeline
        geoip = GeoIPEnricher(
            provider=self.config.geoip_provider,
            db_path=None,  # MaxMind not available in test mode
        )

        # 6. Firewall strategy
        strategy: FirewallStrategy
        if self.config.firewall_strategy == "ufw":
            strategy = UFWStrategy()
            logger.info("Firewall: UFW (production)")
        else:
            strategy = NoOpStrategy()
            logger.info("Firewall: NoOp (test mode)")

        # 7. Block service
        block_svc = BlockService(strategy=strategy, repo=block_repo)

        # 8. Alert channel
        alert_channel: AlertChannel = ConsoleChannel()
        logger.info("Alert channel: %s", alert_channel.name)

        # 9. Detector
        detector = ThresholdDetector(
            threshold=self.config.block_threshold, window_seconds=300
        )
        detector.register_broker(broker)

        # 10. Wire: event → enrich → block → alert → metric
        def on_security_event(event: SecurityEvent) -> None:
            logger.warning(
                "BREACH: %s — %d attempts from %s",
                event.service, event.attempt_count, event.ip,
            )

            # Persist to database
            alert_repo.create(
                ip=event.ip, attempts=event.attempt_count,
                service=event.service,
            )

            # Block
            block_svc.handle_event(event)
            metrics.record_block(
                event.ip,
                strategy.__class__.__name__,
                f"{event.service} brute-force: {event.attempt_count}",
            )

            # Enrich
            try:
                ip_obj = IPv4Address(event.ip)
            except ValueError:
                ip_obj = IPv4Address("127.0.0.1")

            enriched = EnrichedEvent.from_parsed_entry(
                ParsedEntry(
                    ip=ip_obj,
                    timestamp=event.timestamp,
                    service=event.service,
                    event_type="failed_auth",
                    raw_line=event.log_line,
                )
            )
            enriched = geoip.enrich(enriched)

            # Alert
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    alert_channel.send(enriched, {})
                )
                loop.close()
                if result.success:
                    metrics.record_alert(enriched, alert_channel.name)
            except Exception as exc:
                logger.error("Alert channel failed: %s", exc)

        broker.subscribe(on_security_event)

        # 11. Command handler
        cmd_handler = create_command_handler(block_svc, alert_repo)

        # 12. Web dashboard
        app = create_app(alert_repo=alert_repo, api_token=self.config.api_token)
        app.config["TESTING"] = True

        # Add /metrics endpoint
        @app.route("/metrics")
        def metrics_endpoint():
            from flask import Response
            return Response(metrics.render(), mimetype="text/plain")

        def run_web() -> None:
            import werkzeug.serving
            werkzeug.serving._log = lambda *a: None  # silence Flask logs
            app.run(
                host=self.config.web_host,
                port=self.config.web_port,
                use_reloader=False,
            )

        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()
        logger.info(
            "Web dashboard: http://%s:%s",
            self.config.web_host, self.config.web_port,
        )

        # 13. CLI test mode
        if self.config.cli_mode:
            cli = CLIInputAdapter()
            logger.info("CLI test mode ready. Type '/status' to begin.")

            def run_cli() -> None:
                cli.start_listening(cmd_handler)
                self._shutdown.set()

            cli_thread = threading.Thread(target=run_cli, daemon=True)
            cli_thread.start()

        # 14. Log parser (main loop — blocks until shutdown)
        parser = registry.create("ssh_auth", {
            "log_path": self.config.log_path,
        })
        assert isinstance(parser, SSHAuthPlugin), "Expected SSHAuthPlugin"

        def on_entry(entry: ParsedEntry) -> None:
            start = time.monotonic()
            detector.record_attempt(str(entry.ip), entry.timestamp)
            duration = time.monotonic() - start
            metrics.observe_processing_time(parser.name, duration)

        logger.info("Monitoring %s (press Ctrl+C to stop)", self.config.log_path)

        try:
            parser.process_stream(self.config.log_path, callback=on_entry)
        except Exception as exc:
            logger.error("Log parser error: %s", exc)

        logger.info("Worker shutting down")


def main() -> None:
    """Entry point."""
    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
