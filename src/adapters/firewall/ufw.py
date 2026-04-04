"""UFW firewall strategy — production implementation.

Wraps ``ufw`` CLI commands via subprocess.  All methods validate the IP
before executing to prevent command injection.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

from src.core.blocking import FirewallStrategy
from src.utils.validation import validate_ip

logger = logging.getLogger(__name__)


class UFWStrategy(FirewallStrategy):
    """Production firewall strategy using the ``ufw`` command-line tool."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def block(self, ip: str, reason: str, duration: int | None = None) -> bool:
        """Block *ip* via ``ufw deny from <ip>``."""
        validate_ip(ip)
        self._logger.info("Blocking %s: %s", ip, reason)

        result = subprocess.run(
            ["ufw", "deny", "from", ip],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self._logger.error("ufw block failed for %s: %s", ip, result.stderr)
            return False

        self._logger.debug("ufw blocked %s successfully", ip)
        return True

    def unblock(self, ip: str) -> bool:
        """Remove the ufw deny rule for *ip*."""
        validate_ip(ip)
        self._logger.info("Unblocking %s", ip)

        result = subprocess.run(
            ["ufw", "delete", "deny", "from", ip],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self._logger.warning(
                "ufw unblock failed for %s: %s", ip, result.stderr
            )
            return False

        self._logger.debug("ufw unblocked %s successfully", ip)
        return True

    def is_blocked(self, ip: str) -> bool:
        """Check if *ip* appears in ufw status output as DENY."""
        validate_ip(ip)

        try:
            result = subprocess.run(
                ["ufw", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            self._logger.error("ufw status check failed: %s", exc)
            return False

        if result.returncode != 0:
            self._logger.warning("ufw status returned error: %s", result.stderr)
            return False

        # Each rule line starts with the IP.  Look for "DENY IN".
        for line in result.stdout.splitlines():
            if line.startswith(ip) and "DENY IN" in line:
                return True

        return False
