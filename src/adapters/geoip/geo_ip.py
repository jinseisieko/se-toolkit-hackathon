"""GeoIP enricher — adds geographic context to events.

Supports a ``mock`` provider for test mode (no external DB required)
and a ``maxmind`` provider for production (requires the GeoIP2 library
and a MaxMind database file).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import Optional

from src.core.enrichment.base import EnrichedEvent, Enricher, GeoLocation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeoIPEnricher(Enricher):
    """Enrich events with geographic location data.

    Args:
        provider: ``mock`` for test mode (deterministic fake data)
            or ``maxmind`` for production (requires GeoIP2 database).
        db_path: Path to the MaxMind GeoLite2-City.mmdb file.
            Only used when ``provider`` is ``maxmind``.
    """

    provider: str = "mock"
    db_path: Optional[str] = None

    @property
    def name(self) -> str:
        return "geo_ip"

    def enrich(self, event: EnrichedEvent) -> EnrichedEvent:
        """Add GeoIP data to *event* if a valid IP is present.

        If the provider is ``maxmind`` but the database file is missing,
        logs a warning and returns the event unchanged.

        Args:
            event: The event to enrich.

        Returns:
            A new EnrichedEvent with ``geo`` populated (or unchanged
            if enrichment fails).
        """
        geo: Optional[GeoLocation]
        if self.provider == "mock":
            geo = self._mock_lookup(str(event.ip))
        elif self.provider == "maxmind":
            geo = self._maxmind_lookup(event.ip)
        else:
            logger.warning("Unknown GeoIP provider: %s", self.provider)
            return event

        if geo is None:
            logger.debug("No GeoIP data for %s", event.ip)
            return event

        # Return a new frozen dataclass with geo populated
        return EnrichedEvent(
            ip=event.ip,
            timestamp=event.timestamp,
            service=event.service,
            event_type=event.event_type,
            raw_line=event.raw_line,
            user=event.user,
            geo=geo,
            meta=event.meta,
        )

    def _mock_lookup(self, ip_str: str) -> GeoLocation:
        """Return deterministic fake GeoIP data for testing.

        The mock provider always returns the same values based on
        the last octet of the IP, so tests are reproducible.
        """
        parts = ip_str.split(".")
        last_octet = int(parts[-1]) if len(parts) == 4 else 0

        # Deterministic mapping for test reproducibility
        countries = ["US", "CN", "RU", "DE", "BR", "IN", "GB", "JP"]
        cities = [
            "New York", "Beijing", "Moscow", "Berlin",
            "Sao Paulo", "Mumbai", "London", "Tokyo",
        ]
        idx = last_octet % len(countries)

        return GeoLocation(
            country_code=countries[idx],
            country_name=countries[idx],
            city=cities[idx],
            latitude=40.0 + (last_octet * 0.1),
            longitude=-74.0 + (last_octet * 0.1),
            asn=last_octet * 100 + 1,
            is_hosting=(last_octet % 2 == 0),
        )

    def _maxmind_lookup(
        self, ip: IPv4Address | IPv6Address
    ) -> Optional[GeoLocation]:
        """Look up IP in MaxMind GeoLite2 database.

        Falls back to None if the database is missing or the lookup fails.

        Args:
            ip: The IP address to look up.

        Returns:
            GeoLocation if found, None otherwise.
        """
        if not self.db_path:
            logger.warning(
                "MaxMind provider configured but no db_path set"
            )
            return None

        try:
            import geoip2.database  # type: ignore[import-not-found]

            reader = geoip2.database.Reader(self.db_path)
            response = reader.city(str(ip))

            country = response.country
            city_data = response.city
            location = response.location

            return GeoLocation(
                country_code=country.iso_code,
                country_name=country.name,
                city=city_data.name,
                latitude=location.latitude,
                longitude=location.longitude,
                asn=None,  # Requires GeoIP2-ASN database
                is_hosting=False,
            )
        except ImportError:
            logger.warning(
                "geoip2 library not installed — GeoIP enrichment disabled"
            )
            return None
        except FileNotFoundError:
            logger.warning(
                "MaxMind database not found at %s — GeoIP enrichment disabled",
                self.db_path,
            )
            return None
        except Exception as exc:
            logger.debug(
                "MaxMind lookup failed for %s: %s", ip, exc
            )
            return None
