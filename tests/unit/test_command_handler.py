"""Unit tests for CommandHandler and CLIInputAdapter.

Covers:
- /status returns alert and blocked counts
- /unblock <ip> calls block_service.unblock_ip
- /block <ip> calls block_service.block_ip
- Unknown command returns error result
- Action not in allowed_actions → permission denied
- CLIInputAdapter parses "/cmd arg1 arg2" correctly
- CLIInputAdapter handles empty input gracefully
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.interfaces.commands.handler import (
    CommandContext,
    CommandHandler,
    CommandResult,
)
from src.interfaces.commands.cli import CLIInputAdapter


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_block_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_alert_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def handler(mock_block_service: MagicMock, mock_alert_repo: MagicMock) -> CommandHandler:
    return CommandHandler(
        block_service=mock_block_service,
        alert_repo=mock_alert_repo,
    )


@pytest.fixture
def admin_context() -> CommandContext:
    return CommandContext(
        user_id="admin",
        is_test_mode=False,
        allowed_actions={"status", "block", "unblock"},
    )


@pytest.fixture
def restricted_context() -> CommandContext:
    return CommandContext(
        user_id="viewer",
        is_test_mode=True,
        allowed_actions={"status"},
    )


# ── Happy path ────────────────────────────────────────────────


class TestCommandHandlerHappyPath:
    def test_status_returns_counts(
        self, handler: CommandHandler, mock_alert_repo: MagicMock, admin_context: CommandContext
    ) -> None:
        mock_alert_repo.get_recent.return_value = [
            MagicMock(id=1, blocked=False),
            MagicMock(id=2, blocked=False),
            MagicMock(id=3, blocked=True),
        ]

        result = handler.handle("status", [], admin_context)

        assert result.success is True
        assert "Active: 2" in result.message
        assert "Blocked: 1" in result.message

    def test_unblock_calls_block_service(
        self,
        handler: CommandHandler,
        mock_block_service: MagicMock,
        admin_context: CommandContext,
    ) -> None:
        mock_block_service.unblock_ip.return_value = True

        result = handler.handle("unblock", ["192.0.2.1"], admin_context)

        assert result.success is True
        mock_block_service.unblock_ip.assert_called_once_with("192.0.2.1")

    def test_block_calls_block_service(
        self,
        handler: CommandHandler,
        mock_block_service: MagicMock,
        admin_context: CommandContext,
    ) -> None:
        mock_block_service.block_ip.return_value = True

        result = handler.handle("block", ["10.0.0.1", "manual"], admin_context)

        assert result.success is True
        mock_block_service.block_ip.assert_called_once_with(
            "10.0.0.1", "manual"
        )


# ── Edge cases ────────────────────────────────────────────────


class TestCommandHandlerEdgeCases:
    def test_unknown_command_returns_error(
        self, handler: CommandHandler, admin_context: CommandContext
    ) -> None:
        result = handler.handle("foobar", [], admin_context)

        assert result.success is False
        assert "Unknown" in result.message

    def test_unblock_missing_ip_returns_error(
        self, handler: CommandHandler, admin_context: CommandContext
    ) -> None:
        result = handler.handle("unblock", [], admin_context)

        assert result.success is False
        assert "IP" in result.message

    def test_action_not_in_allowed_actions_denied(
        self,
        handler: CommandHandler,
        mock_block_service: MagicMock,
        restricted_context: CommandContext,
    ) -> None:
        result = handler.handle("unblock", ["1.2.3.4"], restricted_context)

        assert result.success is False
        assert "denied" in result.message.lower()
        mock_block_service.unblock_ip.assert_not_called()

    def test_unblock_strategy_failure(
        self,
        handler: CommandHandler,
        mock_block_service: MagicMock,
        admin_context: CommandContext,
    ) -> None:
        mock_block_service.unblock_ip.return_value = False

        result = handler.handle("unblock", ["192.0.2.1"], admin_context)

        assert result.success is False
        assert "Failed" in result.message

    def test_empty_alert_list_shows_zeroes(
        self, handler: CommandHandler, mock_alert_repo: MagicMock, admin_context: CommandContext
    ) -> None:
        mock_alert_repo.get_recent.return_value = []

        result = handler.handle("status", [], admin_context)

        assert result.success is True
        assert "Active: 0" in result.message
        assert "Blocked: 0" in result.message


# ── CLIInputAdapter ───────────────────────────────────────────


class TestCLIInputAdapter:
    def test_parses_commands_correctly(
        self,
    ) -> None:
        """Simulates 3 inputs then stop (empty line)."""
        # Test parse_command static method directly (avoid infinite loop)
        assert CLIInputAdapter._parse_command("/status") == ("status", [])
        assert CLIInputAdapter._parse_command("/unblock 192.0.2.1") == (
            "unblock",
            ["192.0.2.1"],
        )
        assert CLIInputAdapter._parse_command("") is None
        assert CLIInputAdapter._parse_command("  /block 10.0.0.1 reason  ") == (
            "block",
            ["10.0.0.1", "reason"],
        )

    def test_parse_command_ignores_non_slash_input(self) -> None:
        assert CLIInputAdapter._parse_command("just some text") is None

    def test_parse_command_strips_leading_slash(self) -> None:
        assert CLIInputAdapter._parse_command("/help") == ("help", [])
