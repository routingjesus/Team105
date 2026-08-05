---
id: SPEC-006
title: "Frequency values collapse to 1 instead of populating fractional patterns"
category: bug
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

Requested fractional stop frequencies (e.g. 0.5 for "every other week" or
"2x per month") are not making it into the generated stop file — every stop
shows a `Frequency` of `1` regardless of what was requested. Users cannot
generate realistic biweekly/monthly delivery patterns.

## Acceptance criteria

1. When a user requests a mix including fractional frequencies (e.g. 0.5),
   the generated `stops.xlsx` contains stops with `Frequency` values other
   than `1`, matching the requested distribution.
2. Frequency values in the output are limited to the set of values the
   generator supports/validates (e.g. 0.5, 1, and any other supported
   values) — no silently-clamped or defaulted values.
3. A test exists that requests a batch including 0.5-frequency stops and
   asserts the output contains stops with `Frequency == 0.5`.

## Reproduction

- **Input:** Request a stop batch where some percentage of stops should have
  a frequency of 0.5 (every other week / 2x per month).
- **Actual output:** All generated stops show `Frequency` of `1`.
- **Expected output:** The requested proportion of stops show `Frequency`
  of `0.5` (or other requested fractional value).
- **Environment:** Local run via `run-local.cmd`, backend stop generator
  (SPEC-002 area).

## Research

Traced the full path from wizard input to generated `stops.xlsx` and could
not reproduce a collapse-to-`1` defect anywhere in the current codebase:

- `backend/generators/stop.py::build_rows` computes `frequency =
  rng.choice(achievable)` once per stop from `achievable_frequency_values`
  (`backend/generators/stop.py:99-114`), which passes through any requested
  value `>= 1` unconditionally and passes through sub-1 values whenever
  `1/value <= config.weeks`. With the wizard's default `weeks: 2`
  (`lib/wizard-schema.ts:264`), a request for `[1, 0.5]` keeps both values
  achievable (`cycle_weeks = 2 <= weeks = 2`).
- Ran `build_rows` directly with `frequency_values=[1, 0.5]`, `weeks=4`,
  `seed=5` against `fixtures/stop/sample_location_db.xlsx`: output contains
  both `0.5` and `1` values (`['0.5','0.5','1','0.5','1','1','1','1','0.5',
  '0.5']`). Also verified `frequency_values=[0.5]` alone (single fractional
  value, `weeks=2` and `weeks=4`) — output is `0.5` for every row.
- Ran `generate_stop_file` end-to-end and re-read the produced `.xlsx` with
  `pandas.read_excel` (not just the in-memory row list) — the `Frequency`
  column round-trips as `[0.5, 0.5, 1.0, 0.5, 1.0, 1.0, 1.0, 1.0, 0.5, 0.5]`,
  ruling out an Excel-writer/number-formatting defect.
- Hit the real FastAPI endpoint (`POST /api/stops/generate`) via
  `TestClient` with the exact JSON shape the wizard sends
  (`frequency_values: [1, 0.5]`, `stop_count: 30`), decoded the base64
  `stop_file_base64`, and confirmed a real mix: `1.0` × 20, `0.5` × 10.
  This rules out a request/response (pydantic/JSON) round-trip defect.
- Checked the wizard request builder (`lib/build-config.ts::buildStopConfig`)
  and checkbox UI (`components/wizard/stop-questions.tsx`) — `frequency_values`
  passes through as a plain number array with no transformation that could
  drop or coerce fractional values; `FREQUENCY_VALUES`/`FREQUENCY_LABELS`
  (`lib/wizard-types.ts:157-173`) mirror the backend's `FREQUENCY_VALUES`
  tuple exactly.
- Ran the full existing suite (`pytest tests/` — 83 passed, 2 skipped) and
  the targeted generator suite (`pytest tests/test_stop_generator.py` — 30
  passed); no failing or skipped test hints at this defect.
- Git history shows a single commit for the stop generator
  (`08a3603`, SPEC-002) — no intervening fix landed that would explain a
  "since-fixed" defect.

**Conclusion:** the reported collapse-to-`1` behavior does not reproduce
against the current codebase across the generator function, the full HTTP
API round-trip, and the wizard's request-building code. The one concrete
gap found is test coverage: the existing
`test_frequency_values_come_from_requested_subset`
(`tests/test_stop_generator.py:235`) only asserts `seen <= set(frequency_values)`
(a subset check), which would still pass even if `0.5` never actually
appeared — it does not assert AC3's specific claim that `0.5` is present.
This spec proceeds as a regression-coverage add per AC3, closing the gap
that let a report like this go unverified; no production code change is
scoped because no defect was found to fix. If the defect recurs, likely
causes to check first are environment-specific: a stale/pre-SPEC-002
deployment, a different `location_db`, or a `weeks` value too small for the
requested fractional cadence (which currently raises
`FrequencyConsistencyError`, not a silent collapse to `1` — also worth
confirming against whatever error/behavior the user actually observed).

## Scope boundaries

- Does not change the set of frequency options exposed in the wizard UI
  unless the root cause requires it (UI already appears to accept these
  values per the user's report).
- Does not address Pattern/Volume/time-window bugs (tracked separately in
  SPEC-007, SPEC-008, SPEC-009).
- Does not modify `backend/generators/stop.py` or
  `backend/schemas/stop_config.py` production logic — research found no
  reproducible defect in the current codebase (see Research). Scope is
  limited to adding the regression test AC3 calls for.

## Error evidence

None available — no stack trace or error log was provided with the report,
and the defect does not reproduce locally (see Research).

## Root cause analysis

No root cause identified: `achievable_frequency_values`,
`build_rows`, the `/api/stops/generate` endpoint, and the wizard's request
builder were all traced and each behaves correctly for fractional frequency
values under the scenarios tested (see Research for exact repro attempts).

## Blast radius

Isolated — the only change is a new/strengthened assertion in
`tests/test_stop_generator.py`. No production code path is touched.

## Implementation guidance

- **Files likely affected:** `tests/test_stop_generator.py` (strengthen
  `test_frequency_values_come_from_requested_subset` or add a new test to
  explicitly assert `0.5` is present in the output, per AC3).
- **Files NOT to modify:** `backend/generators/stop.py`,
  `backend/schemas/stop_config.py`, `lib/build-config.ts`,
  `components/wizard/stop-questions.tsx` — no defect found in any of these;
  do not speculatively refactor them.
- **Patterns to follow:** existing `TestBuildRowsPopulatesRequiredFields`-style
  tests in `tests/test_stop_generator.py` that build a `base_config`,
  `select_candidates`, then `build_rows` with a fixed `rng`/seed for
  deterministic assertions.
- **Test expectations:** a test requesting `frequency_values` including
  `0.5` asserts the generated rows' `Frequency` column contains `0.5`
  (not just that all values are a subset of the requested set).
