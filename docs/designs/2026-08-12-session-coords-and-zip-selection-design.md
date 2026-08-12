# Session Coords Paste + Zip Stop Selection — Design

- **Date:** 2026-08-12
- **Status:** Approved (brainstorming output)
- **Related:** SPEC-017 (manual location + Trimble geocoding — superseded for
  geocode/persist), SPEC-002 (stop selection radius/state), SPEC-005 (lat/long
  passthrough), SPEC-016 (stops CSV)

## Problem / goal

Recent wizard builds expose three related failures around depot location:

1. The Trimble geocode path for truck/depot addresses is unreliable and blocks
   useful downstream behavior.
2. When depot coordinates cannot be established, **radius** stop selection
   cannot work, but the UI still presents it as available.
3. Manual lat/long entry plus **Save** (persist to `location_db`) errors and
   feels clunky.

Goal: remove external geocoding and DB persist from the wizard; let users
optionally paste Google Maps coordinates; gate radius on real depot coords;
add a separate **zip** stop-selection mode (lists + ranges); keep address
fields; allow blank lat/long in generated files when the user did not paste
coords.

## Chosen approach: contract-aligned incremental (Approach 1)

Alternatives considered and rejected:

- **Client-expanded zips (Approach 2)** — expand ranges in the browser and send
  a flat list. Thinner backend validation, but duplicates parse rules across
  TS/Python and bloats requests for wide ranges.
- **Broader location-entry redesign (Approach 3)** — replace the SPEC-017
  location model with a new abstraction. Cleaner long-term, more churn than
  these bugs require.

### Architecture

One vertical change: wizard UI → shared schema / `build-config` → FastAPI
generators → spatial filters. No new services or third-party geo/ZIP deps.

- **Remove:** Trimble geocode and location-db append (`POST /api/locations/geocode`,
  `POST /api/locations`, `geocoding.py`, `location_store.py` runtime append,
  client helpers, Save/geocode UI, `TRIMBLE_MAPS_API_KEY` from `.env.example`).
  Bundled `location_db.xlsx` remains **read-only** for stop candidates and
  optional depot address match.
- **Location entry:** Shared panel for depots and manual stops — keep
  Address / City / State / Zip; optional Google Maps paste fills lat/lon; no
  Save. Values live in wizard `sessionStorage` only for the run.
- **Stop selection:** Modes `radius | state | zip`. Show **radius** only if at
  least one depot has valid coordinates. Zip mode uses comma-separated values
  and inclusive ranges, normalized to 5-digit strings, filtered with pandas
  like state mode.
- **Generation:** Session manual stops are sent on `StopConfig` and always
  appended after DB candidate thinning (not density-thinned away). Depots and
  manual stops may emit blank lat/long cells. Radius resolves depot coords from
  inline paste first; uses only depots that have resolvable coords.

### Components

| Piece | Change |
|--------|--------|
| `LocationEntryPanel` | Drop geocode + Save. Keep address fields. Add optional coords paste (parse → `latitude`/`longitude`). Remove `geoSource` / `inLocationDb` UX. |
| `truck-questions` / `stop-questions` | Use simplified panel. Stop step: add **zip** radio; hide **radius** when no depot has coords; if radius was selected and becomes unavailable, fall back to **state**. Update manual-stop copy (session-only). |
| `lib/location-utils.ts` | Google decimal paste parser; reuse `hasValidCoordinates` for radius gating. |
| `lib/wizard-schema.ts` + `build-config.ts` | `selectionMode` includes `zip` + `zips` field; mirror backend validators; map `manualStops` into the stop request. |
| `SelectionConfig` / `spatial.py` / `stop.py` | `mode: zip` + `filter_by_zip`; inject session manual stops; allow blank lat/long in row output. |
| `truck.py` (light) | Emit depot lat/long when present; otherwise leave empty (today always empty). |
| API cleanup | Remove location routes/clients/tests/env Trimble vars. Replace `"Depot could not be geocoded"` with a non-geocode message. |

### Data flow

1. User fills address fields; optionally pastes `lat, long`. Parser writes
   numeric `latitude`/`longitude` or leaves them empty. Nothing is written to
   `location_db.xlsx`.
2. Existing wizard `sessionStorage` persists depots + manual stops (including
   optional coords) for the run.
