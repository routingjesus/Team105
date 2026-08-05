# Trimble Maps Single Search API (geocoding provider for SPEC-017)

**Official docs:** https://developer.trimblemaps.com/restful-apis/location/single-search/single-search-api/

## Base URL

```
https://singlesearch.alk.com/{region}/api/{endpoint}
```

| Env var | Default | Purpose |
|---------|---------|---------|
| `TRIMBLE_SINGLESEARCH_REGION` | `na` | Region segment (`na`, `ww`, `eu`, etc.) — must match API key license |
| `TRIMBLE_MAPS_API_KEY` | *(required)* | API key; send via `Authorization` header (preferred) or `authToken` query param |

## Geocoding call (forward)

**Endpoint:** `GET /search`

**Wizard → provider mapping:** concatenate depot/stop fields into a single
query string (comma-separated performs best per Trimble docs):

```
{address}, {city}, {state} {zip}
```

**Recommended query parameters:**

| Parameter | Value |
|-----------|-------|
| `query` | URL-encoded address string (required) |
| `maxResults` | `1` (highest-confidence match only for v1) |
| `countries` | `US` |
| `states` | Wizard state abbreviation (e.g. `VA`) |
| `excludeResultsFor` | `POI,POIType` (optional — prefer street addresses for depots/stops) |

**Authentication (preferred):**

```
Authorization: <api-key>
```

Alternatively: `?authToken=<api-key>` (avoid logging query strings in production).

## Response shape (relevant fields)

Top-level:

| Field | Meaning |
|-------|---------|
| `Err` | `0` = OK; non-zero = error (see Trimble error code table) |
| `Locations` | Array of matches, ordered by confidence |

Per location:

| Field | Maps to `location_db` |
|-------|----------------------|
| `Address.StreetAddress` | `Address` |
| `Address.City` | `City` |
| `Address.State` | `State` |
| `Address.Zip` | `Zip` |
| `Coords.Lat` | `Latitude` (parse string → float) |
| `Coords.Lon` | `Longitude` (parse string → float) |
| `ShortString` | Display / confirmation text only |

## Backend adapter contract

`backend/services/geocoding.py` normalizes Trimble responses to:

```python
{
  "latitude": float,
  "longitude": float,
  "formatted_address": str | None,  # ShortString
  "provider": "trimble-single-search",
}
```

**Success:** `Err == 0` and `Locations` non-empty → use `Locations[0]`.

**Failure:** `Err != 0`, empty `Locations`, or HTTP error → raise
`GeocodeNotFoundError` surfaced to the wizard as user-facing
"Could not find coordinates for this address".

## Rate limits

- 15,000 requests/hour
- 250 requests/minute

Backend proxy should cache by normalized address key within a session and
apply light rate limiting on the wizard geocode endpoint.

## Tests

Mock `httpx` responses using the sample JSON from Trimble docs (Independence
Way example). Do not call the live API in CI; integration tests use mocks only.
