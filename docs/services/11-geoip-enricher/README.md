# 11. GeoIPEnricher

**Pattern:** Strategy
**Files:** `src/adapters/geoip/geo_ip.py`
**Tests:** `tests/unit/enrichment/test_geo_ip.py` (8 tests)

---

## Purpose

Adds geographic location data to security events. Converts raw IP addresses into country, city, ASN, and hosting-provider metadata for enriched alerting.

---

## GeoIPEnricher API

```python
from src.adapters.geoip.geo_ip import GeoIPEnricher

# Mock mode (development — no external dependencies)
geoip = GeoIPEnricher(provider="mock")

# MaxMind mode (production — requires GeoLite2 database)
geoip = GeoIPEnricher(provider="maxmind", db_path="/app/geoip/GeoLite2-City.mmdb")

# Enrich an event
enriched = geoip.enrich(event)
```

### Config Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `provider` | `"mock"` | `"mock"` or `"maxmind"` |
| `db_path` | `None` | Path to `GeoLite2-City.mmdb` (maxmind only) |

### Provider Comparison

| Aspect | Mock | MaxMind |
|--------|------|---------|
| External deps | None | `geoip2` library + `.mmdb` file |
| Deterministic | Yes (last-octet based) | Real GeoIP data |
| Use case | Development, CI, testing | Production |
| Graceful degradation | N/A | Falls back to None if DB missing |

---

## GeoLocation Dataclass

```python
@dataclass(frozen=True)
class GeoLocation:
    country_code: Optional[str]    # ISO 3166-1 alpha-2, e.g. "US"
    country_name: Optional[str]    # Full country name
    city: Optional[str]            # City name
    latitude: Optional[float]      # Decimal latitude
    longitude: Optional[float]     # Decimal longitude
    asn: Optional[int]             # Autonomous System Number
    is_hosting: bool               # Whether IP belongs to hosting/cloud
```

---

## Enrichment Contract

- Implements `Enricher` ABC from `src/core/enrichment/base.py`.
- Takes an `EnrichedEvent` and returns a **new** frozen dataclass with `geo` populated (never mutates the input).
- Returns the event unchanged if the IP is missing or the lookup fails.

---

## Mock Provider Details

The mock provider generates deterministic fake data based on the last octet of the IP:

| Last Octet mod 8 | Country | City |
|-------------------|---------|------|
| 0 | US | New York |
| 1 | CN | Beijing |
| 2 | RU | Moscow |
| 3 | DE | Berlin |
| 4 | BR | Sao Paulo |
| 5 | IN | Mumbai |
| 6 | GB | London |
| 7 | JP | Tokyo |

This ensures tests are fully reproducible.

---

## Design Decisions

- **Strategy pattern:** Swap between mock and MaxMind without changing calling code.
- **Immutable enrichment:** Returns a new `EnrichedEvent` rather than mutating, enabling safe concurrent use and easier reasoning.
- **Graceful fallback:** MaxMind provider logs a warning and returns the event unchanged if the database or library is missing.
