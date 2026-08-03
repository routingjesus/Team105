---
id: SPEC-002
title: "Stop file generator with static location DB"
category: feature
owner: Tye Lofts
authored_by: automated
---

## Problem statement

After truck configuration is captured (SPEC-001), the Dataset Creation Wizard must generate a **`.XLSX` stop file** by plucking customer locations from a **bundled static location database** (XLS of candidate records), filtered by DC geography, and enriched with user-specified operational fields (FixedTime, volumes, Frequency, time windows, EQ codes, optional consolidation line items).

Analysts today hand-assemble stop files or copy from old projects. This spec automates stop selection and field population so generated datasets are **synthetic, non-proprietary, and DirectRoute-importable**.

## Acceptance criteria

1. **Given** a bundled static location database XLS and DC coordinates from truck configuration, **when** the user selects radius-based stop selection with R miles, **then** only stops within R miles of at least one DC are candidates for the output file.
2. **Given** state-based selection instead of radius, **when** the user specifies one or more states, **then** stops are filtered by state from the location database **without** requiring DC proximity.
3. **Given** a candidate list larger than the requested stop count, **when** the user specifies stop density, **then** the generator thins the list to the target count using a documented density algorithm.
4. **Given** volume names and capacities from truck configuration (SPEC-001), **when** the user chooses fixed or averaged volume values for stops, **then** each stop row includes values for those volume columns (at minimum one volume column is required per DirectRoute schema).
5. **Given** Frequency configuration, **when** stops are generated, **then** each stop's `Frequency` value is drawn from the user-selected subset of `7, 6, 5, 4, 3, 2, 1, .5, .25, .125, .083, .077` and is consistent with routing weeks from truck configuration.
6. **Given** Open1/Close1/Pattern1 prompts, **when** the user chooses fixed or randomized time windows, **then** all generated stops have valid military-time Open1/Close1 (0–2359) and Pattern1 in `SMTWRFA` format matching the user's week/weekday/weekend/random/specific-day choice.
7. **Given** optional EqCode randomization enabled, **when** stops are generated, **then** a subset of stops receive EQ code values from the configured list.
8. **Given** consolidation testing enabled with N lines per customer, **when** the stop file is generated, **then** each selected customer appears N times with unique **ID2** fake order numbers.
9. **Given** alias preferences for Name, Contact, Phone, ID1, ID2, ID3, Address_2, **when** the file is generated, **then** output headers use aliases where specified while preserving required field data.
10. **Given** generated stop and truck files together, **when** imported into DirectRoute 26.x, **then** a valid solution is created **without exceptions** (manual smoke test).

## Research

Research gate run twice: an initial pass against local `main`, then refreshed after discovering SPEC-001 was already implemented and merge-ready on an unpushed-to-`main` branch, plus owner-supplied golden stop-file templates. Findings below are the refreshed, final synthesis.

