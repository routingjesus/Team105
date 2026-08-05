---
id: SPEC-015
title: "Matching colors/symbols per Customer ID for line items"
category: feature
owner: Tye Lofts
authored_by: augmented
---

## Problem statement

When users enable multiple line items (consolidation) and also opt into
shape and/or color generation, each line-item row currently draws its own
independent random symbol/color. For consolidation testing, line items that
belong to the same customer (same Customer ID / stop identity) should share
matching visual markers so related rows are visually grouped on the map.
Today they do not, which undermines the point of multi-line-item demo data.

## Acceptance criteria

1. **Given** consolidation (multiple line items) is enabled **and** shape
   and/or color generation is enabled, **when** stops are generated,
   **then** all line-item rows for the same customer identity share the
   same `Symbol` (when shapes enabled) and the same `Color` (when colors
   enabled).
2. **Given** the same options, **when** comparing two different customers,
   **then** they may receive different symbols/colors (assignment is still
   drawn from the supported lists; uniqueness across customers is not
   required).
3. **Given** consolidation is disabled, **when** shapes/colors are enabled,
   **then** existing per-row SPEC-011 behavior is preserved (one row per
   customer; no regression).
4. **Given** shapes/colors are disabled, **when** consolidation is enabled,
   **then** `Symbol`/`Color` remain blank as today.

## Research

- **Root cause is assignment scope, not missing config** — In
  `build_rows`, `rng.choice(SHAPE_VALUES)` / `rng.choice(COLOR_VALUES)`
  run inside the inner `for line in range(1, lines_per_customer + 1)`
  loop (`backend/generators/stop.py` ~304–307), so each consolidation
  line item draws independently. Per-stop fields already chosen once
  before that loop (`frequency`, time window, `eq_code`,
  `_volume_cells` at ~276–279) share correctly across lines. Fix is
  hoist Symbol/Color to that per-stop scope.
  (repo-analyst, docs-researcher, learnings-curator)

- **Customer identity is outer-loop `SelectedStop` / Store # (ID1)** —
  Consolidation groups by iterating thinned stops, then expanding N
  line items from the same `stop` object. Output `"Store #"` is
  `stop.id1` (location_db `ID1`, Name fallback). `ID2`
  (`ORD-{stop_index+1:04d}-{line:02d}`) is the per-line order id and
  must not be the matching key. No new identity key or schema field is
  needed. (repo-analyst, docs-researcher, learnings-curator)

- **Backend-only; existing toggles suffice** — `generate_shapes` /
  `generate_colors` remain plain booleans on `StopConfig`;
  `ConsolidationConfig` already carries `enabled` +
  `lines_per_customer` (`gt=1`, `le=20`). Wizard wiring
  (`stop-questions.tsx`, `build-config.ts`) already sends both feature
  sets. Matching should be automatic when consolidation and
  shape/color are on — no UX or API contract change.
  (repo-analyst, learnings-curator, docs-researcher)

- **Reuse SPEC-011 allowlists; uniqueness not required** —
  Values stay within `SHAPE_VALUES` (35) / `COLOR_VALUES` (48) in
  `stop_config.py`. Across customers, collisions are fine (AC2);
  industry GIS/map-marker and synthetic-data practice treats
  symbol/color as categorical entity attributes, not globally unique
  markers. Shape and color should remain independently drawn channels
  (separate choices, not one combined draw).
  (learnings-curator, prior-art-researcher, docs-researcher)

- **SPEC-014 (Size) stays independent** — Sibling draft sets static
  `Size=28` when shapes/colors are enabled; it does not change
  Symbol/Color semantics. No hard coupling. Both may touch the same
  `build_rows` region, so parallel PRs need ordinary merge care only.
  (repo-analyst, docs-researcher)

- **Test for within-group equality, not allowlist-only** — Existing
  SPEC-011 tests assert `row[symbol] in SHAPE_VALUES` per row and
  would pass even if consolidation lines differ. Consolidation tests
  already use stride grouping (`rows[i:i+N]`) for shared Address /
  FixedTime / coordinates — extend that pattern for Symbol/Color.
  SPEC-006 learning: subset-membership alone is a false-green risk.
  (learnings-curator, repo-analyst, docs-researcher)

