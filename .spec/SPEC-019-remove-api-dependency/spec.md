---
id: SPEC-019
title: "Remove API dependency"
category: feature
owner: Tye Lofts
authored_by: augmented
---

## Problem statement

The Dataset Creation Wizard currently depends on an external Trimble geocoding
API and a runtime **Save** path that appends rows to `location_db.xlsx`
(SPEC-017). In practice:

- Depot geocode often fails, which blocks useful workflows.
- When depots have no coordinates, **radius** stop selection cannot work, but
  the UI still offers it.
- Manual lat/long entry plus **Save** errors and feels unreliable.
- Manual stops entered in the wizard never reach generation unless they were
  persisted to the location database.

Operators need a wizard that does **not** call an external geocode API: they
paste Google Maps coordinates when they have them, leave coords blank when
they do not, pick stops by state or zip (and radius only when at least one
depot has coords), and generate files in a single session without writing to
`location_db.xlsx`.

Design reference:
`docs/designs/2026-08-12-session-coords-and-zip-selection-design.md`

## Acceptance criteria

1. **Given** the wizard location-entry UI for a depot or manual stop, **when**
   the page renders, **then** there is no geocode / "Look up coordinates"
   control and no **Save** / "Add to location database" control.
2. **Given** a user pastes Google Maps coordinates in the form
   `38.38080520110032, -97.4279212147894` (optional whitespace), **when** the
   paste is accepted, **then** the location's latitude and longitude are set to
   those decimal values (WGS84) for the current wizard session.
3. **Given** a user enters Address / City / State / Zip without coordinates,
   **when** they proceed, **then** the wizard accepts the location (coords are
   not required).
4. **Given** every depot lacks valid coordinates, **when** the user is on the
   stop-selection step, **then** the **radius** option is not offered; only
   **state** and **zip** modes are available.
5. **Given** at least one depot has valid coordinates, **when** the user is on
   the stop-selection step, **then** **radius**, **state**, and **zip** modes
   are all available.
6. **Given** stop selection mode is **zip** and the user enters
   `84101, 67861-67942`, **when** stop generation runs, **then** candidates are
   drawn from `location_db` rows whose normalized 5-digit Zip is `84101` or any
   inclusive value from `67861` through `67942`.
7. **Given** a user adds a manual stop in the wizard (with or without
   coordinates) and does not persist anything to disk, **when** stop generation
   completes, **then** that stop appears in the stop file output; if
   coordinates were omitted, Latitude/Longitude cells are empty.
8. **Given** a depot has pasted coordinates, **when** the truck file is
   generated, **then** that depot's Latitude/Longitude cells contain those
   values; if coordinates were omitted, those cells are empty.
9. **Given** session manual stops and a target stop count, **when** generation
   thins DB candidates, **then** session manual stops are still present in the
   output (not removed by density thinning).
10. **Given** the backend no longer exposes location geocode/persist APIs,
    **when** a client calls the former geocode or append endpoints, **then**
    those routes are absent (HTTP 404) and no Trimble API key is required for
    normal wizard generation.
11. **Given** radius mode is requested but no depot has resolvable coordinates,
    **when** stop generation is attempted, **then** the API returns HTTP 422
    with a clear non-geocode error message (not "Depot could not be geocoded").
12. **Given** the Vitest wizard tests and pytest backend tests run, **then**
    existing non-superseded tests pass; new tests cover coords paste parsing,
    zip list/range filtering, radius gating, session manual-stop output with
    blank coords, and removal of geocode/persist client paths.

## Research

Research gate completed 2026-08-12 (learnings-curator, repo-analyst,
docs-researcher, prior-art-researcher).

- **SPEC-019 reverses SPEC-017’s geocode/persist stack.** `LocationEntryPanel`
  still owns Look up / Save, `POST /api/locations/geocode` +
  `POST /api/locations`, Trimble adapter, and `location_store` append. Delete
  that surface (routes → 404, remove clients/tests/env), do not feature-flag.
  Bundled `location_db.xlsx` stays read-only. `(repo-analyst, learnings-curator)`

