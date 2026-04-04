"""BlockService — coordinates firewall strategy with persistence.

Composes a ``FirewallStrategy`` and a ``BlockRepository``.  The service
orchestrates the decision flow: check if already blocked → call strategy
→ persist result.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.core.blocking import FirewallStrategy
from src.core.events import SecurityEvent

logger = logging.getLogger(__name__)


@dataclass
class BlockedIPRecord:
    """Represents a persisted block record."""

    id: int
    ip: str
    blocked_at: datetime
    reason: str
    strategy: str
    is_blocked: bool


class BlockRepository(ABC):
    """Abstract data-access contract for blocked IP records."""

    @abstractmethod
    def create(
        self, ip: str, reason: str, strategy: str
    ) -> BlockedIPRecord:
        """Persist a new block record.

        Args:
            ip: The blocked IP address.
            reason: Why it was blocked.
            strategy: Which strategy was used (e.g. 'ufw', 'noop').

        Returns:
            The created record with an assigned ID.
        """
        ...

    @abstractmethod
    def get_by_ip(self, ip: str) -> BlockedIPRecord | None:
        """Return the record for *ip*, or None if no record exists."""
        ...

    @abstractmethod
    def mark_blocked(self, record_id: int) -> bool:
        """Set ``is_blocked=True`` on an existing record."""
        ...

    @abstractmethod
    def mark_unblocked(self, record_id: int) -> bool:
        """Set ``is_blocked=False`` on an existing record."""
        ...


class BlockService:
    """High-level service for managing IP blocks.

    Uses composition: *has a* strategy, *has a* repository.
    """

    def __init__(
        self,
        strategy: FirewallStrategy,
        repo: BlockRepository,
    ) -> None:
        self._strategy = strategy
        self._repo = repo

    def handle_event(self, event: SecurityEvent) -> bool:
        """Process a security event: block the source IP if not already done.

        If a record already exists for this IP, the existing record is
        marked as blocked and no duplicate firewall call is made.

        Args:
            event: The SecurityEvent triggering the block.

        Returns:
            True on success, False on failure.
        """
        existing = self._repo.get_by_ip(event.ip)

        if existing is not None:
            logger.debug("IP %s already has a record, marking blocked", event.ip)
            return self._repo.mark_blocked(existing.id)

        reason = f"{event.service.upper()} brute-force: {event.attempt_count} attempts"
        if not self._strategy.block(event.ip, reason):
            return False

        self._repo.create(ip=event.ip, reason=reason, strategy=self._strategy.__class__.__name__)
        logger.info("Auto-blocked %s via %s", event.ip, self._strategy.__class__.__name__)
        return True

    def block_ip(self, ip: str, reason: str = "manual block") -> bool:
        """Manually block an IP.

        Args:
            ip: The IP to block.
            reason: Human-readable reason.

        Returns:
            True on success, False if the strategy failed.
        """
        if not self._strategy.block(ip, reason):
            return False

        self._repo.create(ip=ip, reason=reason, strategy=self._strategy.__class__.__name__)
        return True

    def unblock_ip(self, ip: str) -> bool:
        """Manually unblock an IP.

        Args:
            ip: The IP to unblock.

        Returns:
            True on success, False if no record exists or strategy failed.
        """
        record = self._repo.get_by_ip(ip)
        if record is None:
            logger.warning("Cannot unblock %s: no record found", ip)
            return False

        if not self._strategy.unblock(ip):
            return False

        return self._repo.mark_unblocked(record.id)
