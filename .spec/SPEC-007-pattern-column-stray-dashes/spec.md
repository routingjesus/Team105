---
id: SPEC-007
title: "Pattern column contains stray dash characters"
category: bug
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

`Pattern1`/`Pattern n` values in the generated stop file include a leading
and trailing `-` around the day codes (e.g. `-MWF-`). The only valid
characters for this column are the day codes themselves: `S`, `M`, `T`,
`W`, `R`, `F`, `A`. The stray dashes make the file non-conformant with
DirectRoute's expected format.

## Acceptance criteria

1. Generated `Pattern1`/`Pattern n` values contain only characters from the
   set `SMTWRFA` — no leading or trailing `-`, and no other characters.
2. Every combination of requested days-of-week produces a pattern string
   with no dash characters anywhere in the value.
3. A test asserts the pattern column matches the regex `^[SMTWRFA]*$` across
   a representative set of generated stops.

## Reproduction

- **Input:** Generate a stop file with any day-of-week pattern selection.
- **Actual output:** `Pattern1` column values look like `-MWF-` (dash before
  and after the day codes).
- **Expected output:** `Pattern1` column values look like `MWF` (day codes
  only, no dashes).
- **Environment:** Local run via `run-local.cmd`, backend stop generator
  (SPEC-002 area).

## Research

- **Root cause confirmed and localized to one function** (repo-analyst):
  `build_pattern1` in `backend/generators/stop.py` (SPEC-002 area) builds a
  fixed-width 7-character string by joining `letter if letter in active else
  "-"` across all of `PATTERN_DAY_LETTERS` (`"SMTWRFA"`, defined in
  `backend/schemas/stop_config.py`). Any scope other than "every day active"
  produces `-` placeholders for inactive days (e.g. `specific_days=["M","W","F"]`
  → `"-M-W-F-"`), which is exactly the stray-dash defect described in the bug
  report.
- **The golden DirectRoute template does not require fixed-width padding**
  (repo-analyst): `fixtures/stop/TEMPLATE_NewConfigStopFile.xls`'s field
  catalog describes `Pattern1` only as "Days that delivery can occur -
  SMTWRFA for each day of the week" with no width or separator requirement,
  and SPEC-002's own AC6 says only "Pattern1 in `SMTWRFA` format" — neither
  source specifies or requires `-` placeholders for inactive days. The fix is
  therefore purely subtractive: emit only the active-day letters, in
  `SMTWRFA` order, with no separator.
- **No other code depends on the padded/fixed-width shape** (repo-analyst):
  `pattern1` is written to exactly one place (`row["Pattern1"]` in
  `build_rows`) and is not indexed by position or length anywhere else in
  `backend/` or `tests/`. The only callers that assumed dash placeholders
  were the unit tests for `build_pattern1` itself
  (`tests/test_stop_generator.py`), which encode the old (buggy) shape as
  their expected values and must be updated alongside the fix, not treated
  as a separate regression risk.
- **No prior learning in the ledger or done specs' `meta.yaml` mentions this
  defect** (learnings-curator): SPEC-002's completion learnings cover
  Frequency/Open1/Close1 correctness but do not mention Pattern1 formatting,
  so this is a net-new finding, not a recurrence of a previously-fixed bug.
- **External/prior-art lanes produced no repo-external signal worth citing**
  (docs-researcher, prior-art-researcher): this is an internal string-
  formatting bug with no framework or library involvement and no external
  precedent needed beyond the owner-supplied golden template already cited
  above; both lanes are covered by the repo-analyst findings above per the
  research gate's graceful-degradation guidance.

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change which days-of-week combinations are selectable in the
  wizard UI, only the formatting of the generated output.
- Does not address Frequency/Volume/time-window bugs (tracked separately in
  SPEC-006, SPEC-008, SPEC-009).

## Error evidence

<!-- (Recommended) Error logs, stack traces, call stacks from the failure. -->

## Root cause analysis

<!-- (Recommended) What introduced the bug, when, and what the fix should address. -->

## Blast radius

<!-- (Recommended) What else could break if this area is touched. -->

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — `build_pattern1`: change the join to emit
    only letters present in `active`, in `PATTERN_DAY_LETTERS` order, instead
    of substituting `-` for inactive days.
  - `tests/test_stop_generator.py` — update the three existing
    `build_pattern1` unit tests that assert the old dash-padded shape
    (`test_build_pattern1_weekday_scope_excludes_weekend`,
    `test_build_pattern1_specific_days`) to expect dash-free output, and add
    the AC3 regression test(s) asserting `^[SMTWRFA]*$` across
    `build_pattern1` outputs and across `build_rows`-generated stop rows.
- **Files NOT to modify:**
  - `backend/schemas/stop_config.py`'s `PATTERN_DAY_LETTERS` constant/order —
    the day-letter set and Sunday-first ordering are correct and unrelated to
    this bug.
  - Wizard UI (SPEC-003) and truck generator (SPEC-001) — this is isolated to
    stop-file Pattern1 rendering.
- **Patterns to follow:**
  - Keep `build_pattern1`'s existing scope-handling branches
    (`specific_days` / `random` / lookup-table scopes) unchanged; only the
    final render line changes from a fixed-width dash-substitution join to a
    filter-then-join over `PATTERN_DAY_LETTERS`.
- **Test expectations:**
  - `build_pattern1("week", ...)` still returns `"SMTWRFA"` (unchanged, no
    dashes were ever present for the all-active case).
  - `build_pattern1("weekday", ...)` returns `"MTWRF"` (no leading/trailing
    dash).
  - `build_pattern1("specific_days", ["M","W","F"], ...)` returns `"MWF"`.
  - A test asserts `re.fullmatch(r"[SMTWRFA]*", pattern)` across
    `build_pattern1` for every `pattern_scope` choice (week, weekday,
    weekend, specific_days including an empty selection, random), satisfying
    AC1/AC2.
  - A test asserts the same regex against the `Pattern1` column of rows
    produced by `build_rows` for a representative generated stop set,
    satisfying AC3.
