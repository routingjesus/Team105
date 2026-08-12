---
id: SPEC-020
title: "Optional address when coordinates pasted"
category: feature
owner: Tye Lofts
authored_by: augmented
---

## Problem statement

After SPEC-019, operators can paste Google Maps coordinates for a depot or
manual stop, but street, city, state, and ZIP remain required even when
coordinates are present. That blocks a common case: the user has a pin and
does not have (or does not want to type) a full street address.

The Dataset Creation Wizard should treat a location as complete when it has
pasted coordinates **or** all four address fields (or both). The same rule
applies to depots (truck file) and manual stops (stop file). Blank address
fields write as empty cells in generated files; coordinates still write as
they do today.

Design reference:
`docs/designs/2026-08-12-coords-or-address-location-design.md`

## Acceptance criteria

1. **Given** a depot with valid pasted coordinates
   (`38.38080520110032, -97.4279212147894`) and blank street, city, state, and
   ZIP, **when** the user proceeds from the route-details step, **then** the
   wizard accepts the depot (no `"Required"` errors on those four fields).
2. **Given** a manual stop with valid pasted coordinates and blank street,
   city, state, and ZIP, **when** the user proceeds from the stop step,
   **then** the wizard accepts the stop (no `"Required"` errors on those four
   fields).
3. **Given** a depot with no coordinates and blank street, city, state, or
   ZIP, **when** validation runs, **then** each blank field among those four
   shows `"Required"`.
4. **Given** a manual stop with no coordinates and blank street, city, state,
   or ZIP, **when** validation runs, **then** each blank field among those
   four shows `"Required"`.
5. **Given** a coords-only depot (valid lat/long, blank address quartet),
   **when** the truck file is generated, **then** `Address` / `City` /
   `State` / `Zip` cells are empty and `Latitude` / `Longitude` contain the
   pasted values (six-decimal formatting as today).
6. **Given** a coords-only manual stop, **when** the stop file is generated,
   **then** Address / City / State / Zip cells are empty, `Name` and `ID1`
   are `Manual stop N` (1-based index in the session list), and lat/long
   cells contain the pasted values.
7. **Given** an address-only depot or manual stop (all four address fields
   filled, no coordinates), **when** generation runs, **then** the location
   is accepted, address cells are populated, and lat/long cells are empty
   (SPEC-019 behavior unchanged).
8. **Given** both a complete address and pasted coordinates, **when**
   validation and generation run, **then** the location is accepted and both
   address and coordinate cells are populated.
9. **Given** coordinates are present on a depot or manual stop, **when** the
   location panel renders, **then** the street / city / state / ZIP labels
   include `(optional)`. Clearing coordinates restores labels without
   `(optional)` and re-applies the required rule on the next validation.
10. **Given** a generate request whose depot or manual stop has neither valid
    coordinates nor a complete address quartet, **when** the backend validates
    it, **then** the API returns HTTP 422.
11. **Given** the Vitest wizard tests and pytest backend tests run, **then**
    existing non-superseded tests pass; new tests cover the either-or matrix
    (coords-only, address-only, both, neither, partial address without coords)
    on wizard schema, `DepotSpec`, `ManualStop`, and generator output.

## Research

Research gate completed 2026-08-12 (learnings-curator, repo-analyst,
docs-researcher, prior-art-researcher).

**Validation is the gap; emission already matches the ACs**

- `backend/generators/truck.py` writes `Address`/`City`/`State`/`Zip` as
  given (empty string stays an empty cell) and formats lat/long to six
  decimals or blank when `None`. `backend/generators/stop.py`
  `_manual_stops_frame` already names a blank street
  `Manual stop {index + 1}` and copies address fields as-is.
  `lib/build-config.ts` already trims and forwards `""`. Do not change
  generators unless a test proves otherwise (repo-analyst, learnings-curator
  SPEC-005/019 row-assembly passthrough).
- `backend/services/spatial.py` `resolve_depot_coordinates` already prefers
  inline pasted coords, so a coords-only depot still unlocks radius.
  `stop-questions.tsx` gating stays out of scope (repo-analyst, SPEC-019).

**One shared completeness predicate, mirrored client and server**

