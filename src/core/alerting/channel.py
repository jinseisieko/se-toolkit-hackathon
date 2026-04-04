"""Alert channel base — Strategy interface for notification delivery."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from src.core.enrichment.base import EnrichedEvent


@dataclass(frozen=True)
class SendResult:
    """Result of sending an alert through a channel.

    Attributes:
        success: Whether the alert was sent successfully.
        message: Human-readable result or error message.
        channel: Name of the channel that was used.
    """

    success: bool
    message: str
    channel: str


class AlertChannel(ABC):
    """Abstract interface for alert notification delivery.

    Concrete implementations send alerts via different channels
    (Telegram, Slack, email, log, webhook).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique channel identifier, e.g. ``telegram``, ``log``."""

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Check that *config* has all required keys and valid values.

        Args:
            config: Channel-specific configuration.

        Returns:
            True if the config is valid, False otherwise.
        """

    @abstractmethod
    async def send(
        self, event: EnrichedEvent, config: Dict[str, Any]
    ) -> SendResult:
        """Send an alert through this channel.

        Args:
            event: The enriched event to alert about.
            config: Channel-specific configuration (tokens, URLs, etc.).

        Returns:
            A SendResult indicating success or failure.
        """
