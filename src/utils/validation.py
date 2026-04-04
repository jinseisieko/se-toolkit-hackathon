"""Validation helpers for network inputs."""

from __future__ import annotations

import ipaddress
import os
import re

# Whitelist of safe characters in file paths
# Only alphanumeric, dots, slashes, dashes, underscores
_SAFE_PATH_RE = re.compile(r'^[a-zA-Z0-9._/\-]+$')


class InvalidIPError(ValueError):
    """Raised when an IP address string is not a valid IPv4/IPv6 address."""


def validate_ip(ip: str) -> str:
    """Validate and return a normalized IP address string.

    Args:
        ip: The IP address string to validate.

    Returns:
        The normalized IP string.

    Raises:
        InvalidIPError: If the string is not a valid IP address.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise InvalidIPError(f"Invalid IP address: {ip!r}") from exc

    return str(addr)


def validate_ip_strict(ip: str) -> str:
    """Validate IPv4 only (legacy compatibility).

    Args:
        ip: The IP address string to validate.

    Returns:
        The normalized IPv4 string.

    Raises:
        InvalidIPError: If the string is not a valid IPv4 address.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise InvalidIPError(f"Invalid IP address: {ip!r}") from exc

    if not isinstance(addr, ipaddress.IPv4Address):
        raise InvalidIPError(f"Only IPv4 is supported: {ip!r}")

    return str(addr)


def validate_log_path(path: str) -> str:
    """Validate a log file path to prevent command injection.

    Only allows paths with safe characters (alphanumeric, dots,
    slashes, dashes, underscores). Rejects shell metacharacters
    like ;, |, &, $, `, etc.

    Args:
        path: The file path to validate.

    Returns:
        The resolved absolute path.

    Raises:
        ValueError: If the path contains unsafe characters.
    """
    if not path:
        raise ValueError("Log path cannot be empty")

    if not _SAFE_PATH_RE.match(path):
        raise ValueError(
            f"Log path contains unsafe characters: {path!r}. "
            "Only alphanumeric, dots, slashes, dashes, and underscores allowed."
        )

    resolved = os.path.realpath(path)

    # Must be under /var/log or /app or the current working directory
    safe_prefixes = ("/var/log", "/app", os.getcwd())
    if not any(resolved.startswith(p) for p in safe_prefixes):
        raise ValueError(
            f"Log path must be under /var/log or /app: {resolved}"
        )

    return resolved
