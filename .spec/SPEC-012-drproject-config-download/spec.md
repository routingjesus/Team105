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
3. **Given** wizard answers that map to `Configuration/Stop` in the template, **when** the file is generated, **then** the following elements are populated from wizard input (falling back to stop-file generator defaults when an alias is unset), and every other template element is passed through unchanged:
   - `Configuration/Stop/ID1` ← `aliases.id1` (default `Store #`)
   - `Configuration/Stop/ID2` ← `aliases.id2` (default `ID2`)
   - `Configuration/Stop/ID3` ← `aliases.id3` (default `ID3`)
   - `Configuration/Stop/Name` ← `aliases.name` (default `Name`)
   - `Configuration/Stop/Address2` ← `aliases.address_2` (default `Address2`)
   - `Configuration/Stop/Contact` ← `aliases.contact` (default `Contact`)
   - `Configuration/Stop/Phone` ← `aliases.phone` (default `Phone`)
   - `Configuration/Stop/Address` ← fixed `Address`
   - `Configuration/Stop/Quantities/Quantity[n]/Name` ← `volumes[n].name` from truck configuration (one `<Quantity>` per named volume)
   Machine-specific path elements (`Preferences/Preprocess/DistanceFile`, `Preferences/RecentFilesList/*`, `Preferences/RecentProjectsList/*`, `Preferences/MergeDirectoryAndFileSettings/*`, `Preferences/DRTrack` credentials) are always emitted empty regardless of wizard input.
4. **Given** a generation request, **when** the API responds, **then** the response follows the existing paired-endpoint contract: `POST /api/drproject-config/generate` returns JSON metadata with base64-encoded file content, and `POST /api/drproject-config/download` returns the raw XML bytes with a `Content-Disposition: attachment; filename="DRProject.config"` header — the filename is always exactly `DRProject.config` (DirectRoute expects that exact name inside the user data directory, unlike the user-facing truck/stop filenames).
5. **Given** a downloaded `DRProject.config`, **when** the user manually copies it into a DirectRoute user data directory configured under File → Preferences and opens DirectRoute, **then** DirectRoute recognizes the directory as a valid project and loads without blocking config errors (manual smoke test, same acceptance style as SPEC-001 AC7 / SPEC-003 AC8).
6. **Given** the wizard UI, **when** the download step renders, **then** the summary/help text clarifies that the file must be copied by the user into the correct DirectRoute user data directory — this application only produces the file for download, it does not (and cannot, from a browser) write directly into an arbitrary local filesystem path.

## Research

Research gate completed 2026-08-05. Owner-supplied golden template received and bundled at `fixtures/drproject-config/DRProject.config` (sanitized; see `fixtures/drproject-config/README.md`).

**Repo precedent confirms this is a known, deliberately deferred gap** (repo-analyst): `DRProject.config` was explicitly out of scope in SPEC-001, SPEC-002, and SPEC-003. This spec is the first to bring it into scope.

**Established contract to mirror, not reinvent** (repo-analyst): `backend/main.py` implements paired `POST /api/{trucks,stops}/generate` + `.../download` endpoints; `components/wizard/download.tsx` renders one download button per artifact. A third artifact adds `/api/drproject-config/{generate,download}` following the identical shape. `DrprojectConfigResponse` mirrors `TruckGenerationResponse`'s `filename` + base64-content fields.

**Owner-supplied template resolves the schema gap** (owner-supplied, repo-analyst): the golden sample is UTF-8 XML with root element `<AppSettings>`. DirectRoute project setup is driven primarily by `<Configuration>` (stop/truck field-name mappings) plus a large `<Preferences>` tree (routing, geocoding, map, upload settings). For the wizard's purposes, only `Configuration/Stop` is user-answer-driven; depot addresses do not appear in this file — the template is about **how DirectRoute labels and interprets stop-file columns**, not where depots live. The substitution map is documented in `fixtures/drproject-config/README.md` and AC 3.

**Alias and volume alignment with existing stop generator** (repo-analyst): `Configuration/Stop/ID1`–`ID3`, `Name`, `Address2`, `Contact`, `Phone` map directly to `AliasConfig` in `backend/schemas/stop_config.py` (`ALIAS_FIELD_MAP`). `Configuration/Stop/Quantities` maps to `VolumeSpec.name` from truck configuration — same names that become stop-file volume columns. Defaults in the bundled template (`Store #`, `Cube`) match `backend/generators/stop.py`'s `COLUMN_ORDER` / golden stop-file header conventions.

**Sanitization requirements for bundled template** (repo-analyst): the owner sample contained machine-specific paths (`RecentFilesList`, `RecentProjectsList`, `DistanceFile`, `MergeDirectoryAndFileSettings`) and encrypted `DRTrack` credentials. These must be cleared in the repo fixture and always emitted empty in generated output — they are environment-specific, not wizard input. The rest of `<Preferences>` (algorithm defaults, geocoding rules, map settings, encrypted preference blobs) passes through verbatim; do not attempt to decode or regenerate DirectRoute's internal encryption (`Q+6cfzNbwl//MD7q8NAG8Q==`-style values).

**XML generation approach** (docs-researcher): load the bundled template with Python's `xml.etree.ElementTree` (stdlib), apply the substitution map as data (element path → value), serialize back to UTF-8 with `encoding="utf-8"` and XML declaration. Do not hand-build XML strings. Structural parity tests compare parsed element trees for non-substituted nodes; raw byte parity is not required for the full file because DirectRoute may tolerate whitespace normalization on the preference blobs.

**Browser sandboxing — manual placement only** (docs-researcher): generate → download → user copies `DRProject.config` into their DirectRoute user data directory. AC 6 documents this in the UI.

**Fixed filename `DRProject.config`** (repo-analyst): hardcode `DRPROJECT_CONFIG_FILENAME = "DRProject.config"` in `backend/main.py`; never derive from user input or `Content-Disposition` parsing.

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
  - `backend/schemas/drproject_config.py` (new) — Pydantic v2 request model accepting `StopConfig` (or a subset: `aliases`, `volumes` from truck context) and `DrprojectConfigResponse` mirroring `TruckGenerationResponse`'s `filename` + base64-content shape
  - `fixtures/drproject-config/DRProject.config` — bundled golden template (sanitized owner sample); substitution map in `fixtures/drproject-config/README.md`
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
  - Structural parity test: generated XML element tree matches `fixtures/drproject-config/DRProject.config` for all non-substituted nodes (parsed-tree comparison, not raw bytes)
  - Field-substitution test: alias fields and volume names from a sample `StopConfig` appear in `Configuration/Stop`
  - Sanitization test: path elements (`RecentFilesList`, `DistanceFile`, etc.) are empty in output
  - API contract test: `POST /api/drproject-config/generate` returns 200 with base64 content and `filename == "DRProject.config"`; `POST /api/drproject-config/download` returns the exact `Content-Disposition` filename
  - Determinism test: identical input produces byte-identical output
