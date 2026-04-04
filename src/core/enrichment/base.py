"""Enrichment base classes — Strategy interface for event enrichment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any, Dict, Optional

from src.core.plugins.parser_plugin import ParsedEntry


@dataclass(frozen=True)
class GeoLocation:
    """Geographic information for an IP address.

    Attributes:
        country_code: ISO 3166-1 alpha-2 code, e.g. ``US``.
        country_name: Full country name.
        city: City name.
        latitude: Decimal latitude.
        longitude: Decimal longitude.
        asn: Autonomous System Number.
        is_hosting: Whether the IP belongs to a hosting/cloud provider.
    """

    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    asn: Optional[int] = None
    is_hosting: bool = False


@dataclass(frozen=True)
class ThreatInfo:
    """Threat intelligence data for an IP address.

    Attributes:
        is_known_attacker: Whether the IP is on known attacker lists.
        is_anonymous_proxy: Whether the IP is an anonymous proxy.
        is_tor_exit_node: Whether the IP is a known Tor exit node.
        risk_score: Risk score from 0 (clean) to 100 (malicious).
        sources: List of threat intelligence sources consulted.
    """

    is_known_attacker: bool = False
    is_anonymous_proxy: bool = False
    is_tor_exit_node: bool = False
    risk_score: int = 0
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EnrichedEvent:
    """ParsedEntry enriched with contextual data.

    Attributes:
        ip: Source IP address (from ParsedEntry).
        timestamp: When the event occurred (UTC).
        service: The originating service.
        event_type: Categorical event description.
        raw_line: Original log line.
        user: Targeted username.
        geo: Geographic location data (None if not enriched).
        threat_intel: Threat intelligence data (None if not enriched).
        meta: Original metadata from the parser.
        custom: Additional enrichment data from custom enrichers.
    """

    ip: IPv4Address | IPv6Address
    timestamp: datetime
    service: str
    event_type: str
    raw_line: str
    user: Optional[str] = None
    geo: Optional[GeoLocation] = None
    threat_intel: Optional[ThreatInfo] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    custom: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_parsed_entry(cls, entry: ParsedEntry) -> "EnrichedEvent":
        """Create an EnrichedEvent from a raw ParsedEntry.

        Args:
            entry: The parsed log entry to convert.

        Returns:
            A new EnrichedEvent with geo/threat_intel set to None.
        """
        return cls(
            ip=entry.ip,
            timestamp=entry.timestamp,
            service=entry.service,
            event_type=entry.event_type,
            raw_line=entry.raw_line,
            user=entry.user,
            meta=dict(entry.meta),
        )


class Enricher(ABC):
    """Strategy interface for event enrichment.

    Concrete enrichers add contextual data (geo-location, threat intel,
    etc.) to parsed events.  Each enricher is independent and can be
    composed into a pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique enricher identifier, e.g. ``geo_ip``, ``threat_intel``."""

    @abstractmethod
    def enrich(self, event: EnrichedEvent) -> EnrichedEvent:
        """Add contextual data to *event*; never mutate the input.

        Args:
            event: The event to enrich (already converted to EnrichedEvent).

        Returns:
            A new EnrichedEvent with additional data fields populated.
        """
