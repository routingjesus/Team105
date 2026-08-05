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

<!-- Codebase investigation: patterns verified, root cause traced, related specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change the set of frequency options exposed in the wizard UI
  unless the root cause requires it (UI already appears to accept these
  values per the user's report).
- Does not address Pattern/Volume/time-window bugs (tracked separately in
  SPEC-007, SPEC-008, SPEC-009).

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
