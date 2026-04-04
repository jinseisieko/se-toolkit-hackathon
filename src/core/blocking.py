"""Firewall strategy abstract base class (Strategy pattern).

All concrete strategies implement this interface.  The ``BlockService``
composes one strategy instance, allowing production (UFW) and test (NoOp)
behaviours to be swapped without changing core logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class FirewallStrategy(ABC):
    """Abstract contract for firewall operations."""

    @abstractmethod
    def block(self, ip: str, reason: str, duration: int | None = None) -> bool:
        """Block *ip* at the firewall.

        Args:
            ip: IPv4 address to block.
            reason: Human-readable reason for the block.
            duration: Optional block duration in seconds (not all backends
                support timed blocks).

        Returns:
            True on success, False on failure.
        """
        ...

    @abstractmethod
    def unblock(self, ip: str) -> bool:
        """Remove the block for *ip*.

        Returns:
            True on success, False on failure (e.g. IP was not blocked).
        """
        ...

    @abstractmethod
    def is_blocked(self, ip: str) -> bool:
        """Check whether *ip* is currently blocked.

        Returns:
            True if blocked, False otherwise.  On backend errors returns
            False as a safe default.
        """
        ...
