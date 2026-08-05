---
id: SPEC-010
title: "Prompt for ID2/ID3 column alias names"
category: feature
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

The stop file's `ID2` and `ID3` columns are technical names that may not
mean anything to the end user or downstream reviewers. Users want the
option to rename these columns to something meaningful (e.g. "Customer ID",
"Route Zone") when generating a dataset, without being forced to use the
raw technical name.

## Acceptance criteria

1. The wizard prompts the user for an optional alias for the `ID2` column
   and an optional alias for the `ID3` column.
2. If the user provides an alias, the generated stop file uses that alias
   as the column header instead of the technical name.
3. If the user leaves an alias blank, the generated stop file falls back
   to the existing technical column name (`ID2`/`ID3`) — no behavior change
   for users who skip this.
4. The alias is a display-only rename — the underlying data/values in the
   column are unaffected.

## Research

<!-- Codebase investigation: patterns verified, APIs checked, prior specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not add aliasing for any column other than `ID2`/`ID3`.
- Does not change the API contract's field names, only the exported
  file's column headers (exact mechanism to confirm during research).

## User scenarios

<!-- (Recommended) Who uses this and how — user stories, journeys, or scenario descriptions. -->

## Non-functional requirements

<!-- (Recommended) Performance, security, accessibility, or other cross-cutting concerns. -->

## Implementation guidance

<!-- (Recommended) File paths to modify, patterns to follow, test expectations.
     Use repo-root-relative paths for repo files, and describe local-only artifacts
     generically instead of pasting machine-specific paths like `/home/...` or `/Users/...`. -->

- **Files likely affected:**
- **Files NOT to modify:**
- **Patterns to follow:**
- **Test expectations:**
