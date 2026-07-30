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

Research gate completed 2026-07-30. Findings are synthesized across four lanes; attribution in parentheses.

**Format authority and validation strategy**

- No public specification exists for the 76-column `.TRUCK` import schema — Trimble docs confirm the file type and tab-delimited usage but not the column layout. The legacy "Explode my Trucks.xlsxm" macro output is therefore the de facto schema, and golden-master (characterization) testing against known-good macro output is the primary CI validation. DirectRoute 26.x import remains a manual smoke test outside CI (prior-art-researcher).
- **Open item (non-blocking to start, blocking for the parity AC test):** obtain a known-good macro output sample to seed `fixtures/truck/`. The 76-column header list is documented in the PRD, so header/row-logic work can begin before the sample lands.
- Compare golden fixtures as raw **bytes**, not parsed rows — round-tripping through a CSV parser masks encoding, line-ending, and whitespace differences the real parser will see (prior-art-researcher, docs-researcher).

**Formatting fidelity decisions** (prior-art-researcher, docs-researcher)

- Booleans emit uppercase `TRUE`/`FALSE` literal strings — never Python `str(True)`.
- Costs pre-format to fixed two decimals (`1.39`, `30.00`) before writing; never rely on float repr.
- Line endings are CRLF; no UTF-8 BOM; no trailing tab after the last column (unless the macro sample proves otherwise — replicate the sample exactly).
- Encoding contradiction resolved: VBA `Print #` writes ANSI/Windows-1252 while modern Python defaults to UTF-8. Decision: keep all generated content ASCII-only (validated at input), where cp1252 and UTF-8-without-BOM are byte-identical; verify against the macro sample bytes.
- `EDate`/`LDate` auto-fill must replicate the macro's *text representation* of dates, not Excel-internal serials; port date math with explicit `DateSerial`-equivalent logic, never locale-dependent parsing.
- `TrkID`/`SpEq`: replicate macro formulas exactly for the single-depot baseline — byte-parity golden tests require it; simplification would silently break the parity AC. Extensions (multi-depot numbering) layer on top.

**Stack and emitter architecture** (docs-researcher)

- FastAPI 0.141.1 + Pydantic 2.13.4 (current stable, July 2026); install via `fastapi[standard]`.
- Emit via stdlib `csv.writer` with the `excel-tab` dialect and explicit `lineterminator="\r\n"`, building `list[list[str]]` of pre-formatted cell strings. Do not use pandas for the truck file — its line-ending and boolean defaults are OS-dependent and VBA-incompatible (pandas stays reserved for SPEC-002's `.XLSX`).
- Column map as data, not code: an ordered column-definition table drives the generic writer, which is what makes dynamic volume columns possible without forking emitter logic (prior-art-researcher, docs-researcher).
- Volumes modeled as `list[VolumeSpec]` (name + capacity) with a unique-name validator — dynamic column names are an output concern, not a dynamic-Pydantic-model concern.
- Determinism: thread a `random.Random(seed)` instance through the generator (never module-level `random.seed()`); accept `seed` in the request.

**Cross-spec contract decisions** (repo-analyst)

- Repo is greenfield — no application code exists. Use `backend/` (not `api/`) for consistency with SPEC-002/003 assumptions; pytest in a parallel `tests/`; `snake_case` Python; `feat(SPEC-001):` commit format per `.cursor/rules/repo-instructions.md`.
- Multi-depot row semantics defined: each depot has `trucks_per_depot`; territory numbering (`T01`, `T02`, …) continues across depots; total data rows = (Σ trucks per depot) × weeks × 7. In the single-depot baseline this reduces to AC3's `T × (W × 7)` with T = territory count.
- AC6 "routing metadata" enumerated: the generation response carries `truck_row_count`, `weeks`, `territory_count`, `depot_count`, `depots[]` (address, city, state, zip, truck count), `volume_names[]` (with capacities), and `seed`.
- File + metadata delivery: a single HTTP response body can't natively carry both. Recommendation for bootcamp scale: `POST /api/trucks/generate` returns JSON metadata with the `.TRUCK` content base64-encoded (or a paired download endpoint); final contract to be agreed with SPEC-002/003 as SPEC-003 anticipates.
- **Cross-spec risk (owned by SPEC-002, not this spec):** SPEC-002's radius logic mentions "DC coordinates from truck configuration," but geocoding is out of scope here and `Longitude`/`Latitude` are empty placeholders. Decision: SPEC-001 hands off depot *addresses* only; coordinate resolution (e.g., zip-centroid lookup against the static location DB) must be settled in SPEC-002's research gate.

**Prior learnings:** none — `.spec/_ledger/` and completed specs do not exist yet; expected for a greenfield repo (learnings-curator).

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

- **Files likely affected** (greenfield — all new):
  - `backend/main.py` — FastAPI app with `POST /api/trucks/generate` route
  - `backend/generators/truck.py` — ordered column-map table (data, not code) and row builder; pure functions, no I/O
  - `backend/schemas/truck_config.py` — Pydantic v2 request/response models (`TruckConfig`, `VolumeSpec` list with unique-name validator, response metadata model); this module is the canonical API contract SPEC-002/003 mirror
  - `backend/requirements.txt` or `pyproject.toml` — pin `fastapi==0.141.1`, `pydantic==2.13.4`
  - `tests/test_truck_generator.py` — unit + golden parity tests
  - `tests/test_truck_api.py` — FastAPI `TestClient` contract tests
  - `fixtures/truck/` — known-good single-depot macro baseline `.truck` sample(s)
- **Files NOT to modify:**
  - Stop file generator code (SPEC-002)
  - Next.js wizard UI (SPEC-003)
  - `.cursor/skills/` Creator kit files
- **Patterns to follow:**
  - Schema-first emitters: deterministic column output from templates, not LLM-generated bytes
  - Port macro column order exactly from brainstorm VBA header list (A1–BX1 equivalents)
  - Build rows as `list[list[str]]` of pre-formatted strings (fixed-decimal costs, uppercase TRUE/FALSE, explicit date text) → `csv.writer(dialect="excel-tab", lineterminator="\r\n")` → bytes
  - Thread `random.Random(seed)` through the generator; no global RNG state
  - Watch 1-based VBA loop indexing when porting Day/Week/Route/Territory cycles
- **Test expectations:**
  - Unit tests for row count formula: `(Σ trucks per depot) × weeks × 7` (single-depot reduces to `territories × weeks × 7`)
  - Unit tests for Day cycle (SU, MO, TU, WE, TH, FR, SA)
  - Determinism test: identical config + seed → identical output bytes
  - Golden parity test: byte-equality against `fixtures/truck/` macro baseline (raw `read_bytes()` comparison, not parsed-CSV comparison)
  - Integration test: generate file → assert 76 headers present → assert required fields non-empty on row 2; API test asserts status 200, `Content-Disposition`, and body/metadata shape
