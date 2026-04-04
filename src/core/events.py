"""Event system — Observer pattern implementation.

Core contracts for pub/sub between log detection and action services.
Signatures must NOT be changed without updating all subscribers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecurityEvent:
    """Represents a detected security incident (e.g. brute-force threshold breached).

    Attributes:
        ip: Source IP address of the attacker.
        attempt_count: Number of failed attempts that triggered this event.
        timestamp: When the event was created (UTC).
        log_line: The raw log line that contributed to detection.
        service: Service name, e.g. "ssh", "http".
    """

    ip: str
    attempt_count: int
    timestamp: datetime
    log_line: str
    service: str


class EventBroker:
    """Lightweight pub/sub broker implementing the Observer pattern.

    Subscribers (callables) are invoked synchronously in subscription order
    when an event is published.  Exceptions in a handler are caught,
    logged at ERROR level, and do not prevent delivery to remaining handlers.
    """

    def __init__(self) -> None:
        self._subscribers: List[Callable[[SecurityEvent], None]] = []

    def subscribe(self, handler: Callable[[SecurityEvent], None]) -> None:
        """Register a callable to be invoked for every published event.

        Args:
            handler: A callable accepting a single SecurityEvent argument.
        """
        self._subscribers.append(handler)

    def publish(self, event: SecurityEvent) -> None:
        """Dispatch *event* to all subscribed handlers.

        If a handler raises an exception, the exception is logged and the
        broker continues with the next handler.

        Args:
            event: The SecurityEvent to dispatch.
        """
        for handler in self._subscribers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Error in event handler for %s", event.__class__.__name__
                )
