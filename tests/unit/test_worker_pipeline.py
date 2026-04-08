"""Worker pipeline integration tests."""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from ipaddress import IPv4Address

import pytest
from peewee import SqliteDatabase

from src.core.plugins.parser_plugin import ParsedEntry
from src.core.repositories import PeeweeAlertRepository
from src.infrastructure.db import init_database
from src.worker import Worker


def test_worker_marks_auto_blocked_alerts(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "sentinel.db"
    log_path = tmp_path / "auth.log"
    log_path.write_text("", encoding="utf-8")

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("LOG_PATH", str(log_path))
    monkeypatch.setenv("BLOCK_THRESHOLD", "2")
    monkeypatch.setenv("FIREWALL_STRATEGY", "noop")
    monkeypatch.setenv("GEOIP_PROVIDER", "mock")
    monkeypatch.setattr(signal, "signal", lambda *args, **kwargs: None)

    class FakeParser:
        name = "ssh_auth"

        def process_stream(self, file_path, callback, stop_event=None) -> None:
            assert file_path == str(log_path)
            callback(
                ParsedEntry(
                    ip=IPv4Address("192.0.2.10"),
                    timestamp=datetime.now(timezone.utc),
                    service="ssh",
                    event_type="failed_auth",
                    raw_line="line1",
                )
            )
            callback(
                ParsedEntry(
                    ip=IPv4Address("192.0.2.10"),
                    timestamp=datetime.now(timezone.utc),
                    service="ssh",
                    event_type="failed_auth",
                    raw_line="line2",
                )
            )

    class FakeRegistry:
        def register(self, name, parser_cls) -> None:
            return None

        def list_available(self):
            return ["ssh_auth"]

        def create(self, name, config):
            assert name == "ssh_auth"
            assert config["log_path"] == str(log_path)
            return FakeParser()

    monkeypatch.setattr("src.worker.ParserRegistry", FakeRegistry)

    Worker().run()

    db = SqliteDatabase(str(db_path))
    init_database(db)
    repo = PeeweeAlertRepository(db)
    alerts = repo.get_recent()

    assert len(alerts) == 1
    assert alerts[0].ip == "192.0.2.10"
    assert alerts[0].blocked is True
