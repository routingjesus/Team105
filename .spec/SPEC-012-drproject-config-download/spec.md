---
id: SPEC-012
title: "DRProject.config generator and download"
category: feature
owner: Cursor Agent                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

DirectRoute requires a `DRProject.config` file to be present inside **each "user data directory"** that a DirectRoute installation has configured under File → Preferences. Today the wizard produces two of the three artifacts an analyst needs to stand up a working DirectRoute environment — the `.TRUCK` truck file (SPEC-001) and the `.XLSX` stop file (SPEC-002) — but `DRProject.config` has been explicitly out of scope in every prior spec (SPEC-001, SPEC-002, SPEC-003) and no generator exists for it.

Analysts currently have to hand-craft or copy a `DRProject.config` from an existing project (e.g. a real project's config, such as one an analyst keeps locally under a path like `...\LAB\Furniture\DRProject.config`) into each new user data directory before DirectRoute will recognize that directory as a valid project. This spec adds a third generated artifact — an XML `DRProject.config` file, built from a known-good template plus the same wizard answers that already drive truck/stop generation — so a generated dataset is a complete, drop-in DirectRoute project folder rather than two of the three required pieces.

## Acceptance criteria

1. **Given** a completed dataset generation (truck + stop steps done), **when** the user reaches the download step, **then** a third download control offers a `DRProject.config` file alongside the existing truck and stop downloads, using the same generate/download pattern already established for those two files.
2. **Given** the generated `DRProject.config`, **when** it is inspected, **then** it is well-formed XML whose structure (root element, section/element names and nesting) matches the owner-supplied `DRProject.config` template byte-for-byte for every element this spec does not intentionally override with wizard input (golden-template parity, mirroring the `.TRUCK` macro-parity precedent from SPEC-001).
3. **Given** wizard answers that have a corresponding field in the template (at minimum: project/dataset name and depot address information already captured during the truck step), **when** the file is generated, **then** those template fields are populated from the user's answers instead of the template's placeholder values, and every other template field/element is passed through unchanged.
4. **Given** a generation request, **when** the API responds, **then** the response follows the existing paired-endpoint contract: `POST /api/drproject-config/generate` returns JSON metadata with base64-encoded file content, and `POST /api/drproject-config/download` returns the raw XML bytes with a `Content-Disposition: attachment; filename="DRProject.config"` header — the filename is always exactly `DRProject.config` (DirectRoute expects that exact name inside the user data directory, unlike the user-facing truck/stop filenames).
5. **Given** a downloaded `DRProject.config`, **when** the user manually copies it into a DirectRoute user data directory configured under File → Preferences and opens DirectRoute, **then** DirectRoute recognizes the directory as a valid project and loads without blocking config errors (manual smoke test, same acceptance style as SPEC-001 AC7 / SPEC-003 AC8).
6. **Given** the wizard UI, **when** the download step renders, **then** the summary/help text clarifies that the file must be copied by the user into the correct DirectRoute user data directory — this application only produces the file for download, it does not (and cannot, from a browser) write directly into an arbitrary local filesystem path.

## Research

Research gate opened 2026-08-05. Repo-analyst and docs/prior-art findings below; this pass surfaces one hard blocker that keeps the spec at `status: research` rather than `ready` (see "Open item" at the end).

**Repo precedent confirms this is a known, deliberately deferred gap** (repo-analyst): `DRProject.config` is named explicitly in the Scope boundaries of SPEC-001 (`.spec/SPEC-001-truck-file-generator/spec.md`), SPEC-002 (`.spec/SPEC-002-stop-file-generator/spec.md`), and SPEC-003 (`.spec/SPEC-003-dataset-creation-wizard-ui/spec.md`) as explicitly out of scope, with no generator, schema, or fixture anywhere in the repo (`backend/generators/`, `backend/schemas/`, `fixtures/` all lack any `drproject`/`config` reference). This spec is the first to bring it into scope.

**Established contract to mirror, not reinvent** (repo-analyst): `backend/main.py` already implements a paired-endpoint pattern per generator — `POST /api/{trucks,stops}/generate` (JSON metadata + base64 file content) and `POST /api/{trucks,stops}/download` (raw bytes + `Content-Disposition`) — and the wizard's `components/wizard/download.tsx` renders one labeled download button per artifact via `lib/api.ts`'s `downloadBase64`/`downloadFile` helpers. A third artifact should add `/api/drproject-config/{generate,download}` following the identical shape rather than a new delivery mechanism. `backend/schemas/truck_config.py`'s `DepotSummary` and the existing `TruckGenerationResponse`/`StopGenerationResponse` are the precedent for how a new `DrprojectConfigResponse` should carry `filename` + base64 content metadata.

**No public schema exists for `DRProject.config` — same situation SPEC-001 was in for the `.TRUCK` macro schema** (docs-researcher, prior-art-researcher): targeted searches turned up no published Trimble/Appian/DirectRoute documentation for a `DRProject.config` XML schema; DirectRoute's public integration docs (Appian file-import/export references) describe `UPL`/order-file/XML-export formats for stop data, not the project-level preferences config. This is a proprietary, undocumented-outside-the-product file, structurally identical to the `.TRUCK` situation SPEC-001 faced: "no public specification exists... the legacy macro output is the de facto schema" (`.spec/SPEC-001-truck-file-generator/spec.md`). SPEC-001 resolved this with an owner-supplied golden macro sample bundled into `fixtures/truck/`; SPEC-002 resolved its own version of this gap (stop column catalog, Frequency semantics) the same way with owner-supplied templates bundled into `fixtures/stop/`. That is the established, repo-proven pattern for closing this exact class of gap.

**Browser sandboxing means "drop the file into the user data directory" cannot be automated — confirmed non-goal, not a missed requirement** (docs-researcher): a web app cannot write to an arbitrary OS filesystem path (e.g. a DirectRoute-configured user data directory) without the user's explicit per-file save action; this is true for the existing `.TRUCK`/`.XLSX` downloads too (they land wherever the browser's download setting points, and the user manually imports them into DirectRoute — see README.md's "Import into DirectRoute" section). `DRProject.config` delivery should follow the exact same convention: generate → download → user manually places the file. AC 6 makes this explicit in the UI so users don't expect automatic placement.

**Fixed filename is a departure from the other two artifacts, and must be handled carefully** (repo-analyst): `TRUCK_FILENAME`/`STOP_FILENAME` in `backend/main.py` are constants the user never overrides, but they're still cosmetic — DirectRoute doesn't care what the truck/stop filenames are. `DRProject.config` is different: DirectRoute looks for that literal filename inside a user data directory, so the backend/download flow must never let a base64-JSON round trip or `Content-Disposition` parsing (see `lib/api.ts`'s `parseContentDispositionFilename`) silently rename it — hardcode `DRPROJECT_CONFIG_FILENAME = "DRProject.config"` analogous to `TRUCK_FILENAME`/`STOP_FILENAME` and never derive it from user input.

**Open item — blocking, must be resolved before this spec can move past `research`:** no actual `DRProject.config` sample/template exists in this repo, and the exact XML schema (root element, section names, which fields are safe to template vs. must stay verbatim, encoding/line-ending conventions) is unknown without one. The user referenced a real local file (a `DRProject.config` from an existing project on their machine) as the intended template source. Per the SPEC-001/SPEC-002 precedent, the owner must supply that file's contents (or a sanitized/anonymized equivalent with no proprietary customer data) so it can be bundled as a golden fixture — e.g. under `fixtures/drproject-config/` — before AC 2/AC 3's exact field list can be finalized and the spec can reach `ready`. Until that sample is supplied, ACs 1, 4, 5, and 6 are implementable as written; ACs 2 and 3 describe the *shape* of the requirement but cannot be made concrete (which elements exist, which are user-input-driven) without it.

## Scope boundaries

- **In scope:** `DRProject.config` XML generation from a bundled golden template plus applicable wizard answers, a paired `POST /api/drproject-config/generate` + `POST /api/drproject-config/download` API following the existing truck/stop contract, a third download control in the wizard's final step, UI copy clarifying manual placement into the DirectRoute user data directory.
- **Out of scope:** Automatically writing/copying the file into any local filesystem path (browser security makes this impossible; the user places the file manually, same as `.TRUCK`/`.XLSX` today) — see AC 6.
- **Out of scope:** Discovering or validating a user's actual DirectRoute "user data directory" path/Preferences configuration — this application has no visibility into the user's local DirectRoute installation.
- **Out of scope:** Multi-user-data-directory orchestration (DirectRoute may have several configured directories) — this spec produces one `DRProject.config` per generated dataset; the user is responsible for placing copies wherever DirectRoute expects one.
- **Out of scope:** Reverse-engineering or documenting the full `DRProject.config` schema beyond what the owner-supplied template exposes — unused/unrecognized template sections are passed through verbatim, not redesigned.

## User scenarios

- As an **Implementation Consultant**, I want the wizard to also hand me a ready-to-use `DRProject.config` so a freshly generated demo dataset is a complete DirectRoute project folder, not two files short of one.
- As a **Sales Engineer**, I want to drop the downloaded `DRProject.config` into a new user data directory alongside the truck/stop files and have DirectRoute recognize the project immediately, without hand-editing an XML file from a previous project.

## Non-functional requirements

- Generation of the `DRProject.config` completes within the same sub-second budget as the existing truck/stop generators (no new I/O beyond reading a small bundled template).
- Output contains no proprietary customer data — template placeholders not covered by user input stay as safe, non-identifying defaults (mirrors the "no proprietary customer data" NFR already in SPEC-001/SPEC-002).
- Output is deterministic given identical inputs (no randomization needed for this file; unlike truck/stop, no `seed` is expected to affect it).

## Implementation guidance

- **Files likely affected:**
  - `backend/main.py` — add `POST /api/drproject-config/generate` and `POST /api/drproject-config/download`, mirroring the existing truck/stop route pairs; add a `DRPROJECT_CONFIG_FILENAME = "DRProject.config"` constant (never derived from user input)
  - `backend/generators/drproject_config.py` (new) — pure XML-emitting function(s): load the bundled template, substitute the fields identified once the golden sample lands, pass everything else through verbatim; no I/O beyond reading the bundled template
  - `backend/schemas/drproject_config.py` (new) — Pydantic v2 request model for whichever wizard answers actually map to template fields (start from `DepotSummary`/project-name-shaped inputs; extend once the template is known) and a `DrprojectConfigResponse` mirroring `TruckGenerationResponse`'s `filename` + base64-content shape
  - `fixtures/drproject-config/` (new) — bundle the owner-supplied golden `DRProject.config` sample here once available, as the template/parity reference (same role as `fixtures/truck/` and `fixtures/stop/`)
  - `components/wizard/download.tsx` — add a third labeled download button following the existing `downloadBase64`/`TRUCK_MIME`-style pattern, plus UI copy for AC 6
  - `lib/api.ts` — add a `generateDrprojectConfig` client call and a `DRPROJECT_CONFIG_MIME` constant (`application/xml` or `text/xml`, confirm against the template's actual encoding once available)
  - `lib/wizard-types.ts` — TS types mirroring the new backend response shape
  - `tests/test_drproject_config_generator.py`, `tests/test_drproject_config_api.py` (new) — unit + API contract tests following `tests/test_truck_generator.py` / `tests/test_truck_api.py` structure
- **Files NOT to modify:**
  - Truck/stop generator, schema, and route code (SPEC-001/SPEC-002) — add new sibling modules, don't fold this into `truck.py`/`stop.py`
  - `.cursor/skills/` Creator kit files
- **Patterns to follow:**
  - Paired `generate` (JSON + base64)/`download` (raw bytes + `Content-Disposition`) endpoints, exactly as `backend/main.py`'s existing truck/stop routes
  - Ordered/data-driven template substitution (not string concatenation or hand-rolled XML building) — same "column map as data, not code" philosophy `backend/generators/truck.py` uses for `.TRUCK` columns, applied to XML elements instead
  - Golden-fixture byte/structure parity testing against a bundled owner-supplied sample, per SPEC-001's `.TRUCK` macro-parity precedent and SPEC-002's stop-template precedent
  - Fixed, hardcoded output filename (`DRProject.config`) — never let it be renamed via user input or `Content-Disposition` parsing, unlike the cosmetic `TRUCK_FILENAME`/`STOP_FILENAME`
- **Test expectations:**
  - Structural parity test: generated XML's element tree matches the bundled template for every non-substituted element (once the template exists)
  - Field-substitution test: wizard-input fields (project/dataset name, depot info) appear correctly in the corresponding XML elements
  - API contract test: `POST /api/drproject-config/generate` returns 200 with base64 content and `filename == "DRProject.config"`; `POST /api/drproject-config/download` returns the exact `Content-Disposition` filename
  - Determinism test: identical input produces byte-identical output (no seed-driven variance expected)
  - **Blocked until the owner-supplied template lands:** the structural-parity and field-substitution tests above need the real sample to write assertions against, same as SPEC-001's golden `.truck` parity test, which shipped with a documented skip (`fixtures/truck/README.md`) until a sample arrived.
