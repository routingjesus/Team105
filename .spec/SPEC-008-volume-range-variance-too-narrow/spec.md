---
id: SPEC-008
title: "Volume range produces fractional values with too-narrow variance"
category: bug
owner: Cursor Agent                      # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

The "range" option for `Volume1`/`Volume n` (varying volumes around a
requested value) generates fractional values (e.g. 11.12 to 12.55) instead
of whole numbers, and the spread is too narrow relative to the requested
value (e.g. requesting a variance around 12 produced a range of only ~1.4
between the min and max). This does not reflect realistic whole-unit volume
counts or a meaningful variance.

## Acceptance criteria

1. When "range" is used for any `Volume n` column, all generated values are
   whole numbers (no decimal component).
2. The generated range's spread reflects the requested variance in a way a
   user would recognize as meaningfully varying (not clustered within ~1
   unit of each other) — exact variance formula to be confirmed during
   research/implementation.
3. A test requests a range around a known base value and asserts all
   generated volumes are integers and the observed min/max spread meets the
   expected variance.

## Reproduction

- **Input:** Request Volume range mode centered on 12.
- **Actual output:** Generated values like 11.12, 12.55 — fractional, and a
  spread that's too tight to look like real variance.
- **Expected output:** Generated values are whole numbers with a wider,
  realistic spread around 12.
- **Environment:** Local run via `run-local.cmd`, backend stop generator
  (SPEC-002 area).

## Research

- The wizard's "range" label maps to `VolumeAnswer.mode == "averaged"`
  (`backend/schemas/stop_config.py`); the UI option text is "Averaged around
  a target" (`components/wizard/stop-questions.tsx`). No column in the golden
  template or schema requires volume values to carry decimals — the fixed
  mode's `25.00` formatting is a display convention, not a real constraint
  (repo-analyst).
- Root cause confirmed directly in `backend/generators/stop.py::_volume_cells`:
  every cell — fixed *and* averaged — was formatted with `f"{value:.2f}"`.
  For averaged mode this always renders a fractional value even when the
  jittered result would otherwise be whole (repo-analyst).
- The narrow-spread report is explained by the ±15% jitter
  (`rng.uniform(-0.15, 0.15)`) combined with small demo sample sizes: the
  *distribution* spans 30% of the target value, but a handful of stops can
  easily sample from the middle of that range and look clustered, matching
  the reported ~1.4-unit spread around a mean of 12 (repo-analyst).
- This mirrors the pattern from a related fix on the same generator
  (`backend/generators/stop.py::selected_stops_from_candidates`,
  SPEC-005): per-row, per-field values are computed once and threaded
  through `row_by_col` — any fix should stay inside `_volume_cells` rather
  than touching `build_rows`'s row-assembly loop (learnings-curator, via
  SPEC-005's completed learnings).
- `Frequency` uses `f"{frequency:g}"` to print whole numbers without a
  trailing `.0` while still allowing genuine fractional values (e.g. `0.5`)
  — that pattern is intentionally *not* reused here, because AC1 requires
  averaged volumes to always be whole numbers, not "whole when the jitter
  happens to land on one" (repo-analyst).
- No prior learnings in `.spec/_ledger/` or completed specs' `meta.yaml`
  cover volume generation specifically (learnings-curator).

## Scope boundaries

- Does not change the "fixed value" volume mode, only the "range"
  (`mode: "averaged"`) mode — fixed-mode cells keep their existing
  `f"{value:.2f}"` formatting.
- Does not change `Frequency`, `FixedTime`, or any other numeric column.
- Exact variance width is an implementation decision (this spec widens the
  jitter from ±15% to ±35% of the requested mean and rounds to the nearest
  whole number, floored at 1), not a fixed external requirement.
- Does not add a UI-visible variance control — the requested mean remains
  the only user-facing input for averaged mode.

## Error evidence

No exceptions or logs — this is a data-quality defect (wrong value shape and
subjectively narrow spread), not a crash.

## Root cause analysis

`_volume_cells` in `backend/generators/stop.py` used one shared formatting
path (`f"{value:.2f}"`) for both `fixed` and `averaged` modes, and used a
fairly narrow ±15% jitter for `averaged` mode. Averaged-mode volumes
represent whole-unit counts (e.g. cartons, pieces) in the target DirectRoute
workflow, so decimal output is never meaningful for that field, and the
narrow jitter made the resulting spread look artificial on typical demo-sized
stop counts.

## Blast radius

Isolated to `_volume_cells`, which is only called from `build_rows` to
populate the dynamic volume columns. No other generator, schema, or API
contract changes. `VolumeAnswer.value` retains its existing `float` type
(unchanged) since the *requested* mean can still be any positive number —
only the *generated* averaged-mode output is rounded.

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` (`_volume_cells`) — round averaged-mode
    output to a whole number and widen the jitter.
  - `tests/test_stop_generator.py` — new `TestVolumeCells` regression tests.
- **Files NOT to modify:**
  - `backend/schemas/stop_config.py` (`VolumeAnswer`) — the requested mean
    stays a `float`; only generated output changes.
  - `components/wizard/stop-questions.tsx` / `lib/build-config.ts` — no UI
    or request-shape changes.
- **Patterns to follow:**
  - Keep the per-answer loop structure in `_volume_cells`; branch on
    `answer.mode` as before.
  - Floor averaged-mode results at 1 (mirrors `eq_targets`'s
    `max(1, round(...))` pattern already used elsewhere in
    `backend/generators/stop.py::build_rows`).
- **Test expectations:**
  - Fixed mode's exact string formatting (`"25.00"`) is unchanged
    (regression guard).
  - Averaged mode over many stops: every cell parses as an integer string
    (no `.`), and `max - min` across a run exceeds a small threshold to
    prove the spread is meaningfully wide, not just technically nonzero.
  - Averaged mode never produces a value below 1, even for a small
    requested mean.