- **`manualStops` never reach the API today.** Form + `sessionStorage` hold
  them, but `buildStopConfig()` and `StopConfig` have no `manual_stops` field;
  the only current test path persists via `append_location_row` first. Session
  manual stops need a new request field and an **append-after-thinning** path
  in `select_candidates` / generation so they are not removed by
  `thin_to_target`. `(repo-analyst, learnings-curator, prior-art-researcher)`

- **Zip mode is net-new end-to-end.** Extend `selectionMode` /
  `SelectionConfig.mode` with `"zip"`, mirror `parseStates` ↔ `filter_by_state`
  with `parseZips` ↔ `filter_by_zip` (comma lists + inclusive ranges). Normalize
  to 5-digit strings (`astype(str)`, strip ZIP+4, `zfill(5)`) before `isin` —
  same whitespace/padding hygiene as ledger learnings for `location_db` load.
  No ZIP library; no USPS validity. `(repo-analyst, docs-researcher, learnings-curator)`

- **Radius must be UI-gated and API-enforced.** UI always shows radius today
  (default `selectionMode: "radius"`). Hide when no depot passes
  `hasValidCoordinates`; fall back to state if radius becomes unavailable.
  Backend today resolves **every** depot and maps failures to
  `"Depot could not be geocoded"`. Change to: use only resolvable depots for
  radius; if none → 422 with a non-geocode message. `(repo-analyst, prior-art-researcher, docs-researcher)`

- **Google decimal paste is stdlib-feasible; treat missing vs invalid distinctly.**
  Parse `lat, long` (strip, split on comma, float/parseFloat, WGS84 bounds).
  Reject DMS, partial tokens, and prefer rejecting `(0,0)` / Null Island rather
  than treating as valid. Omitted coords → empty Excel cells, never `0.0`.
  Lat-first Google convention only — do not auto-swap GeoJSON order.
  `(docs-researcher, prior-art-researcher)`

- **Blank coords conflict with current generator types.** `SelectedStop` and
  `build_rows` assume floats formatted to six decimals; `truck.py` always emits
  empty lat/long via `_empty` and `DepotSpec` has no coords. AC7–8 need optional
  floats → empty cells for session depots/stops, while SPEC-005 DB-sourced
  parity tests stay green. Follow the three-edit row-assembly pattern
  (`SelectedStop` → selection → `row_by_col`). `(repo-analyst, learnings-curator)`

- **Truck file coords need their own contract path.** Stop generate already
  merges form lat/long onto `DepotSummary` in `buildStopConfig`; truck generate
  does not. AC8 requires optional lat/long on the truck request path + emitter
  change. `(repo-analyst)`

- **Contract and test patterns to reuse.** Wizard camelCase → `build-config` →
  snake_case API (SPEC-003); extend `SelectionConfig` rather than parallel
  schemas (ledger api-contracts); dual-test fixture + real
  `backend/data/location_db.xlsx` for zip/match (SPEC-005); consolidation
  stride-group equality for coords across line items (SPEC-015); assert exact
  blanks/values, not “column exists” (SPEC-006 false-green lesson).
  `(learnings-curator, docs-researcher)`

- **Open implementation choice (resolved in guidance):** Session manual stops
  are **additive after thinning** — they always appear and do not consume the
  DB `stop_count` budget (design + prior-art “protected cohort”). Inverted zip
  ranges (`end < start`) are validation errors, not empty sets.
  `(prior-art-researcher, design doc)`

## Scope boundaries

- No new geocoding providers or offline geocoders
- No runtime append/edit of bundled `location_db.xlsx` (file stays read-only)
- No USPS validity lookup for ZIP codes (match DB rows only)
- No DMS / non-decimal coordinate formats
- Unrelated wizard steps unchanged (EQ codes, time windows, downloads,
  DRProject.config, launcher)

## User scenarios

