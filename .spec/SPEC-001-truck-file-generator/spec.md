---
id: SPEC-001
title: "Truck file generator (.TRUCK)"
category: feature
owner: Tye Lofts
authored_by: automated
---

## Problem statement

The Dataset Creation Wizard needs a backend capability that produces **tab-delimited `.TRUCK` truck files** matching DirectRoute import expectations. Today, analysts rely on the legacy **"Explode my Trucks.xlsxm"** Excel macro, which only supports a single DC, no volume prompts, and no integration with stop file generation.

This spec delivers the **truck-building phase** of the wizard: capture truck-related answers (routing weeks, territories, depots, volumes, costs, work rules) and emit a structurally valid `.TRUCK` file with the 76-column header row defined by the macro baseline, extended for **multi-depot** and **multi-volume** scenarios.

## Acceptance criteria

1. **Given** a generation request with routing weeks (>0), territory count, single DC address (City, State, Zip), MiCost, HrCost, FixedCost, MaxWork, MaxDrive, PreTrip, and PostTrip matching macro defaults, **when** the truck generator runs, **then** the output `.TRUCK` file contains 76 tab-delimited columns with headers matching the Explode my Trucks macro (`TrkID` through `Dash Repeater`).
2. **Given** macro-equivalent inputs, **when** the truck file is generated, **then** row 2 seed values match macro defaults (`Available=TRUE`, `OneWay=FALSE`, `Redispatch=FALSE`, `Size=12`, cost fields populated, `PreTrip`/`PostTrip` set).
3. **Given** routing weeks = W and territory count = T, **when** generation completes, **then** the truck file contains **T × (W × 7)** data rows with auto-filled `EDate`, `LDate`, `Day` (SU–SA cycle), `Week`, `Route`, and `Territory` (T01, T02, …) per macro logic.
4. **Given** multiple depots with distinct addresses, **when** the user specifies trucks per depot, **then** each depot's trucks are generated with the correct DC address columns (`Address`, `City`, `State`, `Zip`) on their rows.
5. **Given** N named volumes with per-truck capacities, **when** generation completes, **then** volume capacity columns are present in the truck file output (column names match user-provided volume names).
6. **Given** a completed generation, **when** the API returns the artifact, **then** the response includes truck row count, weeks, territory count, depot count, and routing metadata for downstream stop generation.
7. **Given** generated truck file, **when** imported into DirectRoute 26.x, **then** the file loads without blocking schema errors (manual smoke test).

## Research

<!-- Deferred — run research gate before marking ready. -->

Investigate before implementation:

- DirectRoute `.TRUCK` import parser expectations in DirectRoute repo (if accessible)
- Column union across DR, TP, SP for truck-related fields beyond the 76 macro columns
- Whether `TrkID` and `SpEq` formulas from the macro should be replicated exactly or simplified for v1

## Scope boundaries

- **In scope:** Truck question data model, `.TRUCK` tab-delimited file generation, macro parity for single-depot baseline, multi-depot and multi-volume extensions, REST API endpoint(s) for truck generation.
- **Out of scope:** Stop file generation (SPEC-002), wizard UI (SPEC-003), static location database, spatial/radius logic, DRProject.config, RFP upload, geocoding (Longitude/Latitude/GeoResult may be empty placeholders).
- **Out of scope:** User-facing wizard flow — this spec is backend/API only; a minimal API contract test harness is sufficient.

## User scenarios

- As a **Development Engineer**, I want to POST truck configuration parameters to an API and receive a `.TRUCK` file so I can validate truck file structure without the full wizard.
- As the **stop file generator (SPEC-002)**, I need depot addresses and routing weeks from truck generation so stop spatial logic and Frequency alignment can use them.
- As **QA**, I want macro-parity output for single-depot defaults so I can diff against known-good Explode my Trucks output.

## Non-functional requirements

- Generation of a typical scenario (2 weeks, 5 territories, 2 depots) completes in under 2 seconds on bootcamp hardware.
- Output is deterministic given identical inputs and seed (if randomization is added later for TrkID patterns, seed must be supported).
- No proprietary customer data in generated files.

## Implementation guidance

- **Files likely affected:**
  - `backend/` or `api/` — new Python module for truck generation (FastAPI route TBD)
  - `backend/generators/truck.py` (or equivalent) — column map and row builder
  - `backend/schemas/truck_config.py` — Pydantic models for truck question answers
  - `tests/test_truck_generator.py` — macro parity tests
  - `fixtures/truck/` — expected output samples for single-depot macro baseline
- **Files NOT to modify:**
  - Stop file generator code (SPEC-002)
  - Next.js wizard UI (SPEC-003)
  - `.cursor/skills/` Creator kit files
- **Patterns to follow:**
  - Schema-first emitters: deterministic column output from templates, not LLM-generated bytes
  - Port macro column order exactly from brainstorm VBA header list (A1–BX1 equivalents)
- **Test expectations:**
  - Unit tests for row count formula: `territories × weeks × 7`
  - Unit tests for Day cycle (SU, MO, TU, WE, TH, FR, SA)
  - Integration test: generate file → assert 76 headers present → assert required fields non-empty on row 2
