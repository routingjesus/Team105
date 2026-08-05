---
id: SPEC-011
title: "Optional shape and color generation for stops"
category: feature
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

DirectRoute supports assigning shapes and/or colors to stops for visual
grouping on routing maps, drawn from a fixed list of supported values.
Today the wizard has no way to opt into generating this data, so users who
want visually differentiated demo/test datasets must add it manually after
import.

## Acceptance criteria

1. The wizard asks the user whether they want shapes generated, colors
   generated, both, or neither.
2. When shapes are requested, generated stops are assigned a shape value
   drawn only from DirectRoute's supported shape list.
3. When colors are requested, generated stops are assigned a color value
   drawn only from DirectRoute's supported color list.
4. When neither is requested, the existing output is unchanged (no
   shape/color columns/values added).

## Research

<!-- Codebase investigation: patterns verified, APIs checked, prior specs reviewed.
     This section must be populated before the spec can reach status: ready. -->

## Scope boundaries

<!-- What is explicitly out of scope. -->

- The authoritative list of supported DirectRoute shapes/colors must be
  sourced from the DirectRoute repo/documentation during research — do not
  invent placeholder values.
- Does not add shape/color support to the truck file (SPEC-001), only the
  stop file, unless research shows DirectRoute expects it on trucks too.

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
