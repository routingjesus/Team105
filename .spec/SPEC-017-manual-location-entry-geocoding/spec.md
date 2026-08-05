---
id: SPEC-017
title: "Manual Location Entry with Geocoding"
category: feature
owner: Tyler Corr
authored_by: augmented
---

## Problem statement

The Dataset Creation Wizard builds DirectRoute demo datasets from a bundled,
read-only `location_db.xlsx` (~22k pre-geocoded rows). Today:

- **Depots** are free-text address fields that must already exist in
  `location_db` for coordinate resolution; unknown addresses fail stop
  generation with `DepotCoordinateError`.
- **Stops** are sampled from the static pool by radius or state — users cannot
  add specific customer locations that are not already in the database.

Operators preparing demos for unfamiliar territories need to **manually add
depots and stops through the wizard**, assign coordinates either by calling
the company's geocoding service or by entering latitude/longitude directly, and
**persist those records to `location_db`** so they participate in depot
resolution, radius filtering, and stop output on subsequent generations.

## Acceptance criteria

1. **Given** a user is on the Route details step and enters a depot address not
   present in `location_db`, **when** they click **Look up coordinates** and
   the geocoding service returns a match, **then** the wizard displays the
   resolved latitude and longitude and marks the depot as geocoded before
   generation proceeds.
2. **Given** geocoding fails or is unavailable, **when** the user enters valid
   WGS84 latitude (−90…90) and longitude (−180…180) manually, **then** the
   wizard accepts the depot and generation proceeds without requiring a
   `location_db` address match.
3. **Given** a depot or stop has valid coordinates (from geocoding or manual
   entry), **when** the user confirms **Add to location database**, **then**
   a new row is appended to `backend/data/location_db.xlsx` with the full
   canonical column set (`Name`, `ID1`, `Contact`, `Phone`, `ID2`, `ID3`,
   `Address`, `Address2`, `City`, `State`, `Zip`, `Latitude`, `Longitude`),
   synthetic `Name`/`ID1` values following the `prepare_location_db.py`
   numbering scheme, and trimmed (non-padded) text fields.
4. **Given** a depot was just persisted (or already exists in `location_db`),
   **when** the user generates a dataset with radius-based stop selection,
   **then** stop candidates are drawn using that depot's coordinates and the
   generation completes without `DepotCoordinateError`.
5. **Given** a user is on the Stop details step, **when** they add one or more
   manual stop locations (address fields plus geocode or manual coordinates)
   and confirm **Add to location database**, **then** those stops are persisted
   to `location_db` and are eligible as stop candidates in the current and
   future generations (subject to radius/state selection rules).
6. **Given** a user attempts to add a location whose normalized address key
   `(address, city, state, zip)` already exists in `location_db` or the
   current wizard session, **when** they confirm the add, **then** the UI
   warns of the duplicate and offers to reuse the existing record instead of
   creating a second row.
7. **Given** a persisted manual stop with coordinates, **when** stop
   generation selects that row and writes `stops.xlsx`, **then** the output
   `Latitude` and `Longitude` columns equal the stored values to six decimal
   places (same fidelity contract as SPEC-005).
8. **Given** the geocoding API key is configured only in server environment
   variables, **when** the wizard triggers geocoding, **then** no API key or
   raw provider credentials appear in browser network responses or client-side
   bundles.
9. **Given** two concurrent add-location requests, **when** both attempt to
   write `location_db.xlsx`, **then** neither request corrupts the file (file
   lock + atomic replace) and both rows are retained or one receives a clear
   conflict error.
10. **Given** a depot address cannot be resolved from `location_db` and the
    user has not yet geocoded or entered coordinates, **when** stop generation
    is attempted, **then** the API returns HTTP 422 with the user-facing
    message **"Depot could not be geocoded"** (not the raw
    `DepotCoordinateError` string).
11. **Given** a location was geocoded manually (`geoSource: manual`), **when**
    the user saves or re-triggers generation, **then** the wizard does not
    overwrite those coordinates with a new geocoding attempt.
12. **Given** the new location-entry and geocoding flows, **when** the
    Vitest wizard tests and pytest backend tests run, **then** all existing
    tests pass and new tests cover geocode success, geocode failure with manual
    fallback, persistence round-trip (write → reload → match), and coordinate
    passthrough to stop output.

## Research

Research gate completed 2026-08-05 (learnings-curator, repo-analyst,
docs-researcher, prior-art-researcher).

