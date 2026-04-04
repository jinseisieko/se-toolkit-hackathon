"""Unit tests for MetricsCollector.

Covers:
- Record alert and increment counter per service
- Record block and increment counter per strategy
- Record parse error and increment counter per parser+error
- Observe processing time and compute average
- Render Prometheus-format output
- Empty metrics render
- Multiple alerts for same service aggregate correctly
"""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import IPv4Address

from src.core.enrichment.base import EnrichedEvent
from src.core.observability.metrics import MetricsCollector


def _make_event(service: str = "ssh") -> EnrichedEvent:
    return EnrichedEvent(
        ip=IPv4Address("192.0.2.1"),
        timestamp=datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc),
        service=service,
        event_type="failed_auth",
        raw_line="Failed password for root from 192.0.2.1",
        user="root",
    )


class TestMetricsCollectorRecordAlert:
    def test_record_alert_increments_counter(self) -> None:
        metrics = MetricsCollector()
        event = _make_event()

        metrics.record_alert(event)
        rendered = metrics.render()

        assert 'logsentinel_alerts_total{service="ssh"} 1' in rendered

    def test_multiple_alerts_aggregate(self) -> None:
        metrics = MetricsCollector()
        event = _make_event()

        metrics.record_alert(event)
        metrics.record_alert(event)
        metrics.record_alert(event)
        rendered = metrics.render()

        assert 'logsentinel_alerts_total{service="ssh"} 3' in rendered

    def test_different_services_tracked_separately(self) -> None:
        metrics = MetricsCollector()

        metrics.record_alert(_make_event("ssh"))
        metrics.record_alert(_make_event("http"))
        metrics.record_alert(_make_event("ssh"))
        rendered = metrics.render()

        assert 'logsentinel_alerts_total{service="http"} 1' in rendered
        assert 'logsentinel_alerts_total{service="ssh"} 2' in rendered


class TestMetricsCollectorRecordBlock:
    def test_record_block_increments_counter(self) -> None:
        metrics = MetricsCollector()
        metrics.record_block("192.0.2.1", "NoOpStrategy", "test reason")
        rendered = metrics.render()

        assert 'logsentinel_blocks_total{strategy="NoOpStrategy"} 1' in rendered

    def test_multiple_blocks_aggregate(self) -> None:
        metrics = MetricsCollector()
        metrics.record_block("192.0.2.1", "NoOpStrategy", "r1")
        metrics.record_block("10.0.0.1", "NoOpStrategy", "r2")
        rendered = metrics.render()

        assert 'logsentinel_blocks_total{strategy="NoOpStrategy"} 2' in rendered

    def test_different_strategies_tracked_separately(self) -> None:
        metrics = MetricsCollector()
        metrics.record_block("192.0.2.1", "NoOpStrategy", "r1")
        metrics.record_block("10.0.0.1", "UFWStrategy", "r2")
        rendered = metrics.render()

        assert 'logsentinel_blocks_total{strategy="NoOpStrategy"} 1' in rendered
        assert 'logsentinel_blocks_total{strategy="UFWStrategy"} 1' in rendered

    def test_accepts_string_ip(self) -> None:
        metrics = MetricsCollector()
        metrics.record_block("10.99.99.99", "NoOpStrategy", "manual")
        rendered = metrics.render()

        assert 'logsentinel_blocks_total{strategy="NoOpStrategy"} 1' in rendered


class TestMetricsCollectorRecordParseError:
    def test_record_parse_error(self) -> None:
        metrics = MetricsCollector()
        metrics.record_parse_error("ssh_auth", "invalid_ip")
        rendered = metrics.render()

        assert (
            'logsentinel_parse_errors_total{key="ssh_auth:invalid_ip"} 1'
            in rendered
        )

    def test_multiple_errors_aggregate(self) -> None:
        metrics = MetricsCollector()
        metrics.record_parse_error("ssh_auth", "invalid_ip")
        metrics.record_parse_error("ssh_auth", "invalid_ip")
        rendered = metrics.render()

        assert (
            'logsentinel_parse_errors_total{key="ssh_auth:invalid_ip"} 2'
            in rendered
        )

    def test_different_errors_tracked_separately(self) -> None:
        metrics = MetricsCollector()
        metrics.record_parse_error("ssh_auth", "invalid_ip")
        metrics.record_parse_error("ssh_auth", "regex_fail")
        rendered = metrics.render()

        assert (
            'logsentinel_parse_errors_total{key="ssh_auth:invalid_ip"} 1'
            in rendered
        )
        assert (
            'logsentinel_parse_errors_total{key="ssh_auth:regex_fail"} 1'
            in rendered
        )


class TestMetricsCollectorProcessingTime:
    def test_observe_processing_time(self) -> None:
        metrics = MetricsCollector()
        metrics.observe_processing_time("ssh_auth", 0.010)
        rendered = metrics.render()

        expected = (
            'logsentinel_parse_duration_seconds'
            '{parser="ssh_auth",quantile="avg"} 0.010000'
        )
        assert expected in rendered

    def test_average_of_multiple_observations(self) -> None:
        metrics = MetricsCollector()
        metrics.observe_processing_time("ssh_auth", 0.010)
        metrics.observe_processing_time("ssh_auth", 0.020)
        rendered = metrics.render()

        expected = (
            'logsentinel_parse_duration_seconds'
            '{parser="ssh_auth",quantile="avg"} 0.015000'
        )
        assert expected in rendered

    def test_multiple_parsers_tracked_separately(self) -> None:
        metrics = MetricsCollector()
        metrics.observe_processing_time("ssh_auth", 0.010)
        metrics.observe_processing_time("nginx_access", 0.005)
        rendered = metrics.render()

        expected_ssh = (
            'logsentinel_parse_duration_seconds'
            '{parser="ssh_auth",quantile="avg"} 0.010000'
        )
        expected_nginx = (
            'logsentinel_parse_duration_seconds'
            '{parser="nginx_access",quantile="avg"} 0.005000'
        )
        assert expected_nginx in rendered
        assert expected_ssh in rendered


class TestMetricsCollectorRender:
    def test_empty_metrics_render(self) -> None:
        metrics = MetricsCollector()
        rendered = metrics.render()

        # Should still produce valid Prometheus headers
        assert "# HELP logsentinel_alerts_total" in rendered
        assert "# TYPE logsentinel_alerts_total counter" in rendered
        assert "# HELP logsentinel_blocks_total" in rendered
        assert "# TYPE logsentinel_blocks_total counter" in rendered

    def test_full_render(self) -> None:
        metrics = MetricsCollector()

        metrics.record_alert(_make_event("ssh"))
        metrics.record_block("1.2.3.4", "NoOpStrategy", "test")
        metrics.record_parse_error("ssh_auth", "bad_line")
        metrics.observe_processing_time("ssh_auth", 0.005)
        rendered = metrics.render()

        assert 'logsentinel_alerts_total{service="ssh"} 1' in rendered
        assert 'logsentinel_blocks_total{strategy="NoOpStrategy"} 1' in rendered
        assert (
            'logsentinel_parse_errors_total{key="ssh_auth:bad_line"} 1'
            in rendered
        )
        assert (
            'logsentinel_parse_duration_seconds{parser="ssh_auth",quantile="avg"} 0.005000'
            in rendered
        )
