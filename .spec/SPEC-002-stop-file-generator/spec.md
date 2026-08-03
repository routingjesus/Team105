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

- **Repo is greenfield — no code or dependency manifests exist yet** (repo-analyst). Only `.spec/` and `.cursor/` scaffolding is present; there is no `backend/`, `tests/`, or `fixtures/` directory, and no Python/Node dependency manifest. Everything in Implementation guidance below must be created from scratch. `.cursor/rules/repo-instructions.md` establishes conventions (Python `backend/` or `api/`, `snake_case`, pytest in a parallel `tests/`) but the backend framework (FastAPI vs. Django) is not yet chosen — this is a shared decision with SPEC-001; whichever spec lands first establishes the toolchain.
- **DC-coordinate resolution (decision, owner-confirmed):** radius filtering (AC #1) needs DC lat/long, but SPEC-001 supplies depot **addresses** only and both specs exclude live geocoding. Resolved: the bundled static location database is already geocoded (has `Latitude`/`Longitude` columns per record, per owner confirmation), so DC coordinates are derived by matching the depot's address (City/State/Zip) against that same database rather than via a separate lookup table or external geocoding call. This keeps the "no live geocoding" boundary intact for both specs and avoids introducing a second static asset. If no exact address match exists in the database, fall back to nearest City/State/Zip match within the same file.
- **Sourcing the static location database file remains an implementation task, not a research blocker** (repo-analyst, owner input). No `.xls` file exists in the repo yet; the owner has confirmed a master geocoded `.xls` already exists (likely as an existing Team 105 asset from prior tooling) and should be bundled into `backend/data/` during implementation rather than generated fresh.
- **Recommended library stack for reading/writing Excel** (docs-researcher, high confidence): use `python-calamine` (via `pandas.read_excel(..., engine="calamine")`) to read the legacy `.xls` database — the current pandas-ecosystem direction, since `xlrd` 2.0+ still reads `.xls` but is being phased out in favor of calamine (correction: xlrd did not drop `.xls` support, it dropped `.xlsx` support in 2.0 — the deprecation risk is `xlrd` losing pandas-ecosystem support over time, not a currently-broken reader). Use `XlsxWriter` (or `pandas.to_excel(..., engine="xlsxwriter")`) to write the output `.xlsx` — write performance is a non-issue at ~50 output rows either way.
- **Radius filtering performance is not a concern at this scale** (docs-researcher, high confidence): a vectorized NumPy/scikit-learn Haversine calculation against ~10k candidate records completes in low milliseconds — well inside the 3-second budget. A spatial index (KD-tree/BallTree) is unnecessary at this scale and only pays off at much larger N; skip it for P0.
- **Density thinning should be spatially aware, not uniform-random** (docs-researcher, prior-art-researcher): naive random subsampling within a radius over-represents dense candidate clusters and produces unrealistic route density in demos — this is the dominant realism failure mode across VRP benchmark literature (Solomon R/C/RC families, Uchoa/CVRPLib generators). Prefer **grid-based quota sampling** or **farthest-point sampling (FPS)** to thin toward the target count while preserving spatial coverage; both are fast at tens-of-output-stops scale. Document the chosen algorithm and seed it for reproducible test fixtures (satisfies AC #3's "documented density algorithm").
- **No complete public DirectRoute 26.x column schema exists** (docs-researcher, prior-art-researcher, high confidence): Trimble/Appian's public integration docs (successor to Descartes DirectRoute) confirm partial field semantics — `Name`, `ID1`/`ID2`/`ID3`, `Address`/`City`/`State`/`Zip`, `Open1`/`Close1`/`Pattern1` (military time, `SMTWRFA` weekday-letter grammar), `FixedTime`, `EqCode` — but not the full 70+-column order, and volume column names are DirectRoute-preference-configured rather than fixed. The fractional `Frequency` enum (`.5`, `.25`, `.125`, `.083`, `.077`) has no public mapping and appears DirectRoute/Descartes-specific. `TEMPLATE_NewConfigStopFile.xls` remains the authoritative column-order reference, and AC #10's manual DirectRoute import smoke test — not external documentation — is the real validation gate for schema correctness.
- **Time-window validation needs to check more than `Close1 ≥ Open1`** (prior-art-researcher): VRPTW generator precedent flags that a window can be technically valid (`Open1 ≤ Close1`) yet still infeasible if its width is narrower than the stop's `FixedTime` (service duration). Validate both `0 ≤ Open1 ≤ Close1 ≤ 2359` and `(Close1 − Open1) ≥ FixedTime`.
- **Consolidation rows should share location/time-window fields and avoid double-counting** (prior-art-researcher): industry grouping conventions (RouteQ, SWAT, SmartRoutes) group multi-order rows for the same stop by identical address and overlapping/identical time windows, with a single `FixedTime` per physical stop rather than one per line item. Apply density thinning at the **customer** level before expanding to N consolidation line items, so consolidation doesn't inflate the effective stop count past the target.
- **No prior learnings exist in this repo** (learnings-curator): there is no `.spec/_ledger/`, and no spec has reached `status: done` yet, so there is nothing to carry forward from prior work. This is expected for an early-stage repo.

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
  - `backend/generators/stop.py` — stop row builder, orchestrates filter → thin → enrich → write
  - `backend/data/location_db.xls` — bundled candidate locations with `Latitude`/`Longitude` columns (owner to supply the existing master file; not yet in repo)
  - `backend/schemas/stop_config.py` — Pydantic models for stop question answers
  - `backend/services/spatial.py` — DC-coordinate lookup (match depot address against `location_db`), radius/state filter, density thinning (grid or FPS)
  - `tests/test_stop_generator.py`, `tests/test_spatial.py`
  - `fixtures/stop/` — sample DB slice and expected outputs
- **Files NOT to modify:**
  - Truck generator (SPEC-001) except shared session/types module if extracted
  - Wizard UI (SPEC-003)
- **Patterns to follow:**
  - Accept truck configuration output from SPEC-001 as input (depot addresses, weeks, volume names)
  - Required stop columns minimum: Name, ID1, Address, City, State, Zip, FixedTime, at least one volume, Open1, Close1, Pattern1, Frequency
  - Derive DC coordinates by matching depot address fields against `location_db`'s own `Latitude`/`Longitude` columns — do not call an external geocoding API and do not introduce a second lookup table
  - Read `.xls` via `pandas.read_excel(..., engine="calamine")` (`python-calamine`); write output via `pandas.to_excel(..., engine="xlsxwriter")` or `XlsxWriter` directly
  - Radius filtering: vectorized NumPy/scikit-learn Haversine across all candidates against DC coordinate(s); no spatial index needed at ~10k-record scale
  - Density thinning: grid-based quota sampling or farthest-point sampling (FPS), seeded for reproducibility; thin at the customer level before consolidation line-item expansion
  - Time-window validation: enforce both `0 ≤ Open1 ≤ Close1 ≤ 2359` and `(Close1 − Open1) ≥ FixedTime`
  - Consolidation rows for the same customer share identical Address/City/State/Zip and time-window fields; `FixedTime` applies once per physical stop, not per line item
- **Test expectations:**
  - Unit test: DC-coordinate lookup resolves lat/long from `location_db` given a depot address, with a documented fallback for no exact match
  - Unit test: radius filter returns only stops within distance
  - Unit test: state filter ignores DC location
  - Unit test: density thinning reduces candidate count to target while preserving spatial spread (not clustered)
  - Unit test: time-window validation rejects windows narrower than `FixedTime` even when `Close1 ≥ Open1`
  - Unit test: consolidation creates N rows with unique ID2 per customer, shared location/time-window fields, and does not multiply `FixedTime`
  - Integration test with SPEC-001 truck output → combined DirectRoute import smoke test
