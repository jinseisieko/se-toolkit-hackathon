"""Unit tests for BlockService.

Covers:
- handle_event blocks IP via strategy and records in repository
- block_ip returns False when strategy fails
- unblock_ip returns False when IP not in repository
- NoOpStrategy path never calls subprocess
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.core.events import SecurityEvent
from src.core.services.block_service import BlockService, BlockRepository
from src.adapters.firewall.noop import NoOpStrategy


@pytest.fixture
def mock_strategy() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def noop_logger() -> MagicMock:
    return MagicMock()


# ── Happy path ───────────────────────────────────────────────


class TestBlockServiceHappyPath:
    def test_handle_event_blocks_ip_and_records(
        self, mock_strategy: MagicMock, mock_repo: MagicMock
    ) -> None:
        mock_strategy.block.return_value = True
        mock_repo.get_by_ip.return_value = None
        mock_repo.create.return_value = MagicMock(id=1)

        service = BlockService(strategy=mock_strategy, repo=mock_repo)

        event = SecurityEvent(
            ip="192.0.2.1",
            attempt_count=5,
            timestamp=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
            log_line="Failed password for root from 192.0.2.1",
            service="ssh",
        )

        result = service.handle_event(event)

        assert result is True
        mock_strategy.block.assert_called_once_with(
            "192.0.2.1", "SSH brute-force: 5 attempts"
        )
        mock_repo.create.assert_called_once()

    def test_handle_event_skips_already_blocked(
        self, mock_strategy: MagicMock, mock_repo: MagicMock
    ) -> None:
        existing = MagicMock(id=42)
        mock_repo.get_by_ip.return_value = existing
        mock_repo.mark_blocked.return_value = True

        service = BlockService(strategy=mock_strategy, repo=mock_repo)

        event = SecurityEvent(
            ip="192.0.2.1",
            attempt_count=5,
            timestamp=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
            log_line="",
            service="ssh",
        )

        result = service.handle_event(event)

        assert result is True
        mock_strategy.block.assert_not_called()  # already recorded
        mock_repo.mark_blocked.assert_called_once_with(42)


# ── Edge cases ──────────────────────────────────────────────


class TestBlockServiceEdgeCases:
    def test_block_ip_returns_false_when_strategy_fails(
        self, mock_strategy: MagicMock, mock_repo: MagicMock
    ) -> None:
        mock_strategy.block.return_value = False

        service = BlockService(strategy=mock_strategy, repo=mock_repo)
        result = service.block_ip("192.0.2.1", "manual block")

        assert result is False
        mock_repo.create.assert_not_called()

    def test_unblock_ip_returns_false_when_not_found(
        self, mock_strategy: MagicMock, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_ip.return_value = None

        service = BlockService(strategy=mock_strategy, repo=mock_repo)
        result = service.unblock_ip("192.0.2.1")

        assert result is False
        mock_strategy.unblock.assert_not_called()

    def test_unblock_ip_calls_strategy_then_repo(
        self, mock_strategy: MagicMock, mock_repo: MagicMock
    ) -> None:
        blocked_record = MagicMock(id=7, is_blocked=True)
        mock_repo.get_by_ip.return_value = blocked_record
        mock_strategy.unblock.return_value = True
        mock_repo.mark_unblocked.return_value = True

        service = BlockService(strategy=mock_strategy, repo=mock_repo)
        result = service.unblock_ip("192.0.2.1")

        assert result is True
        mock_strategy.unblock.assert_called_once_with("192.0.2.1")
        mock_repo.mark_unblocked.assert_called_once_with(7)

    def test_noop_strategy_block_never_calls_subprocess(
        self, noop_logger: MagicMock
    ) -> None:
        """Critical: NoOpStrategy must never touch subprocess."""
        from unittest.mock import patch
        import subprocess

        strategy = NoOpStrategy(logger=noop_logger)
        mock_repo = MagicMock()
        mock_repo.get_by_ip.return_value = None

        service = BlockService(strategy=strategy, repo=mock_repo)

        with patch.object(subprocess, "run") as mock_run:
            result = service.block_ip("192.0.2.1", "test")

        assert result is True
        mock_run.assert_not_called()
