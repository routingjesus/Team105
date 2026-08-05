---
id: SPEC-005
title: "Stop latitude/longitude dropped from generated stop file"
category: bug
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

The generated `stops.xlsx` does not carry over the original stop
latitude/longitude that the source location database (`backend/data/location_db.xlsx`)
resolved for each stop. Users who need to cross-check stop placement, or feed
the file into downstream tooling that expects coordinates, cannot rely on the
generated file for this.

## Acceptance criteria

1. Each row in the generated `stops.xlsx` includes the same latitude and
   longitude that the source location database resolved for that stop address.
2. Latitude/longitude values are present for every stop that successfully
   resolved against the location database (not just a sample).
3. Existing stop-file generation tests are updated/extended to assert
   coordinate columns are populated and match the source DB values.

## Reproduction

- **Input:** Run the wizard end-to-end with a valid depot (e.g. 1216
  Greenbrier Parkway, Chesapeake, VA 23320), generate a stop file.
- **Actual output:** Generated `stops.xlsx` does not contain the original
  latitude/longitude from `location_db.xlsx` for the resolved stops.
- **Expected output:** Generated `stops.xlsx` includes the latitude/longitude
  pulled from `location_db.xlsx` for each stop.
- **Environment:** Local run via `run-local.cmd`, backend stop generator
  (SPEC-002 area).

## Research

<!-- Codebase investigation: patterns verified, root cause traced, related specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change how depot/stop addresses are matched against the location
  database (matching logic itself is out of scope).
- Does not add new columns beyond latitude/longitude carry-through.

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