- **SPEC-017 is the first runtime mutation of `location_db`.** Today the file
  is loaded read-only on each stop request (`spatial.load_location_db`); the
  only writers are offline scripts (`prepare_location_db.py`,
  `fixtures/stop/make_sample_location_db.py`). SPEC-003 explicitly scoped out
  "static location database management"; this spec deliberately expands that
  boundary. (repo-analyst, learnings-curator)

- **Depot coordinate resolution is DB-match-only today** — exact address, then
  city/state/zip fallback — with no external geocoding (`spatial.py` header and
  SPEC-002 research). Manual entry must either pre-insert rows into
  `location_db` or extend `resolve_depot_coordinates` to accept inline
  coordinates from the request. Pre-insert + existing lookup is the smaller
  diff and keeps one resolution path. (repo-analyst, learnings-curator)

- **Persisted rows must follow the existing data-governance model:** real
  geography is fine; `Name` and `ID1` must be synthetic (`Customer {n:05d}` /
  `{n:06d}`) to avoid shipping proprietary identities. Empty `Contact`/`Phone`/
  `ID2`/`ID3`/`Address2` are acceptable defaults. (learnings-curator, SPEC-002
  meta)

- **Write clean, load-normalized:** legacy rows may have whitespace-padded
  strings; `load_location_db` strips on read. New rows should be saved trimmed;
  matching uses casefold on address and city/state/zip. (ledger
  `directroute-file-formats.yaml`, repo-analyst)

- **Coordinate passthrough is a known bug class:** SPEC-005 fixed lat/long
  dropped between filter and row assembly in `stop.py`. Manual stops must be
  verified end-to-end with source-to-output equality assertions, not just
  non-blank checks. (learnings-curator, SPEC-005)

- **Geocoding UX:** industry practice favors an explicit **Look up coordinates**
  button over blur-triggered geocoding (avoids accidental API calls and
  overwrites in-progress edits). Always expose manual lat/long as a fallback;
  block save until coordinates are valid WGS84 — never silently store `(0, 0)`.
  (docs-researcher, prior-art-researcher)

- **Server-side geocoding proxy:** the wizard already calls FastAPI via Next.js
  `rewrites` (`next.config.ts`, `lib/api.ts`). Geocoding should be a new
  `POST /api/locations/geocode` (or company-specific path) on FastAPI with the
  provider key in server env only — no `NEXT_PUBLIC_` prefix. (docs-researcher,
  prior-art-researcher)

- **Excel persistence:** `to_excel` overwrites the whole file; append requires
  read → validate → concat → write. Use a file lock and temp-file + atomic
  rename to avoid corruption under concurrent Uvicorn workers. (docs-researcher)

- **Frontend form patterns:** use `useFieldArray` for add/remove rows and
  `setValue` for async geocode results on nested `latitude`/`longitude` fields
  (avoid `update()` remounts). Mirror backend constraints in
  `lib/wizard-schema.ts` per SPEC-003. (docs-researcher, learnings-curator)

- **Test against real DB quirks:** padded-string matching bugs were invisible in
  `fixtures/stop/sample_location_db.xlsx` alone; persistence round-trip tests
  should exercise reload through `load_location_db` on the written file.
  (learnings-curator)

- **Persistence model (deliberate deviation from prior-art):** industry
  guidance for demo tools favors a session-scoped overlay on an immutable seed
  file. This spec instead persists to `location_db.xlsx` per the product
  requirement — durable rows for repeat demos — with file locking and duplicate
  detection to mitigate shared-host risks. (prior-art-researcher)

- **SPEC-002 "no invented addresses" NFR is superseded** for user-confirmed
  manual entries: invented rows are allowed when explicitly added through this
  flow and persisted with synthetic `Name`/`ID1`. (repo-analyst)

- **Geocoding provider: Trimble Maps Single Search API.** Company geocoding
  uses `GET https://singlesearch.alk.com/{region}/api/search` with a
  comma-separated `query` built from wizard address fields, `maxResults=1`,
  `countries=US`, and the wizard state in `states`. Auth via
  `TRIMBLE_MAPS_API_KEY` (prefer `Authorization` header over `authToken`
  query param). Parse `Locations[0].Coords.Lat/Lon` (strings) and map
  `Address.*` back to `location_db` columns. Full contract in
  `resources/trimble-single-search-api.md`. Rate limits: 250/min, 15k/hr.
  (docs-researcher, product input)

### Resolved assumptions

| Topic | Decision |
|-------|----------|
| Geocoding provider | Trimble Maps Single Search (`region` defaults to `na`) |
| API key storage | `TRIMBLE_MAPS_API_KEY` server env only — never in client or git |
| Multiple matches | v1 uses `maxResults=1` (top confidence); disambiguation UI is follow-up |
| When to persist | On explicit **Add to location database** per row |
| Map preview | Out of scope for v1 — numeric lat/long confirmation only |
| Truck file depot coords | Out of scope (SPEC-001/002); coords matter for stop selection/output |

