# 13. Observability (MetricsCollector)

**Pattern:** Collector
**Files:** `src/core/observability/metrics.py`
**Tests:** `tests/unit/observability/test_metrics.py` (stubbed)

---

## Purpose

Lightweight, dependency-free metrics collector that exposes operational metrics in Prometheus plain-text format. Tracks alert counts, block counts, parse errors, and processing latency — all without requiring the Prometheus client library.

---

## MetricsCollector API

```python
from src.core.observability.metrics import MetricsCollector

metrics = MetricsCollector()

# Record an alert event
metrics.record_alert(enriched_event, channel="console")

# Record an IP block
metrics.record_block("192.0.2.1", "NoOpStrategy", "SSH brute-force: 5 attempts")

# Record a parsing error
metrics.record_parse_error("ssh_auth", "invalid_ip")

# Record processing time
metrics.observe_processing_time("ssh_auth", 0.003)

# Export in Prometheus format
print(metrics.render())
```

---

## Exposed Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `logsentinel_alerts_total` | Counter | `service` | Total security alerts per service |
| `logsentinel_blocks_total` | Counter | `strategy` | Total IPs blocked per strategy |
| `logsentinel_parse_errors_total` | Counter | `key` | Parse failures per parser+error_type |
| `logsentinel_parse_duration_seconds` | Summary | `parser`, `quantile` | Average processing time per parser |

---

## Prometheus Output Example

```
# HELP logsentinel_alerts_total Total alerts by service
# TYPE logsentinel_alerts_total counter
logsentinel_alerts_total{service="ssh"} 3
# HELP logsentinel_blocks_total Total IP blocks by strategy
# TYPE logsentinel_blocks_total counter
logsentinel_blocks_total{strategy="NoOpStrategy"} 2
# HELP logsentinel_parse_duration_seconds Processing time per parser
# TYPE logsentinel_parse_duration_seconds summary
logsentinel_parse_duration_seconds{parser="ssh_auth",quantile="avg"} 0.005155
```

---

## Integration with Flask

The worker mounts a `/metrics` endpoint on the Flask app:

```python
@app.route("/metrics")
def metrics_endpoint():
    from flask import Response
    return Response(metrics.render(), mimetype="text/plain")
```

Scrape this endpoint with Prometheus or check manually via `curl`.

---

## Design Decisions

- **No Prometheus client dependency:** Uses plain in-memory dicts and renders Prometheus-compatible text directly. This avoids pulling in the `prometheus-client` package while remaining fully compatible with Prometheus scraping.
- **Per-parser latency tracking:** `observe_processing_time()` records individual observations and computes averages. Percentile support can be added later by sorting the observation list.
- **Thread-safe enough for single-worker:** No explicit locking — the worker runs in a single process, so dict mutations are safe. Multi-process deployments should add a lock or switch to `prometheus-client`.
