---
id: SPEC-011
title: "Optional shape and color generation for stops"
category: feature
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

DirectRoute supports assigning shapes and/or colors to stops for visual
grouping on routing maps, drawn from a fixed list of supported values.
Today the wizard has no way to opt into generating this data, so users who
want visually differentiated demo/test datasets must add it manually after
import.

## Acceptance criteria

1. The wizard asks the user whether they want shapes generated, colors
   generated, both, or neither.
2. When shapes are requested, generated stops are assigned a shape value
   drawn only from DirectRoute's supported shape list.
3. When colors are requested, generated stops are assigned a color value
   drawn only from DirectRoute's supported color list.
4. When neither is requested, the existing output is unchanged (no
   shape/color columns/values added).

## Research

- **BLOCKING: no authoritative fixed list of DirectRoute-supported `Symbol`
  (shape) or `Color` values exists in any source checked** (repo-analyst,
  docs-researcher, verified directly by the agent). This spec's own scope
  boundary requires sourcing the list "from the DirectRoute repo/
  documentation during research" and forbids inventing placeholder values
  — that source does not appear to exist:
  - The repo's owner-supplied golden template
    (`fixtures/stop/TEMPLATE_NewConfigStopFile.xls`, `Header Desc.` sheet,
    read directly) describes `Symbol` as **"recommended but not
    required"** and `Color` as **"recommended but not required, use for
    enhanced map interaction"** — plain-language notes about optionality,
    not an enumerated value list. `Size` is described as "in pixels, size
    of stop icon" (numeric, not an enum).
  - Public Trimble Appian DirectRoute integration docs (`developer.
    trimblemaps.com/appian-integration/docs/file-import/` and `.../docs/
    web-services/importorders/`) describe `SFSYMBOL`/`symbolField` and
    `SFCOLOR`/`colorField` as free-form **strings**, with only three
    scattered example values across both pages (`Circle`, `Red`, `green`
    — inconsistent casing) and no published enum.
  - `.spec/_ledger/directroute-file-formats.yaml` and prior specs'
    `meta.yaml`/`spec.md` (SPEC-001, SPEC-002) reference an internal
    Notion field-reference doc as the source for other DirectRoute
    constraints (e.g. the truck file's EDate/LDate semantics), but that
    doc is not accessible to this agent and no prior spec's research
    captured a Symbol/Color enum from it.
  - Prior-art precedent from other GIS/mapping tools (OGC SLD point
    symbolizers, Google Maps `SymbolPath`, ALKMaps) offers plausible
    *generic* shape/color vocabularies (`circle`, `square`, `triangle`,
    `star`; `red`, `blue`, `green`, etc.), but these are explicitly
    **not verified as DirectRoute's accepted values** and using them
    would be inventing placeholder data, which the spec's scope boundary
    forbids.
  - **Revised understanding of the premise**: the evidence is more
    consistent with `Symbol`/`Color` being free-text, display-only
    fields (matching the "recommended but not required" framing, and
    consistent with how `ID2`/`ID3`/`Name` aliasing already treats other
    stop-file columns as display text rather than constrained enums —
    see the SPEC-010 ledger entry) than with DirectRoute enforcing a
    closed vendor enum. This contradicts the problem statement's
    "drawn from a fixed list of supported values" framing and is not
    something this agent can resolve without an internal source (the
    Notion field reference, or an empirical export from a live
    DirectRoute instance with known Symbol/Color values set).
- **Columns already exist in the stop file's structure but are never
  populated** (repo-analyst, verified directly). `COLUMN_ORDER` in
  `backend/generators/stop.py` (lines 35–47) already includes `"Symbol"`,
  `"Size"`, `"Color"` after `Latitude`; `build_header()` passes them
  through unaliased; `build_rows()`'s `row_by_col` (lines ~238–256) never
  sets any of the three, so `row_by_col.get(col, "")` always renders them
  blank. AC4 ("no shape/color columns/values added" when neither is
  requested) therefore means **values stay blank**, not that columns are
  removed — removing them from `COLUMN_ORDER` would break golden-template
  column-count parity (an established constraint from SPEC-002).
- **The repo's own enum + optional-generation patterns are otherwise a
  clean fit once a value source exists** (repo-analyst, learnings-
  curator). `FREQUENCY_VALUES` (`backend/schemas/stop_config.py`) is the
  closest template: a fixed backend tuple, a `@field_validator` rejecting
  unknown values, a frontend mirror, and `rng.choice()` per stop
  (`achievable_frequency_values` / `stop.py` lines ~213–231). `EqCodeConfig`
  is the closest template for optional-nested-config wiring (`enabled` +
  `null`-when-disabled through `lib/build-config.ts`), though its
  fraction-based **subset** assignment is a deliberate scope choice for
  that feature, not necessarily right for shape/color (see UX note below).
  SPEC-010's newly-added always-visible-optional-fieldset pattern
  (`components/wizard/stop-questions.tsx`) is the right UI precedent for
  AC1's "asks the user whether..." phrasing — two independent checkboxes
  (generate shapes / generate colors), not a buried advanced toggle and
  not a 4-way radio (prior-art-researcher: industry guidance favors
  independent checkboxes over radio groups when options are
  independently combinable, since two unchecked = neither and both
  checked = both without a redundant explicit "both" option).
- **Open UX question surfaced by research, not resolved**: should a
  shape/color, once enabled, be assigned to every stop (matching AC2/AC3's
  literal wording and the industry default per prior-art research —
  Mockaroo/Gretel-style generators default to 100% coverage for a
  dedicated visual-encoding field) or to a subset via a fraction
  (mirroring this repo's existing `EqCodeConfig` pattern)? The ACs as
  written ("generated stops are assigned a ... value") read as 100%
  coverage; this research recommends that reading, but it is worth
  explicit confirmation since it diverges from the closest in-repo
  precedent (EqCode's fraction).
- **Consolidation interaction not addressed by the current ACs**
  (prior-art-researcher, repo-analyst): when `consolidation` produces
  multiple line-item rows for one physical stop (see
  `test_consolidation_creates_n_rows_per_customer_with_unique_id2`),
  should shape/color be drawn once per physical stop and shared across
  its line items (matching how `Address`/`FixedTime` are already shared
  across consolidated rows), or drawn independently per row? Industry
  precedent (synthetic-data tools with referential integrity) favors
  once-per-entity; this spec's ACs don't currently say either way.

## Scope boundaries

<!-- What is explicitly out of scope. -->

- The authoritative list of supported DirectRoute shapes/colors must be
  sourced from the DirectRoute repo/documentation during research — do not
  invent placeholder values.
- Does not add shape/color support to the truck file (SPEC-001), only the
  stop file, unless research shows DirectRoute expects it on trucks too.

## User scenarios

<!-- (Recommended) Who uses this and how — user stories, journeys, or scenario descriptions. -->

## Non-functional requirements

<!-- (Recommended) Performance, security, accessibility, or other cross-cutting concerns. -->

## Implementation guidance

<!-- (Recommended) File paths to modify, patterns to follow, test expectations.
     Use repo-root-relative paths for repo files, and describe local-only artifacts
     generically instead of pasting machine-specific paths like `/home/...` or `/Users/...`. -->

- **Files likely affected:**
- **Files NOT to modify:**
- **Patterns to follow:**
- **Test expectations:**
