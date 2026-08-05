---
id: SPEC-014
title: "Static Size 28 when shapes/colors are generated"
category: feature
owner: Tye Lofts
authored_by: augmented
---

## Problem statement

When Sales Engineers opt into generating shapes and/or colors for stops
(SPEC-011), the `Size` column in the stop file remains blank. Downstream
DirectRoute map rendering expects a size value alongside symbol/color for
usable visual markers. Users need a consistent static size of `28` written
into `Size` whenever shape and/or color generation is enabled, so demo
datasets render correctly without manual post-editing.

## Acceptance criteria

1. **Given** the user enables shape generation, color generation, or both,
   **when** the stop file is generated, **then** every output row has
   `Size` set to the static string/number `28`.
2. **Given** the user leaves both shape and color generation disabled
   (default), **when** the stop file is generated, **then** `Size` remains
   blank (unchanged from current behavior).
3. **Given** shapes and/or colors are enabled, **when** inspecting any
   generated row, **then** existing `Symbol`/`Color` behavior from SPEC-011
   is unchanged — this spec only adds the `Size` value.

## Research

- Stop-file `COLUMN_ORDER` already reserves `Symbol`, `Size`, `Color` as
  adjacent columns after `Latitude`; SPEC-011 wired Symbol/Color via
  `generate_shapes` / `generate_colors` but left `Size` blank — the same
  reserved-but-unwired symptom class as SPEC-005 coordinates, except SPEC-014
  needs a **conditional static write**, not candidate passthrough.
  (`repo-analyst`, `learnings-curator`)
- Confirmed implementation surface: `backend/generators/stop.py::build_rows`
  (Symbol/Color at lines 304–307), flags already on
  `StopConfig` (`generate_shapes: bool = False`, `generate_colors: bool = False`
  in `backend/schemas/stop_config.py`). No new schema, API, or wizard fields
  are required — gate Size on the existing OR of those booleans.
  (`repo-analyst`, `learnings-curator`)
- Golden template `Header Desc.` (verified via `xlrd` on
  `fixtures/stop/TEMPLATE_NewConfigStopFile.xls`) documents `Size` as
  **"in pixels, size of stop icon"** (not required). This closes the prior
  research gap that SPEC-011 never recorded for Size, and confirms the
  column is the map-marker dimension — distinct from `SzRestriction`.
  (`docs-researcher`; local template verification)
- Public Trimble Appian File Import docs list `SFSYMBOL` / `SFCOLOR` for map
  display and describe `SFSIZE` as "size restriction," which does **not**
  reliably map to the stop-file `Size` (pixel) column. Prefer the golden
  template + truck emission patterns over that glossary for this field.
  (`docs-researcher`, `prior-art-researcher`)
- Truck generator always emits `Size` as the string `"12"`
  (`backend/generators/truck.py`); stop Size should likewise emit string
  `"28"` (not int `28`) for generator consistency. Different constants per
  entity type are intentional and in scope. (`repo-analyst`, `docs-researcher`)
- Industry / demo-data practice supports treating Size as part of a
  conditional visual-style bundle: emit a fixed product default when styling
  is opted in, leave blank when styling is off (do not silently default Size
  for unstyled output). OR-trigger (shapes **or** colors) matches map
  renderers that need an explicit size whenever any custom visual attribute
  is present. (`prior-art-researcher`)
- No prior ledger or done-spec learning documents stop-file `Size=28`; the
  value remains a product/SE constant (like truck `12`), not an allowlist
  draw. SPEC-011's shape/color enum research gap is settled and does not
  block Size. (`learnings-curator`, `docs-researcher`)
- Adjacent in-flight SPEC-015 (matching Symbol/Color across consolidation
  line items) explicitly defers Size to SPEC-014; static `"28"` on every
  eligible output row automatically stays consistent across line items with
  no extra coupling. (`repo-analyst`, `learnings-curator`)
- Automated tests can assert exact row values; visual marker correctness in
  DirectRoute 26.x still depends on the existing manual smoke-test path in
  `README.md` (CI cannot close rendering). Product owner confirmed `28` is a
  valid DirectRoute Size value — no further constant validation required.
  (`docs-researcher`, `prior-art-researcher`)

## Scope boundaries

- Does not introduce a user-configurable size control — value is always `28`
  when shapes/colors are on.
- Does not change truck-file `Size` behavior (trucks already emit `12`).
- Does not change when shapes/colors are offered in the wizard UI.

## User scenarios

- As a Sales Engineer generating a visually styled stop file, I want map
  marker size filled automatically so I do not hand-edit `Size` after
  download.

## Non-functional requirements

- Deterministic: every eligible row gets exactly `28`, no RNG.

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — in `build_rows`, immediately after the
    existing Symbol/Color blocks (~304–307), add:
    `if config.generate_shapes or config.generate_colors: row_by_col["Size"] = "28"`.
    When both flags are false, leave Size unset so `row_by_col.get(col, "")`
    keeps the blank cell.
  - `tests/test_stop_generator.py` — extend `TestBuildRows` shape/color cases
    (default / shapes-only / colors-only / both) with `size_idx` assertions.

- **Files NOT to modify:**
  - `backend/schemas/stop_config.py` — flags and allowlists already exist; no
    new Size field or config object.
  - `backend/generators/truck.py` — truck `Size=12` stays unchanged.
  - Wizard / frontend (`components/wizard/stop-questions.tsx`,
    `lib/wizard-schema.ts`, `lib/wizard-types.ts`, `lib/build-config.ts`) —
    no new UI toggle or mapping.
  - `backend/main.py`, `tests/test_stop_api.py`, golden templates under
    `fixtures/stop/` — no contract or template edits.
  - Do not write to `SzRestriction` (different column / semantics).

- **Patterns to follow:**
  - SPEC-011 boolean-flag + adjacent `if` blocks in `build_rows` (raw
    learning: plain booleans, not nested Config).
  - Truck static string Size emission (`"12"`) — emit `"28"` as a string
    literal (inline or a small module-level constant in `stop.py`; no need
    to promote into `stop_config.py` unless preferred for discoverability).
  - Blank-when-unset via existing `row_by_col.get(col, "")` fallback — do
    **not** apply the SPEC-005 three-edit passthrough recipe (Size is not
    sourced from `location_db` / `SelectedStop`).

- **Test expectations:**
  - Extend the four `TestBuildRows` cases at
    `tests/test_stop_generator.py` (~419–461):
    | generate_shapes | generate_colors | Expected Size |
    |-----------------|-----------------|---------------|
    | off | off | `""` |
    | on | off | `"28"` |
    | off | on | `"28"` |
    | on | on | `"28"` |
  - Keep existing Symbol/Color assertions unchanged (AC3).
  - Assert exact `"28"` / `""` (not merely non-blank), matching
    `tests/test_truck_generator.py`'s `assert cell["Size"] == "12"`.
  - Optional: with `ConsolidationConfig` + either visual flag on, every
    line-item row gets `Size == "28"`.
