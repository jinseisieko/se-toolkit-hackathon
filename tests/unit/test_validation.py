"""Unit tests for validation helpers.

Covers:
- validate_ip accepts valid IPv4/IPv6
- validate_ip rejects invalid strings
- validate_ip_strict rejects IPv6
- validate_log_path accepts safe paths under /var/log
- validate_log_path rejects shell metacharacters
- validate_log_path rejects paths outside safe prefixes
"""

from __future__ import annotations

import pytest

from src.utils.validation import (
    InvalidIPError,
    validate_ip,
    validate_ip_strict,
    validate_log_path,
)


class TestValidateIP:
    def test_valid_ipv4(self) -> None:
        assert validate_ip("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv6(self) -> None:
        result = validate_ip("2001:db8::1")
        assert "2001:db8" in result

    def test_invalid_string(self) -> None:
        with pytest.raises(InvalidIPError):
            validate_ip("not-an-ip")

    def test_command_injection(self) -> None:
        with pytest.raises(InvalidIPError):
            validate_ip("1.2.3.4; rm -rf /")

    def test_empty_string(self) -> None:
        with pytest.raises(InvalidIPError):
            validate_ip("")


class TestValidateIPStrict:
    def test_valid_ipv4(self) -> None:
        assert validate_ip_strict("10.0.0.1") == "10.0.0.1"

    def test_rejects_ipv6(self) -> None:
        with pytest.raises(InvalidIPError):
            validate_ip_strict("2001:db8::1")


class TestValidateLogPath:
    def test_accepts_var_log(self) -> None:
        result = validate_log_path("/var/log/auth.log")
        assert result.startswith("/var/log/auth.log")

    def test_accepts_safe_chars(self) -> None:
        result = validate_log_path("/var/log/my-app_2024/auth.log")
        assert "auth.log" in result

    def test_rejects_semicolon(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            validate_log_path("/var/log/auth.log; rm -rf /")
        assert "unsafe characters" in str(exc_info.value).lower()

    def test_rejects_pipe(self) -> None:
        with pytest.raises(ValueError):
            validate_log_path("/var/log/auth.log | cat")

    def test_rejects_backticks(self) -> None:
        with pytest.raises(ValueError):
            validate_log_path("/var/log/`whoami`.log")

    def test_rejects_dollar_sign(self) -> None:
        with pytest.raises(ValueError):
            validate_log_path("/var/log/$HOME/auth.log")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_log_path("")

    def test_rejects_outside_safe_prefixes(self) -> None:
        # /etc/passwd is not under /var/log, /app, or cwd
        with pytest.raises(ValueError):
            validate_log_path("/etc/passwd")