3. Stop step: if any depot has valid coords → radius available; else only
   state / zip. Zip input example: `84101, 67861-67942`.
4. Generate: `buildStopConfig` sends selection payload, depot summaries with
   optional inline coords, and `manual_stops`. Truck generate uses depot
   address (+ optional coords for truck file cells).
5. Backend: load read-only `location_db` → filter by radius/state/zip → thin
   DB candidates to the remaining target budget → **always append** session
   manual stops (blank coords allowed; not subject to density thinning) →
   build XLSX/CSV (empty lat/long cells when missing).

### Coordinate paste rules

Canonical example (Google Maps right-click → copy coordinates):

```text
38.38080520110032, -97.4279212147894
```

- Strip whitespace and optional wrapping parentheses.
- Split on first comma (optionally accept `;`).
- Parse each token with decimal `float`-equivalent; validate WGS84 bounds.
- Out of scope: DMS (`38°22'50.9"N`), geocoders, reverse geocode.
- Lat/long are **optional**. Address fields remain.

### Zip selection rules

- Separate mode from state (radio: radius | state | zip) — not combined.
- Input: comma-separated list plus inclusive ranges (`67861-67942`).
- Flexible parsing: singles, lists, ranges; ZIP+4 truncated to base-5;
  leading-zero pad to 5 characters; compare as strings via pandas `isin`.
- Match means “DB row Zip falls in the expanded set,” not “USPS-active ZIP.”
- No new ZIP library.

### Radius gating

- Show radius iff **at least one** depot has valid coordinates.
- If every depot lacks coords → only state / zip.
- If radius becomes unavailable while selected → switch UI to **state**.
- Backend: if `mode=radius` arrives with no resolvable depot coords → clear 4xx
  (not a geocode-themed message). Radius filtering uses depots that have
  resolvable coords.

### Blank coordinates in output

- Depots in the truck file and manual stops in the stop file are included even
  when lat/long are blank (empty cells).
- Bundled `location_db` candidates that already have coords keep them
  (SPEC-005 parity for DB-sourced rows).
- Density thinning / radius math must skip or exclude rows without numeric
  coords rather than crashing.

### Error handling

- Invalid coords paste → field error; lat/lon unset.
- Invalid zip tokens / inverted ranges / empty parse → validation error on
  zips field before generate.
- Empty filter result → actionable generate error (same spirit as state/radius
  today).
- Removed geocode/persist APIs → no client calls; no duplicate-on-save path.

### Testing

- Parser: Google paste happy path; whitespace/parens; reject DMS/garbage;
  WGS84 bounds.
- Zip parse/expand: singles, lists, ranges, ZIP+4 → base-5, leading zeros,
  invalid tokens.
- `filter_by_zip` against fixture `location_db`.
- UI/schema: radius hidden/shown correctly; zip mode refine; no geocode/Save.
- Session manual stops in output with and without lat/long.
- Regression: state + radius paths; remove/replace Trimble persist tests;
  update assertions where blank session coords are newly allowed.
- Smoke: address-only depots → state/zip only; paste coords → radius works;
  zip range yields expected candidates.

## Out of scope

- New geocoding providers or offline geocoders
- Editing or appending the bundled `location_db.xlsx` at runtime
- USPS validity lookup for ZIP codes
- DMS / non-decimal coordinate formats
- Unrelated wizard step redesign (EQ codes, time windows, downloads, etc.)

## Files likely affected

- `components/wizard/location-entry-panel.tsx`
- `components/wizard/truck-questions.tsx`
- `components/wizard/stop-questions.tsx`
- `components/wizard/review.tsx`
- `lib/location-utils.ts`, `lib/wizard-schema.ts`, `lib/wizard-types.ts`,
  `lib/build-config.ts`, `lib/api.ts`
- `backend/schemas/stop_config.py`, `backend/schemas/location.py` (remove or
  shrink)
- `backend/services/spatial.py`, `backend/services/geocoding.py` (remove),
  `backend/services/location_store.py` (remove runtime append)
- `backend/generators/stop.py`, `backend/generators/truck.py`
- `backend/main.py`
- `.env.example`
- Tests under `tests/`, `lib/*.test.ts`

## Design references

- Brainstorming Q&A (2026-08-12): remove geocode everywhere; keep address +
  optional paste; session-only (no Save); radius if any depot has coords;
  separate zip mode with ranges; blank coords allowed in file output.
