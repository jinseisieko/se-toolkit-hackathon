"""Threshold detector — aggregates per-IP attempts and fires SecurityEvents.

Strategy: sliding time window.  Each call to ``record_attempt`` appends a
timestamp to a per-IP deque.  Stale entries (older than *window_seconds*)
are pruned.  When the remaining count reaches *threshold*, a
``SecurityEvent`` is published via the registered ``EventBroker`` and the
counter for that IP is reset.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Deque, Dict, Optional

from src.core.events import EventBroker, SecurityEvent

logger = logging.getLogger(__name__)


class ThresholdDetector:
    """Detect brute-force patterns by counting attempts per IP within a window.

    Args:
        threshold: Number of attempts within the window to trigger an event.
        window_seconds: Width of the sliding window in seconds.
    """

    def __init__(self, threshold: int, window_seconds: int = 300) -> None:
        self.threshold = threshold
        self.window_seconds = window_seconds
        self._attempts: Dict[str, Deque[datetime]] = defaultdict(deque)
        self._broker: Optional[EventBroker] = None

    def register_broker(self, broker: EventBroker) -> None:
        """Attach the event broker so this detector can publish events.

        Args:
            broker: The EventBroker instance to publish SecurityEvents to.
        """
        self._broker = broker

    def record_attempt(self, ip: str, timestamp: datetime) -> None:
        """Record a single failed login attempt for *ip* at *timestamp*.

        If the number of attempts from this IP within the sliding window
        reaches ``self.threshold``, a ``SecurityEvent`` is published and the
        counter for this IP is reset.

        Args:
            ip: Source IP of the failed attempt.
            timestamp: When the attempt occurred (should be timezone-aware).
        """
        self._prune(ip, timestamp)
        self._attempts[ip].append(timestamp)

        if len(self._attempts[ip]) >= self.threshold:
            count = len(self._attempts[ip])
            logger.info(
                "Threshold breached for %s: %d attempts in %ds window",
                ip,
                count,
                self.window_seconds,
            )
            if self._broker is not None:
                self._broker.publish(
                    SecurityEvent(
                        ip=ip,
                        attempt_count=count,
                        timestamp=timestamp,
                        log_line="",
                        service="ssh",
                    )
                )
            # Reset counter after firing
            self._attempts[ip].clear()
        else:
            logger.debug(
                "Attempt %d/%d for %s (window: %ds)",
                len(self._attempts[ip]),
                self.threshold,
                ip,
                self.window_seconds,
            )

    # ── Internal helpers ──────────────────────────────────────

    def _prune(self, ip: str, current: datetime) -> None:
        """Remove timestamps older than the window relative to *current*."""
        cutoff = current.timestamp() - self.window_seconds
        queue = self._attempts[ip]
        while queue and queue[0].timestamp() < cutoff:
            queue.popleft()