- **RNG stream note (intentional when N>1)** — Hoisting to once-per-stop
  matches the `eq_code` / volume pattern and preserves the exact
  draw count when consolidation is off (`lines_per_customer == 1`),
  so SPEC-011 per-row behavior and seed streams stay intact on that
  path. With consolidation on, fewer `choice` calls per stop shift
  the stream for later stops versus today's buggy multi-draw path —
  acceptable for this fix; within-run determinism for a given seed
  remains. Prefer hoist-and-reuse over hash-bucketing to stay
  consistent with existing generator style.
  (repo-analyst, prior-art-researcher, docs-researcher)

- **Edge case: duplicate Store # across distinct stops** — Grouping is
  structural (outer-loop stop instance), not a global group-by on
  ID1. Two thinned locations that somehow share an ID1 string can
  still receive different symbols/colors. Acceptable; aligns with how
  Address/FixedTime already behave. (repo-analyst)

## Scope boundaries

- Does not change how many line items are generated or consolidation
  config UX.
- Does not require unique symbol/color pairs across all customers.
- Does not address `Size` (see SPEC-014) unless research shows they must
  ship together — prefer independent delivery.
- Customer identity for matching is confirmed: outer-loop selected stop
  / Store # (`stop.id1` / ID1), the same grouping consolidation already
  uses — not ID2.

## User scenarios

- As a Sales Engineer testing consolidation, I enable multiple line items
  plus colors/symbols so every line for Customer A looks the same on the
  map and differs visually from Customer B.

## Non-functional requirements

- Stable within a single generation run: all lines for a customer match.
- Still uses only DirectRoute-supported shape/color values (SPEC-011 lists).

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — in `build_rows`, choose Symbol/Color
    once per outer-loop stop (when the corresponding
    `generate_shapes` / `generate_colors` flag is on), then assign the
    same values into every line-item `row_by_col` inside the
    `lines_per_customer` loop.
  - `tests/test_stop_generator.py` — add consolidation + shape/color
    sharing coverage; keep existing SPEC-011 allowlist tests.

- **Files NOT to modify:**
  - `backend/schemas/stop_config.py` — no new fields; reuse
    `SHAPE_VALUES` / `COLOR_VALUES` and existing bools /
    `ConsolidationConfig`.
  - Wizard / client config path — `components/wizard/stop-questions.tsx`,
    `lib/wizard-schema.ts`, `lib/wizard-types.ts`, `lib/build-config.ts`,
    `lib/api.ts`, `lib/build-config.test.ts` (behavior is automatic).
  - `backend/main.py` — row-count math unchanged.
  - `backend/generators/truck.py`, golden templates under `fixtures/stop/`,
    spatial thinning (`backend/services/spatial.py`).
  - SPEC-014 Size behavior — leave blank Size / Size=28 work to that
    sibling spec.

- **Patterns to follow:**
  - Per-stop shared fields before the line loop in
    `backend/generators/stop.py` (`eq_code`, `_volume_cells`,
    frequency, time window ~276–279): draw once, reuse on every line.
  - Keep the two independent `if config.generate_shapes` /
    `if config.generate_colors` blocks (SPEC-011 bool-toggle pattern);
    do not introduce a nested config object or a combined
    shape×color draw.
  - When flags are off, leave Symbol/Color unset so
    `row_by_col.get(col, "")` keeps blanks.
  - Suggested shape:

    ```python
    # Before inner line loop (per stop):
    symbol = rng.choice(SHAPE_VALUES) if config.generate_shapes else None
    color = rng.choice(COLOR_VALUES) if config.generate_colors else None
    # Inside line loop:
    if symbol is not None:
        row_by_col["Symbol"] = symbol
    if color is not None:
        row_by_col["Color"] = color
    ```

- **Test expectations:**
  - Consolidation on (`lines_per_customer` ≥ 2) + shapes and/or colors
    on → for each stride group of N rows, `len({Symbol}) == 1` and/or
    `len({Color}) == 1`; values still ∈ allowlists.
  - Different customers may share or differ — do not assert global
    uniqueness (optional soft check that at least two groups can
    differ under a seed is fine but not required).
  - Consolidation off + shapes/colors on → existing SPEC-011 per-row
    (one row per stop) behavior preserved; allowlist + blank-other
    column assertions still pass.
  - Shapes/colors off + consolidation on → Symbol/Color remain blank.
  - Reuse stride grouping style from
    `test_consolidation_creates_n_rows_per_customer_with_unique_id2`
    and `test_consolidation_shares_coordinates_across_line_items`.
  - `test_deterministic_output_for_same_seed` should still pass for its
    current config; do not treat cross-version seed streams under
    consolidation+shapes as a regression target.
