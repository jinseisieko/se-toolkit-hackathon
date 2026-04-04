# 14. Enrichment Pipeline (EnrichedEvent + Enricher)

**Pattern:** Strategy + Pipeline
**Files:** `src/core/enrichment/base.py`
**Tests:** Indirectly via `tests/unit/enrichment/test_geo_ip.py`

---

## Purpose

Defines the enriched event data model and the abstract interface for enrichers. Each enricher (GeoIP, threat intel, custom) takes a raw `ParsedEntry`, wraps it in an `EnrichedEvent`, and adds contextual data without mutating the original.

---

## EnrichedEvent

A frozen dataclass representing a parsed log entry with additional context:

| Field | Type | Source |
|-------|------|--------|
| `ip` | `IPv4Address \| IPv6Address` | From `ParsedEntry` |
| `timestamp` | `datetime` | From `ParsedEntry` |
| `service` | `str` | From `ParsedEntry` |
| `event_type` | `str` | From `ParsedEntry` |
| `raw_line` | `str` | From `ParsedEntry` |
| `user` | `Optional[str]` | From `ParsedEntry` |
| `geo` | `Optional[GeoLocation]` | Added by `GeoIPEnricher` |
| `meta` | `Dict[str, Any]` | From `ParsedEntry` |

### Factory Method

```python
enriched = EnrichedEvent.from_parsed_entry(parsed_entry)
# → EnrichedEvent with geo=None
```

---

## Enricher ABC

```python
class Enricher(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def enrich(self, event: EnrichedEvent) -> EnrichedEvent: ...
```

### Contract

- **Never mutate the input.** Always return a new `EnrichedEvent`.
- **Safe to skip.** If the enricher has no data for the event, return it unchanged.
- **Composable.** Multiple enrichers can be chained:

```python
event = EnrichedEvent.from_parsed_entry(entry)
event = geoip_enricher.enrich(event)
event = threat_enricher.enrich(event)  # future
```

---

## GeoLocation

```python
@dataclass(frozen=True)
class GeoLocation:
    country_code: Optional[str]  # "US", "CN", "RU", ...
    country_name: Optional[str]  # "United States", ...
    city: Optional[str]          # "New York", ...
    latitude: Optional[float]
    longitude: Optional[float]
    asn: Optional[int]           # Autonomous System Number
    is_hosting: bool             # Hosting/cloud provider
```

---

## Design Decisions

- **Frozen dataclasses:** All enrichment data structures are immutable (`frozen=True`), preventing accidental modification and making them safe to share across threads.
- **Optional fields:** `geo` is `Optional`, so the enrichment pipeline is fully incremental — you can run with zero enrichers.
- **`from_parsed_entry` factory:** Single entry point for converting raw `ParsedEntry` to `EnrichedEvent`, ensuring consistent initialisation.
