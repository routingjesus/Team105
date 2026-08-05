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

- **Root cause confirmed and live-verified: silent horizon filtering, not a row-assembly drop** (repo-analyst): `Frequency` has been correctly wired into `row_by_col` since SPEC-002 (`backend/generators/stop.py:261`, `"Frequency": f"{frequency:g}"`) — this is *not* the same failure mode as SPEC-005's lat/long omission. The actual cause is `achievable_frequency_values()` (`backend/generators/stop.py:99-114`), called from `build_rows()` at line 217: for any requested value `< 1`, it computes `cycle_weeks = 1 / value` and drops the value unless `cycle_weeks <= weeks`. With the reported repro (`frequency_values=[1, 0.5]`, `weeks=1`), `0.5` needs a 2-week cycle and is silently dropped, leaving `achievable = [1.0]`, so `rng.choice(achievable)` at line 235 can only ever return `1` — no error is raised (the only guard is an empty-list check at lines 218-221). Live verification against `fixtures/stop/sample_location_db.xlsx` (`frequency_values=[1, 0.5]`, `stop_count=20`, `seed=5`) confirmed: `weeks=1` → 20/20 stops at `1`; `weeks=2` or `weeks=4` → a real 11/9 mix of `1`/`0.5`. This directly violates AC #2 ("no silently-clamped or defaulted values").
- **Full call chain traced end-to-end, no other hop drops or coerces the value** (repo-analyst): wizard UI (`components/wizard/stop-questions.tsx:54-60,156-171`) → form defaults (`lib/wizard-schema.ts:77,282`, default `[1]` only if nothing is checked) → `buildStopConfig()` (`lib/build-config.ts:62,76`, passes `weeks` and `frequency_values` through unchanged) → `StopConfig` schema (`backend/schemas/stop_config.py:17,156-169`, `frequency_values: list[float]` with a subset-membership validator against `FREQUENCY_VALUES = (7,6,5,4,3,2,1,0.5,0.25,0.125,0.083,0.077)`, no default, no coercion, no `ALIAS_FIELD_MAP` entry) → `achievable_frequency_values()` → `rng.choice()` → `row_by_col["Frequency"]` → `to_excel()`. No `int()`/`round()` truncation, no hardcoded `"1"`, no Pydantic default/coercion, and no `truck.py` involvement (it has no frequency concept) anywhere in the chain.
- **Library-level coercion ruled out by documentation** (docs-researcher): Pydantic v2's `float`→numeric handling would raise on a bad type rather than silently round `0.5` to `1` (and this schema uses plain `list[float]`, not `Literal`/`int`, so no coercion path exists); `int()`/`round()` truncate `0.5` toward `0`, not `1`, and neither appears in the generator; pandas/xlsxwriter write Frequency as a pre-formatted string (`f"{frequency:g}"`) before `to_excel()`, and xlsxwriter does not coerce string cells to numbers unless `strings_to_numbers` is explicitly opted into (it isn't here) — ruling out a write-path cause.
- **Existing tests pass even when the bug is present, because they only assert subset membership, not distribution fidelity** (repo-analyst, prior-art-researcher): `test_frequency_values_come_from_requested_subset` (`tests/test_stop_generator.py:250-256`) asserts `seen <= set(base_config.frequency_values)`, which is satisfied even when every single row is `1`. `TestAchievableFrequency` (`tests/test_stop_generator.py:111-125`) unit-tests the filter function itself but never exercises the `weeks=1` + `[1, 0.5]` combination end-to-end. No test anywhere asserts `0.5` actually appears in output (AC #3's gap). This mirrors a documented lesson from this same generator: "column present ≠ value populated" bugs are only caught by explicit AC-by-AC assertions, not incidental green tests (SPEC-002 meta.yaml, corroborated by SPEC-005's research) — subset-membership checks are exactly the kind of test that erodes into a no-op (prior-art-researcher: stochastic/distribution tests degrading to non-empty/in-range checks is a well-documented failure pattern in synthetic-data tooling).
- **This is a distinct bug class from SPEC-005's row-assembly drop, but the regression-test philosophy from that fix still applies** (learnings-curator): the ledger's row-assembly passthrough lesson (`.spec/_ledger/directroute-file-formats.yaml`) and SPEC-002's Open1/Close1 falsy-zero lesson both establish "assert exact expected values, not just presence/subset" as the standing test pattern for this generator — directly applicable to writing SPEC-006's new coverage. No prior learning documents this exact failure mode (frequency horizon-filtering); this is a new class of bug for the ledger.
- **Recommended test shape: deterministic seeded assertion, not a flaky statistical check** (prior-art-researcher): use a fixed seed with `weeks >= 2` and `frequency_values=[1, 0.5]` at a large-enough `stop_count` (e.g. 20+) and assert `0.5` is present in the output `Frequency` column — following the existing seeded-test convention in this file rather than a large-N statistical test, since small-to-medium `stop_count` makes chi-squared/proportion-tolerance checks unreliable.
- **Open scoping question, resolved as out of scope per this spec's own boundaries** (repo-analyst): there is no UI affordance today for a "% mix" (e.g. "50% at 0.5") — the wizard only offers checkboxes for which values *may* appear, sampled uniformly via `rng.choice()`. The silent-filtering bug is orthogonal to this product question and is fully fixable in the backend; this spec's existing scope boundary ("does not change wizard UI unless the root cause requires it") holds, since the root cause and fix are entirely server-side.

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change the set of frequency options exposed in the wizard UI
  unless the root cause requires it (UI already appears to accept these
  values per the user's report).
- Does not address Pattern/Volume/time-window bugs (tracked separately in
  SPEC-007, SPEC-008, SPEC-009).

## Error evidence

No exceptions or logged errors — this is a silent data-fidelity bug. `achievable_frequency_values()` only raises when the filtered list is empty (`backend/generators/stop.py:218-221`); when at least one requested value survives filtering (as `1` always does, since it's never `< 1`), the function returns successfully with a shrunken list and no warning. Confirmed via direct interpreter run: `achievable_frequency_values([1, 0.5], weeks=1)` returns `[1.0]` silently.

## Root cause analysis

Introduced by SPEC-002's original design: `achievable_frequency_values()` was written to keep frequency selections "consistent with routing weeks" (`.spec/SPEC-002-stop-file-generator/spec.md` AC #5) by dropping sub-weekly values that don't fit the routing horizon — e.g. `0.5` (biweekly) requires `weeks >= 2`. This filtering is reasonable in principle, but it fails silently: when a user's `weeks` value is too short for their requested fractional frequencies, the generator quietly produces a batch where every stop gets the one remaining value (`1`) instead of surfacing that the request couldn't be honored as specified. The bug is the *silence*, not the filtering logic itself — AC #2 requires "no silently-clamped or defaulted values," which the current behavior violates whenever `achievable` ends up as a strict subset of the requested `frequency_values`.

## Blast radius

Isolated to `backend/generators/stop.py`'s frequency-selection path (`achievable_frequency_values()` and its call site in `build_rows()`) plus test coverage in `tests/test_stop_generator.py`. `backend/generators/truck.py` has no frequency concept and is unaffected. `backend/schemas/stop_config.py` may optionally gain a cross-field validator (`frequency_values` vs `weeks`) if the fix is implemented as upfront validation rather than a generation-time warning/error — either approach stays within this one schema/generator pair. No frontend changes are required for the fix itself (see Research's scoping note); an optional, non-required frontend consistency hint is listed below for completeness only.

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — `achievable_frequency_values()` (lines 99-114) and its call site in `build_rows()` (lines 217-221): when the filtered `achievable` list is a strict subset of the requested `frequency_values` (not just when it's empty), raise a clear validation error (e.g. `ValueError` surfaced as a 4xx via the existing API error path) naming which requested values don't fit the given `weeks`, rather than silently proceeding with the reduced set. Confirm how `backend/main.py`'s stop endpoint already converts `ValueError` to an HTTP error (it delegates to `generate_stop_file`/`select_candidates`, per SPEC-005's blast-radius notes) so the new error follows the same convention.
  - `tests/test_stop_generator.py` — add a test that builds a config with `frequency_values=[1, 0.5]` and `weeks>=2` (a seed and `stop_count>=20`, following the existing seeded-test convention in this file) and asserts `0.5` appears in the generated `Frequency` column; add a second test asserting the new error/rejection behavior when `weeks=1` is combined with `frequency_values=[1, 0.5]` (i.e. the AC #2 "no silent clamping" case). Extend `TestAchievableFrequency` (lines 111-125) if the fix changes that function's signature or return contract.
- **Files NOT to modify:**
  - `backend/generators/truck.py` — no frequency logic; unrelated to this bug.
  - `backend/main.py` — thin wrapper; picks up the fix automatically once `stop.py`/`stop_config.py` raise clearly.
  - `backend/services/spatial.py` — unrelated to frequency selection.
  - `lib/api.ts`, `lib/build-config.ts` — the `frequency_values`/`weeks` mapping to the backend is already correct; no wiring bug exists on the frontend.
- **Patterns to follow:**
  - Error-surfacing: match the existing validation-error convention already used for `frequency_values_known()` in `backend/schemas/stop_config.py:156-169`, which raises `ValueError` with a message naming the offending value(s) — the new "unfit for weeks" case should read similarly (name the requested values that don't fit, and the `weeks` value that was given).
  - Regression-proofing: assert the *specific* requested fractional value appears in output (equality/membership on the real rendered `Frequency` cell), not just that output is non-blank or a subset of allowed values — this generator's prior bugs (Open1/Close1 falsy-zero, SPEC-002; lat/long passthrough, SPEC-005) were both only caught by exact-value assertions, and the current frequency test's subset check is the same class of gap.
  - Seeded determinism: use a fixed `seed` and adequately large `stop_count` (20+) rather than a statistical/proportion-tolerance check, consistent with existing tests in `tests/test_stop_generator.py`.
- **Test expectations:**
  - A new test proves `Frequency == 0.5` appears in generated output when requested with a compatible `weeks` value (directly satisfies AC #1 and AC #3).
  - A new test proves the generator rejects/errors (rather than silently degrading) when requested frequencies are incompatible with `weeks` (directly satisfies AC #2).
  - Existing `test_frequency_values_come_from_requested_subset` and `TestAchievableFrequency` continue to pass unmodified unless the fix changes `achievable_frequency_values()`'s contract, in which case update them alongside the fix.