## Scope boundaries

- **In scope:** Wizard UI for manual depot and stop entry; geocode button;
  manual lat/long override; persist to `location_db.xlsx`; duplicate detection;
  backend geocode proxy; file-lock-safe append.
- **Out of scope:** Mutating or deleting existing seed rows; bulk CSV import;
  interactive map picker; address autocomplete/typeahead; user authentication;
  cross-session wizard state (SPEC-003 P1); populating truck-file
  `Longitude`/`Latitude` columns; changing `DRProject.config` geocoder settings;
  fuzzy address deduplication beyond normalized exact match.
- **Files NOT to modify:** `backend/data/prepare_location_db.py` (offline rebuild
  only), golden DirectRoute template fixtures unless a new column is required,
  unrelated wizard steps (`review.tsx`, `download.tsx`) except summary display
  of added locations.

## User scenarios

- **New territory demo:** A solutions engineer models a depot in Denver that is
  not in the bundled Southeast-heavy seed data. They enter the address, click
  **Look up coordinates**, confirm the result, add it to `location_db`, then
  generate a radius-based dataset with stops near that depot.
- **Geocoder outage:** Geocoding returns no match for a rural address. The
  engineer expands **Enter coordinates manually**, pastes lat/long from a
  map, adds the stop, and completes generation.
- **Repeat demo:** On a second wizard run the same week, the previously added
  depot resolves via normal `location_db` address match without re-entry.

## Non-functional requirements

- Geocoding endpoint rate-limited (per-session or per-IP) to prevent quota
  abuse on shared demo hosts.
- Persistence operations complete within 5 seconds for a single-row append on
  the current ~22k-row file.
- All new text fields pass the existing ASCII-only validation used by truck/
  stop schemas.
- Geocoding errors surfaced to users as plain language (e.g. "Could not find
  coordinates for this address"); technical provider errors logged server-side
  only.

## Implementation guidance

- **Files likely affected:**
  - `backend/services/spatial.py` — optional `append_location_row`, extend
    `resolve_depot_coordinates` if inline coords needed before persist
  - `backend/services/location_store.py` (new) — lock, read, append, atomic
    write; synthetic ID allocation
  - `backend/services/geocoding.py` (new) — Trimble Single Search adapter
    (`resources/trimble-single-search-api.md`)
  - `backend/schemas/location.py` (new) — `LocationEntry`, `GeocodeRequest`,
    `GeocodeResponse`
  - `backend/main.py` — `POST /api/locations/geocode`,
    `POST /api/locations` (append)
  - `components/wizard/truck-questions.tsx` — geocode button, coord fields,
    add-to-db action per depot
  - `components/wizard/stop-questions.tsx` — manual stop entry section
  - `lib/wizard-schema.ts`, `lib/wizard-types.ts`, `lib/build-config.ts`,
    `lib/api.ts`
  - `tests/test_spatial.py`, `tests/test_location_api.py` (new),
    `tests/test_stop_generator.py`
  - `fixtures/stop/` — fixture rows for manual-entry scenarios
- **Files NOT to modify:** `backend/generators/truck.py` (empty coords by
  design), `backend/data/prepare_location_db.py`, unrelated specs' directories
- **Patterns to follow:**
  - Synthetic ID generation from `prepare_location_db.py:33-34`
  - Paired JSON API + Pydantic validation from `backend/main.py` truck/stop
    endpoints
  - Zod ↔ Pydantic mirroring from `lib/wizard-schema.ts`
  - Coordinate output formatting from `backend/generators/stop.py` (six decimal
    places, SPEC-005)
  - `setValue` for geocode results on field-array rows (react-hook-form docs)
  - Track `geoSource: "api" | "manual"` per location row; skip re-geocode when
    manual (prior-art-researcher)
  - Add `filelock` (or equivalent) for concurrent-safe xlsx append
    (docs-researcher)
- **Test expectations:**
  - Unit: geocode adapter mock, append + reload, duplicate key detection,
    `resolve_depot_coordinates` after append
  - API: geocode 200/422, append 201/409, file not corrupted after concurrent
    append (can use threading in test)
  - Integration: manual depot → radius stop gen succeeds; manual stop → selected
    row lat/long in output xlsx matches persisted values
  - Extend `fixtures/stop/make_sample_location_db.py` if needed; also verify
    against a temp copy of the real column shape