- **SPEC-001 is implemented, not just speced — mirror its established contract and conventions, don't re-derive them** (repo-analyst, refreshed from SPEC-001's own research + ledger). SPEC-001's PR (open, stacked on this branch's base) established: FastAPI + Pydantic v2 backend under `backend/`; a canonical `backend/schemas/truck_config.py` contract (`DepotSummary` — address/city/state/zip/truck_count; `VolumeSpec` — name/capacity; `TruckGenerationResponse` — weeks, territory_count, depots, volume_names, seed) that SPEC-001's own docs say SPEC-002 should **mirror or extend, not duplicate**; a paired-endpoint file-delivery pattern (`POST /generate` returns JSON metadata + base64 file content, `POST /download` returns raw bytes with `Content-Disposition`); an ASCII-only input validator (`_validate_ascii`) applied to all text fields destined for the DirectRoute-imported file; and a documented Windows bootcamp environment constraint (`uv` via `winget install astral-sh.uv`, `UV_SYSTEM_CERTS=true` required for corporate TLS interception). SPEC-002 should reuse all of these rather than reinventing them.
- **DC-coordinate resolution (decision, cross-confirmed by both specs' research):** SPEC-001's own research independently flagged this exact gap and deferred it to SPEC-002 with the same suggested approach the owner confirmed here: since live geocoding is out of scope for both specs, and the bundled static location database is already geocoded (has `Latitude`/`Longitude` columns per record), DC coordinates are derived by matching the depot's address (from SPEC-001's `DepotSummary`) against that same database rather than via a separate lookup table or external geocoding call. If no exact address match exists, fall back to nearest City/State/Zip match within the same file.
- **Golden stop-file templates obtained from the owner — this resolves the column-catalog and Frequency-semantics open items directly** (owner-supplied, authoritative). Two template variants exist: a customer-facing template (69 data columns, stricter required-field flags) and an internal/analyst variant (70 columns, adds `LocationTimeZone`, marks `Longitude`/`Latitude` as required-with-geocoding-fallback). Concrete findings:
  - **Full column order** (customer-facing template, canonical for output): `Name, Contact, Phone, ID1(alias "Store #"), ID2, ID3, Address, Address2, City, State, Zip, FixedTime, Rt, Seq, SzRestriction, EqCode, Cube, Weight, UnldCube, UnldWeight, CloseTW, Open1, Close1, Pattern1, Open2, Close2, Pattern2, Longitude, Latitude, Symbol, Size, Color, Selected, EarliestDate, LatestDate, EarlyBuffer, LateBuffer, PenaltyCost, AddressErr, GeoResult, MaxSplits, CurrentRoute, RouteSequence, ServiceDate, Zone, AMStart, AMEnd, AMAdj, PMStart, PMEnd, PMAdj, Territory, Day, Frequency, ServTm, EstTime, StemTm, DrvBtwnStop, Lock, OrgTerritory, OrgDay, Change, MinDaysBetweenDeliveries, MaxDaysBetweenDeliveries, Patterns, Delivery Day, AssignedDays, Priority, OnFinalize, Country`.
  - **Required fields confirmed** (matches the P0 minimum already in Implementation guidance): `Name`, `ID1` (`Store #` alias), `Address`, `City`, `State`, `Zip`, `FixedTime`, at least one volume (`Cube`), `Open1`, `Close1`, `Pattern1`, `Frequency`. All other columns are optional and may be emitted blank.
  - **`Frequency` semantics are now authoritative, not vendor-opaque**: the template's field description states it directly — "value represents # of service occurrences per week (ex. 1 = 1x per wk, .5 = 2x per mo, .25 = 1x per mo)." This confirms the AC #5 enum (`7, 6, …, 1, .5, .25, .125, .083, .077`) is a weekly-occurrence scale with sub-1 values as fractional-month cadences (`.125` ≈ 1x/2mo, `.083`/`.077` ≈ quarterly), replacing the earlier "no public mapping" caveat.
  - **`Longitude`/`Latitude`/`GeoResult` confirmed optional-with-fallback** in the customer-facing template ("DirectRoute will populate thru Geocoding process") — validates the existing scope boundary that these may be emitted empty in P0.
  - Action for implementation: bundle the owner's template file(s) into `fixtures/stop/` (e.g. as `TEMPLATE_NewConfigStopFile.xls`) as the golden column-order reference; treat the customer-facing variant as canonical for P0 output, since it matches the already-documented required-field minimum.
