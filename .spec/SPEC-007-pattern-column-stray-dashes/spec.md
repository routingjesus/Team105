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

<!-- Codebase investigation: patterns verified, root cause traced, related specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

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

<!-- (Recommended) File paths to modify, patterns to follow, test expectations.
     Use repo-root-relative paths for repo files, and describe local-only artifacts
     generically instead of pasting machine-specific paths like `/home/...` or `/Users/...`. -->

- **Files likely affected:**
- **Files NOT to modify:**
- **Patterns to follow:**
- **Test expectations:**