- Frontend: `locationFieldsSchema` in `lib/wizard-schema.ts` already backs
  both `depotSchema` and `manualStopSchema`. Switch the four address fields
  to `optionalAscii`, then `.superRefine` with `hasValidCoordinates` OR
  `hasCompleteAddress` (new trim-aware helper in `lib/location-utils.ts`).
  When coords are absent, emit `"Required"` per blank field via
  `ctx.addIssue({ path: ["address"] })` (and city/state/zip). Do not put
  the rule only on `wizardSchema.superRefine` — nested depot/stop parse
  needs per-item paths (repo-analyst, docs-researcher Zod 4 refinements).
- Zod 4.4.3: after `locationFieldsSchema` has a refinement, extend it with
  `.safeExtend()`, not `.extend()` — Zod 4 throws if you `.extend()` a
  refined object. `depotSchema` currently uses `.extend({ trucks })` and
  must switch (docs-researcher, https://zod.dev/api#refinements).
- Backend: drop `min_length=1` on `DepotSpec` and `ManualStop`; use
  `Field(default="")`. Shared `@model_validator(mode="after")` helper lives
  next to `DepotSpec` in `backend/schemas/truck_config.py` and is imported
  by `ManualStop` (same sharing as `_validate_ascii`). Field validators
  cannot see later-declared lat/long reliably — `mode="after"` is required
  (docs-researcher Pydantic v2, repo-analyst, ledger api-contracts).
- Completeness on the backend must use `.strip()` and treat coordinates as
  an atomic pair matching `hasValidCoordinates` (both present, in bounds,
  reject `(0, 0)`). Today Pydantic only checks bounds — that SPEC-019 drift
  would let the API accept coords the wizard rejects (repo-analyst,
  prior-art-researcher Null Island).
- Empty `""` already passes `_validate_ascii` / `isAsciiText`; non-ASCII in
  a filled field stays rejected (learnings-curator SPEC-003).

**422 mapping and RHF error clearing**

- FastAPI 0.141.1 + Pydantic 2.13.4: a plain `raise ValueError` in
  `model_validator` yields HTTP 422 but a **model-scoped** `loc` (e.g.
  `["body", "depots", 0]`), which `lib/api.ts` `apiLocToFormPath` cannot
  map onto `depots.0.address`. For field-level `"Required"` parity, raise
  `ValidationError.from_exception_data` with `loc=('address',)` (etc.) per
  blank field (docs-researcher, pydantic#10668).
- `@hookform/resolvers` 5.7.1 maps `issue.path.join('.')` to RHF paths.
  Cross-field errors can stick after coords paste/clear until re-validation
  (resolvers #661/#672). After **Use coordinates** / **Clear coordinates**,
  `trigger()` the location prefix (or `clearErrors` on the four fields)
  (docs-researcher).

**Either-or semantics and empty export cells**

- Industry practice is a flat location object with an `anyOf`-style
  predicate (coords, address, or both) — not `oneOf` XOR and not a
  discriminated union. Unions fit mutually exclusive modes; this UI allows
  both, and Zod 3/4 `discriminatedUnion` + `superRefine` does not compose
  (prior-art-researcher, Zod #2440).
- Routing/GIS exports use empty cells for missing address, not placeholders
  (`N/A`, `-`, `0`). Identity fallbacks like `Manual stop N` on Name/ID1
  are separate and already implemented (prior-art-researcher).
- No public DirectRoute `.TRUCK` spec documents empty address + populated
  lat/long. SPEC-001 already treated the macro as de facto schema; empty
  address cells with coords remain the agreed product behavior, covered by
  generator tests (docs-researcher, SPEC-001). Trimble Plan Trip REST
  requires coords **or** address per stop — analogous either-or, not a
  file-format proof.

**Tests must pin the matrix, not a subset**

- Keep `lib/wizard-schema.test.ts` `"requires a depot address"` (no coords
  → still invalid). Add coords-only, both, neither, and partial-address-
  without-coords on wizard schema, `DepotSpec`, `ManualStop`, and generator
  output. Subset-style assertions are a known false-green (learnings-curator
  SPEC-006/010, repo-analyst).
- Wire helpers into `superRefine` / `model_validator`, not tests-only
  (SPEC-002 `validate_time_window` gap).

## Scope boundaries

- **In scope:** Either-or completeness for depots and manual stops; optional
  labels when coordinates are present; empty address cells in truck and stop
  output; matching wizard Zod and backend Pydantic validation.
- **Out of scope:** New location types or a coords-vs-address discriminated
  union; making address always optional with no either-or check; placeholders
  in Address / City / State / Zip cells; new geocoding, reverse geocode, or
  DMS paste formats; changes to radius / state / zip selection logic beyond
  what coords-only depots already unlock; unrelated wizard step redesign
  (costs, volumes, downloads, packaging).

## User scenarios

- *Pin-only depot:* An operator copies coordinates from Google Maps for a
  DC they do not have a street address for. They paste, leave address fields
  blank, and generate a truck file whose depot rows have lat/long and empty
  address cells. Radius stop selection is available because the depot has
  coords.
- *Pin-only manual stop:* The same paste on a session manual stop produces a
  stop row with empty address cells and `Name`/`ID1` of `Manual stop N`.
- *Address-only (unchanged):* An operator who only has a street address still
  fills the four fields and leaves coordinates blank.

## Non-functional requirements

- Wizard and backend completeness rules must stay in lockstep (Zod already
  mirrors Pydantic).
- Empty address strings remain ASCII-valid; non-ASCII in a filled field is
  still rejected.
- No new runtime dependencies.

## Implementation guidance

### Design references

- `docs/designs/2026-08-12-coords-or-address-location-design.md`

### Files likely affected

- `lib/location-utils.ts`, `lib/location-utils.test.ts`
- `lib/wizard-schema.ts`, `lib/wizard-schema.test.ts`
- `components/wizard/location-entry-panel.tsx`
- `backend/schemas/truck_config.py`
- `backend/schemas/stop_config.py`
- `tests/test_truck_generator.py`, `tests/test_truck_api.py`,
  `tests/test_stop_generator.py`, `tests/test_location_api.py`

### Files NOT to modify

- `backend/generators/truck.py` and `backend/generators/stop.py` unless a
  test proves emission of empty strings is not already correct
- `backend/services/spatial.py` (inline coords already preferred)
- Radius / zip / state UI gating in `components/wizard/stop-questions.tsx`
  (already uses `hasValidCoordinates`)
- `lib/build-config.ts` (already trims and forwards empty strings)
- Location database, geocoding remnants, download / packaging paths

### Patterns to follow

- Shared `locationFieldsSchema` already backs both `depotSchema` and
  `manualStopSchema` — put the either-or `superRefine` there, not twice.
- Reuse `hasValidCoordinates` in `lib/location-utils.ts`; add
  `hasCompleteAddress` (trim-aware) for the address side of the rule.
- After refining `locationFieldsSchema`, use `.safeExtend()` for
  `depotSchema` (Zod 4.4.3; plain `.extend()` throws on refined objects).
- Backend: `Field(default="")` on the four address fields; shared
  `model_validator(mode="after")` helper in `truck_config.py`, imported by
  `ManualStop`. Match `hasValidCoordinates` (pair + bounds + reject
  `(0, 0)`); use `.strip()` for address completeness.
- For HTTP 422 field mapping through `lib/api.ts`, raise
  `ValidationError.from_exception_data` with per-field `loc`s (`address`,
  `city`, `state`, `zip`) when coords are absent — not a single model-level
  `ValueError`.
- After paste/clear coordinates in `LocationEntryPanel`, `trigger()` the
  location prefix (or `clearErrors` on the four fields) so RHF drops stale
  `"Required"` errors.
- `_manual_stops_frame` already names a blank address
  `Manual stop {index + 1}`.

### Test expectations

- Wizard schema: coords-only depot valid; coords-only manual stop valid;
  address-only still valid; neither invalid; partial address without coords
  invalid; non-ASCII rejection on filled fields unchanged.
- `hasCompleteAddress`: `"  "` is not complete.
- Pydantic: same matrix on `DepotSpec` and `ManualStop`, including `(0, 0)`
  not counting as coordinates.
- API: coords-only generate returns 200; neither returns 422 with loc paths
  that map to the four address fields.
- Generators: coords-only depot emits empty address cells and populated
  lat/long; coords-only manual stop emits empty address cells and
  `Manual stop N` for Name/ID1.
- Existing `"requires a depot address"` test must still fail when coordinates
  are absent.
