---
id: SPEC-011
title: "Optional shape and color generation for stops"
category: feature
owner: Cursor Agent                      # git config user.name
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

- `backend/generators/stop.py`'s `COLUMN_ORDER` already reserves `Symbol`
  ("shape") and `Color` slots (after `Latitude`), but `row_by_col` never
  sets them, so every output row renders them blank — the same
  reserved-but-unwired gap SPEC-005 fixed for `Longitude`/`Latitude`.
- Read both golden templates (`fixtures/stop/TEMPLATE_NewConfigStopFile.xls`,
  `TEMPLATE_AnalystStopFile.xls`, `Header Desc.` sheet) directly with
  `xlrd`: `Symbol` = "recommended but not required"; `Color` =
  "recommended but not required, use for enhanced map interaction". Neither
  description enumerates a supported-value list, and scanning the raw
  binary for embedded dropdown/validation strings surfaced only two
  anecdotal sample values already visible in the templates (`Tower` for
  Symbol, `Cyan` for Color) plus a couple more (`Circle`, `Square`, `Red`,
  `green`) from Trimble ImportOrders samples referenced in the format
  ledger — none of these is a complete, authoritative enum.
- Checked `.spec/_ledger/directroute-file-formats.yaml` and every prior
  spec's `meta.yaml` `source:` field: the only DirectRoute field-reference
  doc cited in-repo is a private Notion page (the shared PRD source used by
  SPEC-001/002/003), which is not reachable from this environment (fetch
  times out — Notion requires authentication this environment doesn't
  have). No other DirectRoute schema catalog exists in the repo.
- **Resolved**: the owner located an authoritative DirectRoute reference
  document (an internal supplemental handout, not tracked in this repo)
  containing the complete "Optional Colors" (48 values) and "Optional
  Shapes" (35 values) tables. `backend/schemas/stop_config.py::SHAPE_VALUES`
  / `COLOR_VALUES` were updated to the full authoritative lists before
  merge, superseding the earlier 3-value anecdotal placeholder (which,
  coincidentally, was a subset of the real list). No waiver remains — see
  `meta.yaml` learnings for provenance.
- Reviewed the closest existing "optional stop-level generation toggle"
  pattern: `EqCodeConfig`/`ConsolidationConfig` in
  `backend/schemas/stop_config.py`, wired through `StopConfig`,
  `backend/generators/stop.py::build_rows`, the wizard's "Advanced stop
  options" `<details>` block in `components/wizard/stop-questions.tsx`,
  `lib/wizard-schema.ts`, `lib/wizard-types.ts`, and `lib/build-config.ts`.
  Shape/color generation follows the same shape: no user-supplied value
  list (unlike EQ codes), just an enable flag per field, so a boolean pair
  (`generate_shapes`, `generate_colors`) is simpler than a nested config
  object.
- Truck file (`backend/generators/truck.py`) already always emits blank
  `Symbol`/`Color` for the same reserved-but-unwired reason, but per this
  spec's own scope boundary and AC (stop file only), it stays untouched.

## Scope boundaries

- The authoritative list of supported DirectRoute shapes/colors must be
  sourced from the DirectRoute repo/documentation during research — do not
  invent placeholder values. **Satisfied** (see Research) — the full
  authoritative list was located and used; no waiver remains.
- Does not add shape/color support to the truck file (SPEC-001), only the
  stop file — `backend/generators/truck.py` is not modified.

## User scenarios

- A wizard user filling out stop details wants demo/test datasets that are
  visually differentiated on DirectRoute's routing maps by shape, by
  color, by both, or (default) neither — matching today's unchanged
  behavior when they skip the option.

## Non-functional requirements

- Deterministic given the same `seed`, matching every other stop-file
  randomization (frequency, EQ codes, volumes).
- No new required user input — enabling shapes/colors takes no free-text
  value list from the user (unlike EQ codes), since the value pool is a
  fixed, backend-owned allowlist.

## Implementation guidance

- **Files likely affected:**
  - `backend/schemas/stop_config.py` — add `SHAPE_VALUES`, `COLOR_VALUES`
    tuples (mirroring the `FREQUENCY_VALUES` pattern) and
    `generate_shapes: bool = False`, `generate_colors: bool = False`
    fields on `StopConfig`.
  - `backend/generators/stop.py` — in `build_rows`, when `generate_shapes`
    is set, assign `row_by_col["Symbol"] = rng.choice(SHAPE_VALUES)`, else
    leave unset (blank, via the existing `row_by_col.get(col, "")`
    fallback); same for `Color`/`generate_colors`.
  - `components/wizard/stop-questions.tsx` — two new checkboxes in the
    existing "Advanced stop options" `<details>` block, alongside EQ
    codes/consolidation/aliases.
  - `lib/wizard-schema.ts` — `generateShapes: z.boolean().default(false)`,
    `generateColors: z.boolean().default(false)` on `stopStep`, plus
    `defaultWizardValues` and `stopStepFields` entries (the compile-time
    coverage guard at the bottom of the file will fail the build if either
    is missed).
  - `lib/wizard-types.ts` — `generate_shapes: boolean`,
    `generate_colors: boolean` on the `StopConfig` interface.
  - `lib/build-config.ts` — map `values.generateShapes` /
    `values.generateColors` onto the new `StopConfig` fields in
    `buildStopConfig`.
  - `tests/test_stop_generator.py` — new `TestBuildRows` cases mirroring
    `test_eq_code_assigned_to_a_subset_not_all` (values ∈ allowlist when
    enabled) and a default-off case asserting `Symbol`/`Color` stay blank
    (AC4).
  - `lib/build-config.test.ts` — mirror the "nulls optional blocks" /
    "includes when enabled" pattern used for `eq_code`/`consolidation`.
- **Files NOT to modify:**
  - `backend/generators/truck.py` (truck file is out of scope per AC).
  - `fixtures/stop/TEMPLATE_*.xls` golden templates (read-only schema
    reference).
- **Patterns to follow:** `EqCodeConfig`/`ConsolidationConfig` end-to-end
  wiring (schema → generator → wizard UI → form schema → build-config →
  types), per the Research section above.
- **Test expectations:** backend `pytest tests/test_stop_generator.py`
  covers both-enabled, shapes-only, colors-only, and neither (default,
  AC4-unchanged) cases with allowlist-membership and blank-when-disabled
  assertions; frontend `npm test -- build-config` covers the
  `buildStopConfig` mapping for enabled/disabled toggles.
