"""Metrics collector — lightweight Prometheus-compatible metrics.

Provides counters and histograms for key operational signals.
Exports metrics in plain-text Prometheus format via ``render()``.
"""

from __future__ import annotations

import logging
import time
from ipaddress import IPv4Address
from typing import Dict, Optional

from src.core.enrichment.base import EnrichedEvent

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and exposes operational metrics in Prometheus format.

    Tracks:
        - Total alerts by service
        - Total blocks by strategy
        - Parse errors by parser name
        - Processing time per parser
    """

    def __init__(self) -> None:
        self._alert_counts: Dict[str, int] = {}
        self._block_counts: Dict[str, int] = {}
        self._parse_errors: Dict[str, int] = {}
        self._processing_times: Dict[str, list[float]] = {}

    def record_alert(self, event: EnrichedEvent, channel: str = "") -> None:
        """Increment alert counter for the event's service.

        Args:
            event: The enriched alert event.
            channel: The channel that handled the alert.
        """
        key = event.service
        self._alert_counts[key] = self._alert_counts.get(key, 0) + 1
        logger.info(
            "Alert recorded: service=%s channel=%s ip=%s",
            event.service, channel, event.ip,
        )

    def record_block(self, ip: IPv4Address, strategy: str, reason: str) -> None:
        """Increment block counter for the given strategy.

        Args:
            ip: The blocked IP address.
            strategy: The firewall strategy used (e.g. ``ufw``, ``noop``).
            reason: Human-readable block reason.
        """
        self._block_counts[strategy] = self._block_counts.get(strategy, 0) + 1
        logger.info(
            "Block recorded: ip=%s strategy=%s reason=%s",
            ip, strategy, reason,
        )

    def record_parse_error(self, parser: str, error_type: str) -> None:
        """Increment parse error counter for the given parser.

        Args:
            parser: The parser name (e.g. ``ssh_auth``).
            error_type: Category of the error (e.g. ``invalid_ip``, ``regex_fail``).
        """
        key = f"{parser}:{error_type}"
        self._parse_errors[key] = self._parse_errors.get(key, 0) + 1

    def observe_processing_time(self, parser: str, duration_seconds: float) -> None:
        """Record a processing time observation for a parser.

        Args:
            parser: The parser name.
            duration_seconds: How long parsing took in seconds.
        """
        if parser not in self._processing_times:
            self._processing_times[parser] = []
        self._processing_times[parser].append(duration_seconds)

    def render(self) -> str:
        """Render all metrics in Prometheus plain-text format.

        Returns:
            A string with all metrics, one per line, ready for
            ``/metrics`` HTTP endpoint.
        """
        lines: list[str] = []
        lines.append("# HELP logsentinel_alerts_total Total alerts by service")
        lines.append("# TYPE logsentinel_alerts_total counter")
        for svc, count in sorted(self._alert_counts.items()):
            lines.append(f'logsentinel_alerts_total{{service="{svc}"}} {count}')

        lines.append("# HELP logsentinel_blocks_total Total IP blocks by strategy")
        lines.append("# TYPE logsentinel_blocks_total counter")
        for strat, count in sorted(self._block_counts.items()):
            lines.append(f'logsentinel_blocks_total{{strategy="{strat}"}} {count}')

        lines.append("# HELP logsentinel_parse_errors_total Total parse errors")
        lines.append("# TYPE logsentinel_parse_errors_total counter")
        for key, count in sorted(self._parse_errors.items()):
            lines.append(f'logsentinel_parse_errors_total{{key="{key}"}} {count}')

        lines.append("# HELP logsentinel_parse_duration_seconds Processing time per parser")
        lines.append("# TYPE logsentinel_parse_duration_seconds summary")
        for parser, times in sorted(self._processing_times.items()):
            if times:
                avg = sum(times) / len(times)
                lines.append(
                    f'logsentinel_parse_duration_seconds{{parser="{parser}",quantile="avg"}} {avg:.6f}'
                )

        lines.append("")
        return "\n".join(lines)
