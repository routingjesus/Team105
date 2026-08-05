---
id: SPEC-008
title: "Volume range produces fractional values with too-narrow variance"
category: bug
owner: Tye Lofts                         # git config user.name
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

<!-- Codebase investigation: patterns verified, root cause traced, related specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change the "fixed value" volume mode, only the "range" mode.
- Exact variance/spread algorithm is an implementation decision to
  finalize during research, not fixed by this draft.

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