1. **Address-only demo:** Operator enters depot street address without coords,
   selects stops by state or zip, downloads truck/stop files with empty depot
   lat/long cells.
2. **Radius demo:** Operator pastes Google Maps coords for at least one depot,
   chooses radius mode, gets nearby DB candidates plus any session manual stops.
3. **Custom customer:** Operator adds a manual stop with address (coords
   optional); it appears in this run's stop file without saving to the
   location database.

## Non-functional requirements

- No new heavy geo/ZIP dependencies; stdlib + existing pandas stack
- Zip range expansion may produce large sets (~100k worst case) but filtering
  stays vectorized against ~10k candidate rows
- Wizard session data remains in `sessionStorage` (existing persistence)

## Implementation guidance

- **Design references:**
  `docs/designs/2026-08-12-session-coords-and-zip-selection-design.md`
- **Files likely affected:**
  - `components/wizard/location-entry-panel.tsx` — remove geocode/Save; add paste
  - `components/wizard/truck-questions.tsx`, `stop-questions.tsx`, `review.tsx`
  - `lib/location-utils.ts` — paste parser; reuse `hasValidCoordinates` for gating
  - `lib/wizard-schema.ts`, `lib/wizard-types.ts`, `lib/build-config.ts`,
    `lib/api.ts` (`NESTED_MAP` / `selection.zips`)
  - `backend/schemas/stop_config.py` — `zip` mode, `zips`, `manual_stops`
  - `backend/schemas/truck_config.py` — optional depot lat/long for AC8
  - `backend/services/spatial.py` — `filter_by_zip` / parse helpers; radius
    policy for partial depot coords
  - `backend/generators/stop.py` — zip branch; append session stops post-thin;
    optional blank lat/long cells
  - `backend/generators/truck.py` — emit depot coords when present
  - `backend/main.py` — remove location routes; replace
    `DEPOT_GEOCODE_ERROR_MESSAGE`
  - Delete/retire: `backend/services/geocoding.py`,
    `backend/services/location_store.py`, shrink `backend/schemas/location.py`
  - `.env.example` (Trimble vars); drop unused `filelock` if nothing else needs it
  - Tests: `tests/test_spatial.py`, `tests/test_stop_generator.py`,
    `tests/test_location_api.py`, `lib/location-utils.test.ts`,
    `lib/wizard-schema.test.ts`, `lib/build-config.test.ts`,
    `lib/location-api.test.ts`, `lib/api.test.ts`
- **Files NOT to modify:**
  - Bundled `backend/data/location_db.xlsx` row contents (read-only at runtime)
  - Offline ETL (`prepare_location_db.py`, fixture makers) beyond comment/doc
    cleanup that implied runtime mutate
  - Unrelated EQ / time-window / download / DRProject / launcher behavior
- **Patterns to follow:**
  - Contract parity: `lib/wizard-schema.ts` ↔ `backend/schemas/stop_config.py`
    (`superRefine` / `mode_matches_fields`)
  - Zip template: `parseStates` + `filter_by_state` → `parseZips` + `filter_by_zip`
  - Inline depot coords: extend `buildStopConfig` merge; add parallel truck path
  - `resolve_depot_coordinates` already prefers inline lat/long — keep that
  - Delete SPEC-017 geocode/persist rather than flagging
  - Prefer flat Zod schema + `superRefine` over discriminatedUnion churn
  - Default selection: when radius unavailable at stop-step entry, default/fallback
    to `state` (current default `radius` breaks address-only demos)
- **Test expectations:**
  - Paste: canonical Google example; reject DMS, partial, `(0,0)`, out-of-bounds
  - Zip: leading zeros, ZIP+4→base-5, inclusive range edges, inverted range error,
    fixture + real `location_db.xlsx`
  - Radius gating UI + API 422 without “geocode” in message
  - Session manual stop in output with/without coords; survives aggressive thin
  - Truck depot coords present vs empty cells
  - Former location routes 404; SPEC-005 DB coord tests still pass
  - Assert exact blanks/values, not column-presence alone
