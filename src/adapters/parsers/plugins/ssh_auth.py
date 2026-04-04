"""SSH authentication log parser plugin (V2 migration from V1).

Implements ``LogParserPlugin`` to parse ``/var/log/auth.log`` lines
for failed SSH login attempts.  Produces normalised ``ParsedEntry``
objects with IPv4Address, event_type, and structured metadata.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address
from typing import Any, Dict, List, Optional

from src.core.plugins.parser_plugin import (
    DetectionRule,
    LogParserPlugin,
    ParsedEntry,
    Severity,
)

logger = logging.getLogger(__name__)


class SSHAuthPlugin(LogParserPlugin):
    """Parses SSH authentication failures from syslog auth.log.

    Handles lines like::

        Apr  4 12:00:01 server sshd[1]: \
            Failed password for root from 192.0.2.1 port 22 ssh2
        Apr  4 12:00:01 server sshd[1]: \
            Failed publickey for deploy from 10.0.0.1 port 22 ssh2

    Config keys:
        log_path: Override the default log path (default: /var/log/auth.log).
    """

    # Matches both password and publickey, with optional "invalid user" prefix
    _FAILED_PATTERN = re.compile(
        r"Failed\s+(password|publickey)\s+for\s+"
        r"(?:invalid\s+user\s+)?"
        r"(\S+)\s+"
        r"from\s+"
        r"(\S+)\s+"
        r"port\s+(\d+)"
    )

    # Syslog timestamp: "Apr  4 12:00:01"
    _TIMESTAMP_PATTERN = re.compile(
        r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        raw_path = self._config.get("log_path", "/var/log/auth.log")
        self._log_path: str = str(raw_path)

    @property
    def name(self) -> str:
        return "ssh_auth"

    @property
    def default_log_path(self) -> str:
        return self._log_path

    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        """Parse a single auth.log line for SSH failure patterns.

        Args:
            line: Raw log line text.

        Returns:
            A ``ParsedEntry`` if the line matches a failed SSH attempt,
            or ``None`` otherwise.
        """
        stripped = line.strip()
        if not stripped:
            return None

        match = self._FAILED_PATTERN.search(stripped)
        if not match:
            return None

        auth_type = match.group(1)
        user = match.group(2)
        ip_raw = match.group(3)
        port = match.group(4)

        ip_type = self._classify_ip(ip_raw)
        if ip_type == "invalid":
            logger.debug("Skipping invalid IP: %s", ip_raw)
            return None

        timestamp = self._extract_timestamp(stripped)
        event_type = (
            "failed_auth" if auth_type == "password" else "failed_publickey"
        )

        meta: Dict[str, Any] = {
            "auth_type": auth_type,
            "port": port,
            "ip_type": ip_type,
        }

        # For V1 compatibility, also store the raw IPv4/IPv6 string
        ip_obj: IPv4Address | IPv6Address
        if ip_type == "ipv4":
            ip_obj = IPv4Address(ip_raw)
        else:
            ip_obj = IPv6Address(ip_raw)

        return ParsedEntry(
            ip=ip_obj,
            timestamp=timestamp,
            service="ssh",
            user=user,
            event_type=event_type,
            raw_line=stripped,
            meta=meta,
        )

    def get_indicators(self) -> List[DetectionRule]:
        """Return detection rules supported by this plugin.

        Returns:
            A list with rules for failed password and failed publickey.
        """
        return [
            DetectionRule(
                name="ssh_failed_password",
                pattern=re.compile(r"Failed\s+password\s+for"),
                severity=Severity.HIGH,
                threshold=5,
                window_seconds=300,
            ),
            DetectionRule(
                name="ssh_failed_publickey",
                pattern=re.compile(r"Failed\s+publickey\s+for"),
                severity=Severity.MEDIUM,
                threshold=10,
                window_seconds=600,
            ),
        ]

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _classify_ip(ip_str: str) -> str:
        """Classify an IP address string.

        Returns:
            ``ipv4``, ``ipv6``, or ``invalid``.
        """
        try:
            addr = ipaddress.ip_address(ip_str)
            return "ipv4" if isinstance(addr, IPv4Address) else "ipv6"
        except ValueError:
            return "invalid"

    @staticmethod
    def _extract_timestamp(line: str) -> datetime:
        """Extract the syslog timestamp from a log line.

        Falls back to the current UTC time if parsing fails.

        Args:
            line: The full log line.

        Returns:
            A timezone-aware datetime.
        """
        match = SSHAuthPlugin._TIMESTAMP_PATTERN.search(line)
        if not match:
            logger.debug(
                "No timestamp found in line, using current time: %r",
                line[:80],
            )
            return datetime.now(timezone.utc)

        ts_str = match.group(1)
        try:
            year = datetime.now().year
            dt = datetime.strptime(f"{year} {ts_str}", "%Y %b %d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.debug(
                "Failed to parse timestamp %r, using current time", ts_str
            )
            return datetime.now(timezone.utc)
