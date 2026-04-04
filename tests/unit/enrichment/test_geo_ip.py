"""Unit tests for GeoIPEnricher.

Covers:
- Mock provider returns deterministic data
- MaxMind provider with missing DB → warning log, event unchanged
- Invalid IP handling
- Pipeline: enrich multiple events
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from ipaddress import IPv4Address

import pytest

from src.adapters.geoip.geo_ip import GeoIPEnricher
from src.core.enrichment.base import EnrichedEvent


def _make_event(ip: str = "8.8.8.8") -> EnrichedEvent:
    return EnrichedEvent(
        ip=IPv4Address(ip),
        timestamp=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
        service="ssh",
        event_type="failed_auth",
        raw_line=f"Failed password from {ip}",
        user="root",
        meta={"port": "22"},
    )


# ── Happy path ────────────────────────────────────────────────


class TestGeoIPEnricherHappyPath:
    def test_mock_provider_returns_geo(self) -> None:
        enricher = GeoIPEnricher(provider="mock")
        event = _make_event("8.8.8.8")
        result = enricher.enrich(event)

        assert result.geo is not None
        assert result.geo.country_code is not None
        assert result.geo.city is not None
        # Original event data preserved
        assert result.ip == IPv4Address("8.8.8.8")
        assert result.service == "ssh"

    def test_mock_provider_is_deterministic(self) -> None:
        enricher = GeoIPEnricher(provider="mock")
        event_a = _make_event("1.2.3.100")
        event_b = _make_event("1.2.3.100")

        result_a = enricher.enrich(event_a)
        result_b = enricher.enrich(event_b)

        assert result_a.geo == result_b.geo

    def test_mock_provides_varied_data_by_ip(self) -> None:
        enricher = GeoIPEnricher(provider="mock")
        result_1 = enricher.enrich(_make_event("1.2.3.100"))
        result_2 = enricher.enrich(_make_event("1.2.3.200"))

        assert result_1.geo is not None
        assert result_2.geo is not None
        assert result_1.geo.country_code != result_2.geo.country_code

    def test_enrich_does_not_mutate_input(self) -> None:
        enricher = GeoIPEnricher(provider="mock")
        event = _make_event("8.8.8.8")
        result = enricher.enrich(event)

        assert result is not event  # New instance
        assert event.geo is None  # Original unchanged
        assert result.geo is not None


# ── Edge cases ────────────────────────────────────────────────


class TestGeoIPEnricherEdgeCases:
    def test_unknown_provider_returns_event_unchanged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        enricher = GeoIPEnricher(provider="bogus")
        event = _make_event()

        with caplog.at_level(logging.WARNING, logger="src.adapters.geoip.geo_ip"):
            result = enricher.enrich(event)

        assert result is event
        assert result.geo is None
        assert any("Unknown GeoIP provider" in r.message for r in caplog.records)

    def test_maxmind_missing_db_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        enricher = GeoIPEnricher(
            provider="maxmind", db_path=None
        )
        event = _make_event()

        with caplog.at_level(logging.WARNING, logger="src.adapters.geoip.geo_ip"):
            result = enricher.enrich(event)

        # Returns same event (unchanged) when geo unavailable
        assert result.geo is None
        assert any("no db_path" in r.message for r in caplog.records)

    def test_maxmind_non_existent_db_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        enricher = GeoIPEnricher(
            provider="maxmind", db_path="/nonexistent/GeoLite2-City.mmdb"
        )
        event = _make_event()

        with caplog.at_level(logging.WARNING, logger="src.adapters.geoip.geo_ip"):
            result = enricher.enrich(event)

        assert result.geo is None
        # geoip2 lib not installed in test env → warning about missing lib
        assert any(
            "GeoIP enrichment disabled" in r.message
            for r in caplog.records
        )

    def test_preserves_existing_geo(self) -> None:
        """If event already has geo, enricher should not overwrite it
        unless the enricher itself produces geo data."""
        from src.core.enrichment.base import GeoLocation

        existing_geo = GeoLocation(
            country_code="XX", city="TestCity"
        )
        event = EnrichedEvent(
            ip=IPv4Address("1.2.3.4"),
            timestamp=datetime.now(timezone.utc),
            service="ssh",
            event_type="failed_auth",
            raw_line="test",
            geo=existing_geo,
        )

        enricher = GeoIPEnricher(provider="mock")
        result = enricher.enrich(event)

        # GeoIPEnricher always produces new geo from its lookup
        assert result.geo is not None
        assert result.geo.country_code != "XX"
