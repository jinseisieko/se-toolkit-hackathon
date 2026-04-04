"""NoOp firewall strategy — test-mode implementation.

Logs all blocking decisions without executing any subprocess calls.
Use this during development and testing to avoid accidentally blocking
real IPs.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.blocking import FirewallStrategy

logger = logging.getLogger(__name__)


class NoOpStrategy(FirewallStrategy):
    """Test-mode strategy: logs actions, never touches the firewall.

    All methods return ``True`` (simulated success) without calling
    ``subprocess.run``.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def block(self, ip: str, reason: str, duration: int | None = None) -> bool:
        duration_msg = f" for {duration}s" if duration else ""
        self._logger.info(
            "[TEST MODE] Would block %s: %s%s", ip, reason, duration_msg
        )
        return True

    def unblock(self, ip: str) -> bool:
        self._logger.info("[TEST MODE] Would unblock %s", ip)
        return True

    def is_blocked(self, ip: str) -> bool:
        self._logger.debug("[TEST MODE] is_blocked(%s) → False", ip)
        return False