- **Recommended library stack for reading/writing Excel** (docs-researcher, high confidence; independently corroborated by SPEC-001's research explicitly reserving pandas for SPEC-002's `.XLSX` work while avoiding it for SPEC-001's byte-exact `.TRUCK` output): use `python-calamine` (via `pandas.read_excel(..., engine="calamine")`) to read the legacy `.xls` database — the current pandas-ecosystem direction, since `xlrd` 2.0+ still reads `.xls` but is being phased out in favor of calamine. Use `XlsxWriter` (or `pandas.to_excel(..., engine="xlsxwriter")`) to write the output `.xlsx` — write performance is a non-issue at ~50 output rows either way.
- **Radius filtering performance is not a concern at this scale** (docs-researcher, high confidence): a vectorized NumPy/scikit-learn Haversine calculation against ~10k candidate records completes in low milliseconds — well inside the 3-second budget. A spatial index (KD-tree/BallTree) is unnecessary at this scale and only pays off at much larger N; skip it for P0.
- **Density thinning should be spatially aware, not uniform-random** (docs-researcher, prior-art-researcher): naive random subsampling within a radius over-represents dense candidate clusters and produces unrealistic route density in demos — this is the dominant realism failure mode across VRP benchmark literature (Solomon R/C/RC families, Uchoa/CVRPLib generators). Prefer **grid-based quota sampling** or **farthest-point sampling (FPS)** to thin toward the target count while preserving spatial coverage; both are fast at tens-of-output-stops scale. Document the chosen algorithm and seed it for reproducible test fixtures (satisfies AC #3's "documented density algorithm").
- **Time-window validation needs to check more than `Close1 ≥ Open1`** (prior-art-researcher): VRPTW generator precedent flags that a window can be technically valid (`Open1 ≤ Close1`) yet still infeasible if its width is narrower than the stop's `FixedTime` (service duration). Validate both `0 ≤ Open1 ≤ Close1 ≤ 2359` and `(Close1 − Open1) ≥ FixedTime`.
- **Consolidation rows should share location/time-window fields and avoid double-counting** (prior-art-researcher): industry grouping conventions (RouteQ, SWAT, SmartRoutes) group multi-order rows for the same stop by identical address and overlapping/identical time windows, with a single `FixedTime` per physical stop rather than one per line item. Apply density thinning at the **customer** level before expanding to N consolidation line items, so consolidation doesn't inflate the effective stop count past the target.
- **Prior learnings exist and were initially missed — process gap, not absence of signal** (learnings-curator, corrected): the first research pass correctly found no `.spec/_ledger/` on the local checkout, but SPEC-001's branch (pushed, PR open, not yet merged) already has `.spec/_ledger/api-contracts.yaml`, `directroute-file-formats.yaml`, and `environment.yaml` with directly applicable entries (contract-mirroring decision, `EDate`/`LDate` field-reference correction, Windows bootcamp `uv`/TLS constraint). All three are folded into the findings above. Lesson: check unmerged sibling-spec branches, not just `main`, when curating prior learnings in a fast-moving multi-branch repo.

## Scope boundaries

- **In scope:** Static location DB loading, radius and state-based filtering, density thinning, stop field population (FixedTime, volumes, Frequency, Open1/Close1/Pattern1, EqCode, consolidation/ID2, aliases), `.XLSX` output, REST API endpoint accepting truck config + stop answers.
- **Out of scope:** Truck file generation (SPEC-001), wizard UI (SPEC-003), live geocoding API (Longitude/Latitude/GeoResult may be empty; DirectRoute geocodes on import), Open2/Close2/Pattern2+ (P1), DRProject.config.
- **Out of scope:** Informing the user they are in the "stop phase" — orchestration is SPEC-003's job; this spec exposes a stop generation API.

## User scenarios

- As a **QA Engineer**, I want stops plucked from a known static database within a radius of a test DC so scenarios are reproducible and non-proprietary.
- As an **Implementation Consultant**, I want to configure Frequency and time windows so I can test SchedulePro and TerritoryPro scenarios.
- As a **Sales Engineer**, I want consolidation line items (multiple ID2 per customer) to demo order consolidation in DirectRoute.

## Non-functional requirements

- Static location database is bundled with the application (no external DB dependency in P0).
- Stop generation for 50 stops from a 10k-record database completes in under 3 seconds.
- All addresses in output come from the static database — no invented addresses in P0.

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — stop row builder, orchestrates filter → thin → enrich → write, following SPEC-001's `backend/generators/truck.py` pattern of an ordered column-definition table driving a generic writer
  - `backend/data/location_db.xls` — bundled candidate locations with `Latitude`/`Longitude` columns (owner to supply the existing master file; not yet in repo)
  - `backend/schemas/stop_config.py` — Pydantic v2 models for stop question answers; import/extend `DepotSummary`, `VolumeSpec`, and `TruckGenerationResponse` from `backend/schemas/truck_config.py` (SPEC-001's canonical contract) rather than redefining depot/volume shapes
  - `backend/services/spatial.py` — DC-coordinate lookup (match depot address against `location_db`), radius/state filter, density thinning (grid or FPS)
  - `backend/main.py` — extend with `POST /api/stops/generate` (JSON metadata + base64 content) and `POST /api/stops/download` (raw bytes + `Content-Disposition`), mirroring SPEC-001's paired-endpoint pattern
  - `tests/test_stop_generator.py`, `tests/test_spatial.py`
  - `fixtures/stop/` — bundle the owner's golden stop-file template(s) here (e.g. `TEMPLATE_NewConfigStopFile.xls`) as the column-order reference, plus a sample DB slice and expected outputs
- **Files NOT to modify:**
  - Truck generator internals (SPEC-001) — import from `backend/schemas/truck_config.py`, don't edit it
  - Wizard UI (SPEC-003)
- **Patterns to follow:**
  - Accept truck configuration output from SPEC-001 as input via its actual `TruckGenerationResponse` shape (depot addresses, weeks, volume names/capacities), not a redefined equivalent
  - Full stop-file column order (canonical, customer-facing template): `Name, Contact, Phone, ID1, ID2, ID3, Address, Address2, City, State, Zip, FixedTime, Rt, Seq, SzRestriction, EqCode, Cube, Weight, UnldCube, UnldWeight, CloseTW, Open1, Close1, Pattern1, Open2, Close2, Pattern2, Longitude, Latitude, Symbol, Size, Color, Selected, EarliestDate, LatestDate, EarlyBuffer, LateBuffer, PenaltyCost, AddressErr, GeoResult, MaxSplits, CurrentRoute, RouteSequence, ServiceDate, Zone, AMStart, AMEnd, AMAdj, PMStart, PMEnd, PMAdj, Territory, Day, Frequency, ServTm, EstTime, StemTm, DrvBtwnStop, Lock, OrgTerritory, OrgDay, Change, MinDaysBetweenDeliveries, MaxDaysBetweenDeliveries, Patterns, Delivery Day, AssignedDays, Priority, OnFinalize, Country` — emit all columns (blank where not populated) so output structurally matches the golden template, not just the required subset
  - Required stop columns minimum: Name, ID1, Address, City, State, Zip, FixedTime, at least one volume (Cube), Open1, Close1, Pattern1, Frequency
  - `Frequency` = service occurrences per week (1 = 1x/wk; .5 = 2x/mo; .25 = 1x/mo; sub-.25 values are quarterly-and-longer cadences) — validate the user-selected subset against this scale, not an arbitrary enum
  - Derive DC coordinates by matching depot address fields (from `DepotSummary`) against `location_db`'s own `Latitude`/`Longitude` columns — do not call an external geocoding API and do not introduce a second lookup table
  - Read `.xls` via `pandas.read_excel(..., engine="calamine")` (`python-calamine`); write output via `pandas.to_excel(..., engine="xlsxwriter")` or `XlsxWriter` directly
  - Radius filtering: vectorized NumPy/scikit-learn Haversine across all candidates against DC coordinate(s); no spatial index needed at ~10k-record scale
  - Density thinning: grid-based quota sampling or farthest-point sampling (FPS), seeded for reproducibility; thin at the customer level before consolidation line-item expansion
  - Time-window validation: enforce both `0 ≤ Open1 ≤ Close1 ≤ 2359` and `(Close1 − Open1) ≥ FixedTime`
  - Consolidation rows for the same customer share identical Address/City/State/Zip and time-window fields; `FixedTime` applies once per physical stop, not per line item
  - ASCII-only validation on all text fields feeding the output file, reusing SPEC-001's `_validate_ascii` pattern (`backend/schemas/truck_config.py`) for consistency across generators
  - Windows bootcamp environment: `uv` via `winget install astral-sh.uv`; set `UV_SYSTEM_CERTS=true` if corporate TLS interception breaks dependency installs
- **Test expectations:**
  - Unit test: DC-coordinate lookup resolves lat/long from `location_db` given a depot address, with a documented fallback for no exact match
  - Unit test: radius filter returns only stops within distance
  - Unit test: state filter ignores DC location
  - Unit test: density thinning reduces candidate count to target while preserving spatial spread (not clustered)
  - Unit test: output column order matches the golden template exactly, including blank optional columns
  - Unit test: time-window validation rejects windows narrower than `FixedTime` even when `Close1 ≥ Open1`
  - Unit test: consolidation creates N rows with unique ID2 per customer, shared location/time-window fields, and does not multiply `FixedTime`
  - API contract test: `POST /api/stops/generate` and `/download` mirror SPEC-001's response/metadata shape conventions
  - Integration test with SPEC-001 truck output → combined DirectRoute import smoke test
