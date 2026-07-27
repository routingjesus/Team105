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

<!-- Deferred — run research gate before marking ready. -->

Investigate before implementation:

- Select or create the bundled static location database XLS (non-proprietary addresses)
- Catalog required stop columns across DR, TP, SP (70+ fields in brainstorm; P0 minimum subset)
- Haversine or equivalent distance calculation for radius filtering
- `TEMPLATE_NewConfigStopFile.xls` column order as golden template reference

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
  - `backend/generators/stop.py` — stop row builder and spatial filter
  - `backend/data/location_db.xls` — bundled candidate locations (or path config)
  - `backend/schemas/stop_config.py` — Pydantic models for stop question answers
  - `backend/services/spatial.py` — radius/state filter + density thinning
  - `tests/test_stop_generator.py`, `tests/test_spatial.py`
  - `fixtures/stop/` — sample DB slice and expected outputs
- **Files NOT to modify:**
  - Truck generator (SPEC-001) except shared session/types module if extracted
  - Wizard UI (SPEC-003)
- **Patterns to follow:**
  - Accept truck configuration output from SPEC-001 as input (depot addresses, weeks, volume names)
  - Required stop columns minimum: Name, ID1, Address, City, State, Zip, FixedTime, at least one volume, Open1, Close1, Pattern1, Frequency
- **Test expectations:**
  - Unit test: radius filter returns only stops within distance
  - Unit test: state filter ignores DC location
  - Unit test: density thinning reduces candidate count to target
  - Unit test: consolidation creates N rows with unique ID2 per customer
  - Integration test with SPEC-001 truck output → combined DirectRoute import smoke test
