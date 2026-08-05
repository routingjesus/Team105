---
id: SPEC-009
title: "Time window generation under-weights realistic business hours"
category: bug
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

Generated stop time windows have decent variance in absolute terms, but the
distribution across that variance isn't realistic: too many stops end up
with windows open after 1700, when in reality few real-world stops are open
that late. The generator should bias the distribution so most stops fall
within 0500–1600, with a small tail after 1700.

## Acceptance criteria

1. Across a representative generated batch, the majority (target
   percentage to be confirmed during research, e.g. ~80-90%) of stop time
   windows fall within 0500–1600.
2. Only a small minority of generated stop time windows extend past 1700.
3. A test generates a large batch of stops and asserts the proportion of
   windows within 0500–1600 versus after 1700 meets the target distribution.

## Reproduction

- **Input:** Generate a stop file with default/typical time-window settings.
- **Actual output:** A disproportionate share of stops have windows open
  after 1700.
- **Expected output:** Most stops have windows between 0500 and 1600; few
  extend past 1700.
- **Environment:** Local run via `run-local.cmd`, backend stop generator
  (SPEC-002 area).

## Research

<!-- Codebase investigation: patterns verified, root cause traced, related specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change the user-facing time-window inputs in the wizard, only
  the underlying generation distribution.
- Exact target percentage split is to be finalized during research, not
  fixed by this draft.

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
