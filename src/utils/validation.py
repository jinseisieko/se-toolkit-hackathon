"""Validation helpers for network inputs."""

from __future__ import annotations

import ipaddress


class InvalidIPError(ValueError):
    """Raised when an IP address string is not a valid IPv4 address."""


def validate_ip(ip: str) -> str:
    """Validate and return a normalized IPv4 address string.

    Args:
        ip: The IP address string to validate.

    Returns:
        The normalized IP string.

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
