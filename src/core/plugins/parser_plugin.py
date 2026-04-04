"""Log parser plugin system — Strategy pattern for log sources.

Defines the abstract interface that all log source plugins must implement,
along with the core dataclasses used throughout the parsing pipeline.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from ipaddress import IPv4Address
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Severity levels for detection rules."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DetectionRule:
    """A pattern + threshold that defines a detectable security event.

    Attributes:
        name: Human-readable rule identifier, e.g. ``ssh_brute_force``.
        pattern: Compiled regex to match against log lines.
        severity: How serious a match is considered.
        threshold: Number of matches within the window to trigger.
        window_seconds: Sliding window width in seconds.
    """

    name: str
    pattern: re.Pattern[str]
    severity: Severity
    threshold: int
    window_seconds: int


@dataclass(frozen=True)
class ParsedEntry:
    """Normalized output from any log parser plugin.

    Attributes:
        ip: Source IPv4 address of the event.
        timestamp: When the event occurred (UTC).
        service: The service that generated the event, e.g. ``ssh``, ``nginx``.
        user: Targeted username if available.
        event_type: Categorical description, e.g. ``failed_auth``, ``path_traversal``.
        raw_line: The original log line text.
        meta: Extensible plugin-specific metadata.
    """

    ip: IPv4Address
    timestamp: datetime
    service: str
    event_type: str
    raw_line: str
    user: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class LogParserPlugin(ABC):
    """Abstract interface for log source plugins.

    Concrete implementations parse a specific log format (SSH auth,
    Nginx access, etc.) and emit normalised ``ParsedEntry`` objects.

    Subclasses must implement all abstract properties and methods.
    The optional ``__init__`` accepts a config dict injected by the
    ``ParserRegistry`` factory.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialise the plugin with optional configuration.

        Args:
            config: Arbitrary key-value configuration from the registry.
                Subclasses should validate and store what they need.
        """
        self._config = config or {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier, e.g. ``ssh_auth``, ``nginx_access``."""

    @property
    @abstractmethod
    def default_log_path(self) -> str:
        """Default host path to monitor (used in config examples)."""

    @abstractmethod
    def parse_line(self, line: str) -> Optional[ParsedEntry]:
        """Parse a single log line.

        Args:
            line: Raw log line text.

        Returns:
            A ``ParsedEntry`` if the line matches a known pattern,
            or ``None`` if the line should be ignored.
        """

    @abstractmethod
    def get_indicators(self) -> List[DetectionRule]:
        """Return detection rules this plugin supports.

        Returns:
            A list of ``DetectionRule`` instances describing the patterns
            and thresholds this plugin can detect.
        """


class PluginAlreadyRegisteredError(Exception):
    """Raised when a plugin is registered twice under the same name."""


class PluginInstantiationError(Exception):
    """Raised when a plugin fails to initialise with the given config."""
