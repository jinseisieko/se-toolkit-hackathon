"""SSH authentication log parser.

.. deprecated::
    This legacy parser inherits from ``BaseLogParser`` and is kept for
    backward compatibility with demo scripts and V1 test suites.
    The production worker (``src/worker.py``) uses the V2 plugin
    ``SSHAuthPlugin`` (``src/adapters/parsers/plugins/ssh_auth.py``)
    which implements ``LogParserPlugin`` and supports the plugin registry.

Parses ``/var/log/auth.log`` lines for failed SSH login attempts.
Supports both ``Failed password`` and ``Failed publickey`` patterns,
including the ``invalid user`` variant.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from src.adapters.log_tail import BaseLogParser, ParsedEntry

logger = logging.getLogger(__name__)


class SSHAuthLogParser(BaseLogParser):
    """Parses SSH authentication failures from auth.log.

    Handles syslog-style lines like::

        Apr  4 12:00:01 server sshd[12345]: Failed password for root from 192.0.2.1 port 22 ssh2
        Apr  4 12:00:01 server sshd[12345]: Failed password for invalid user admin from 10.0.0.1 port 22 ssh2
        Apr  4 12:00:01 server sshd[12345]: Failed publickey for deploy from 172.16.0.5 port 22 ssh2
    """

    # Matches both password and publickey, with optional "invalid user <user>"
    FAILED_PATTERN = re.compile(
        r"Failed\s+(password|publickey)\s+for\s+"
        r"(?:invalid\s+user\s+)?"  # optional "invalid user" prefix
        r"(\S+)\s+"                  # username
        r"from\s+"
        r"(\S+)\s+"                  # IP address
        r"port\s+(\d+)"              # port number
    )

    # Syslog timestamp: "Apr  4 12:00:01"
    TIMESTAMP_PATTERN = re.compile(
        r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
    )

    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        """Parse a single auth.log line for SSH failure patterns.

        Args:
            line: Raw log line from auth.log.

        Returns:
            A ParsedEntry if the line matches a failed SSH attempt,
            or None otherwise.
        """
        stripped = line.strip()
        if not stripped:
            return None

        match = self.FAILED_PATTERN.search(stripped)
        if not match:
            return None

        auth_type = match.group(1)
        user = match.group(2)
        ip_raw = match.group(3)
        port = match.group(4)

        # Determine IP type
        ip_type = self._classify_ip(ip_raw)
        if ip_type == "invalid":
            logger.debug("Skipping invalid IP: %s", ip_raw)
            return None

        timestamp = self._extract_timestamp(stripped)

        metadata = {
            "service": "ssh",
            "auth_type": auth_type,
            "port": port,
            "ip_type": ip_type,
        }

        return ParsedEntry(
            ip=ip_raw,
            user=user,
            timestamp=timestamp,
            raw_line=stripped,
            metadata=metadata,
        )

    # ── Internal helpers ──────────────────────────────────────

    def _classify_ip(self, ip_str: str) -> str:
        """Classify an IP address string.

        Returns:
            'ipv4', 'ipv6', or 'invalid'.
        """
        try:
            addr = ipaddress.ip_address(ip_str)
            return "ipv4" if isinstance(addr, ipaddress.IPv4Address) else "ipv6"
        except ValueError:
            return "invalid"

    def _extract_timestamp(self, line: str) -> datetime:
        """Extract the syslog timestamp from a log line.

        Falls back to the current UTC time if parsing fails.

        Args:
            line: The full log line.

        Returns:
            A timezone-aware datetime.
        """
        match = self.TIMESTAMP_PATTERN.search(line)
        if not match:
            logger.debug("No timestamp found in line, using current time")
            return datetime.now(timezone.utc)

        ts_str = match.group(1)
        try:
            # Syslog timestamps don't include year — assume current year
            year = datetime.now().year
            dt = datetime.strptime(f"{year} {ts_str}", "%Y %b %d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.debug("Failed to parse timestamp %r, using current time", ts_str)
            return datetime.now(timezone.utc)
