"""Console alert channel — writes alerts to stdout/stderr.

Used for development and VM deployment where external notification
services (Telegram, Slack) are unavailable or blocked.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict

from src.core.alerting.channel import AlertChannel, SendResult
from src.core.enrichment.base import EnrichedEvent

logger = logging.getLogger(__name__)


class ConsoleChannel(AlertChannel):
    """Writes formatted alerts to the console.

    Config keys:
        use_stderr: If True, write to stderr instead of stdout.
        colorize: If True, add ANSI color codes (default: True for TTY).
    """

    @property
    def name(self) -> str:
        return "console"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Console channel requires no special config — always valid.

        Args:
            config: Arbitrary config dict (ignored).

        Returns:
            Always True.
        """
        return True

    async def send(
        self, event: EnrichedEvent, config: Dict[str, Any]
    ) -> SendResult:
        """Write a formatted alert to the console.

        Args:
            event: The enriched event to display.
            config: Optional config with ``use_stderr`` and ``colorize`` keys.

        Returns:
            SendResult indicating success.
        """
        use_stderr = config.get("use_stderr", False)
        colorize = config.get(
            "colorize", sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False
        )

        geo_str = ""
        if event.geo:
            parts = []
            if event.geo.country_code:
                parts.append(event.geo.country_code)
            if event.geo.city:
                parts.append(event.geo.city)
            geo_str = f" [{', '.join(parts)}]" if parts else ""

        severity_icon = {
            "failed_auth": "🔴",
            "failed_publickey": "🟡",
        }.get(event.event_type, "⚪")

        lines = [
            f"{severity_icon} [{event.service.upper()}] {event.event_type}",
            f"   IP: {event.ip}{geo_str}",
            f"   Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]
        if event.user:
            lines.append(f"   User: {event.user}")

        message = "\n".join(lines)

        output = sys.stderr if use_stderr else sys.stdout
        print(message, file=output, flush=True)

        return SendResult(success=True, message="Logged to console", channel="console")
