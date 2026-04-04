"""Unit tests for FirewallStrategy implementations.

Covers:
- NoOpStrategy.block() logs but never calls subprocess
- NoOpStrategy.unblock() / is_blocked() behave consistently
- UFWStrategy.block() calls correct ufw command
- UFWStrategy.unblock() calls correct ufw command
- UFWStrategy.is_blocked() checks status correctly
- Invalid IP raises ValueError at adapter boundary
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.firewall.noop import NoOpStrategy
from src.adapters.firewall.ufw import UFWStrategy
from src.utils.validation import InvalidIPError, validate_ip


# ── NoOpStrategy (test mode) ─────────────────────────────────


class TestNoOpStrategy:
    def test_block_never_calls_subprocess(self) -> None:
        mock_logger = MagicMock()
        strategy = NoOpStrategy(logger=mock_logger)

        with patch.object(subprocess, "run") as mock_run:
            result = strategy.block("192.0.2.1", "test brute-force")

        assert result is True
        mock_run.assert_not_called()
        mock_logger.info.assert_called_once()

    def test_unblock_never_calls_subprocess(self) -> None:
        mock_logger = MagicMock()
        strategy = NoOpStrategy(logger=mock_logger)

        with patch.object(subprocess, "run") as mock_run:
            result = strategy.unblock("192.0.2.1")

        assert result is True
        mock_run.assert_not_called()
        mock_logger.info.assert_called_once()

    def test_is_blocked_always_returns_false(self) -> None:
        strategy = NoOpStrategy(logger=MagicMock())

        assert strategy.is_blocked("192.0.2.1") is False
        assert strategy.is_blocked("10.0.0.1") is False


# ── UFWStrategy (production) ────────────────────────────────


class TestUFWStrategy:
    @patch("src.adapters.firewall.ufw.subprocess.run")
    def test_block_calls_ufw_deny(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        strategy = UFWStrategy(logger=MagicMock())

        result = strategy.block("192.0.2.1", "SSH brute-force")

        assert result is True
        mock_run.assert_called_once_with(
            ["ufw", "deny", "from", "192.0.2.1"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("src.adapters.firewall.ufw.subprocess.run")
    def test_block_returns_false_on_failure(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        strategy = UFWStrategy(logger=MagicMock())

        result = strategy.block("192.0.2.1", "test")

        assert result is False

    @patch("src.adapters.firewall.ufw.subprocess.run")
    def test_unblock_calls_ufw_delete(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        strategy = UFWStrategy(logger=MagicMock())

        result = strategy.unblock("192.0.2.1")

        assert result is True
        mock_run.assert_called_once_with(
            ["ufw", "delete", "deny", "from", "192.0.2.1"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("src.adapters.firewall.ufw.subprocess.run")
    def test_unblock_returns_false_on_failure(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        strategy = UFWStrategy(logger=MagicMock())

        result = strategy.unblock("192.0.2.1")

        assert result is False

    @patch("src.adapters.firewall.ufw.subprocess.run")
    def test_is_blocked_parses_status(self, mock_run: MagicMock) -> None:
        # ufw status output with a blocked IP
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="192.0.2.1                  DENY IN    Anywhere\n",
        )
        strategy = UFWStrategy(logger=MagicMock())

        assert strategy.is_blocked("192.0.2.1") is True
        assert strategy.is_blocked("10.0.0.1") is False

    @patch("src.adapters.firewall.ufw.subprocess.run")
    def test_is_blocked_handles_ufw_error(
        self, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="broken")
        strategy = UFWStrategy(logger=MagicMock())

        # On error, is_blocked should return False (safe default)
        assert strategy.is_blocked("192.0.2.1") is False


# ── IP validation at adapter boundary ────────────────────────


class TestIPValidation:
    def test_validate_ip_accepts_valid_ipv4(self) -> None:
        validate_ip("192.168.1.1")  # should not raise

    def test_validate_ip_rejects_invalid(self) -> None:
        with pytest.raises(InvalidIPError):
            validate_ip("not-an-ip")

    def test_validate_ip_rejects_localhost_edge_cases(self) -> None:
        # "999.999.999.999" is invalid
        with pytest.raises(InvalidIPError):
            validate_ip("999.999.999.999")
