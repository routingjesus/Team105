---
id: SPEC-003
title: "Dataset Creation Wizard UI"
category: feature
owner: Tye Lofts
authored_by: automated
---

## Problem statement

The Dataset Creation Wizard needs a **multi-step web UI** that guides users through truck-building and stop-building questions in a single seamless flow — without revealing which file type is being built — then triggers generation and delivers **`.XLSX` + `.TRUCK` downloads**.

This spec is the user-facing capstone deliverable: the demo-ready wizard that orchestrates SPEC-001 (truck API) and SPEC-002 (stop API) into the end-to-end experience described in the Team 105 PRD acceptance criteria.

## Acceptance criteria

1. **Given** a new user opens the app, **when** they start the Dataset Creation Wizard, **then** they are presented with truck-related questions first (weeks, territories, depots, volumes, costs, work rules) with no mention of "truck file" or "stop file".
2. **Given** truck questions are complete, **when** the user advances, **then** stop-centric questions begin automatically with no explicit phase announcement.
3. **Given** all questions are answered, **when** the user reaches the preview step, **then** they see a summary (depots, trucks, stops, volumes, weeks, selection mode) before generation runs.
4. **Given** the user confirms generation, **when** the backend APIs (SPEC-001, SPEC-002) complete, **then** both `.XLSX` and `.TRUCK` files are available for download to the local PC.
5. **Given** a validation error from the backend, **when** generation fails, **then** the UI displays a clear error message and allows the user to correct inputs without losing prior answers.
6. **Given** a successful generation, **when** the user downloads, **then** they receive both files (zip bundle or two separate downloads).
7. **Given** the deployed bootcamp URL, **when** a reviewer walks through the wizard, **then** the full flow from kickoff to download completes in under 3 minutes for a demo scenario (2 depots, 2 weeks, ~20 stops).
8. **Given** generated files from the wizard, **when** imported into DirectRoute, **then** a valid solution is created without exceptions (end-to-end demo acceptance).

## Research

<!-- Deferred — run research gate before marking ready. -->

Investigate before implementation:

- Next.js App Router multi-step form patterns in repo (if any scaffold exists)
- Bootcamp deployment target and environment variables for API base URL
- Whether wizard state lives client-only or persists server-side between phases

## Scope boundaries

- **In scope:** Next.js wizard UI, form validation, phase orchestration (truck Q → stop Q → preview → generate → download), API integration with SPEC-001 and SPEC-002 endpoints, responsive layout suitable for demo.
- **Out of scope:** Truck/stop generation logic (SPEC-001, SPEC-002), static location database management, DRProject.config, user authentication, session persistence across browser restarts (P1), output format selector (OIS/REST).
- **Out of scope:** Researching DR/TP/SP column catalogs — belongs to SPEC-001/002 research.

## User scenarios

- As a **Sales Engineer**, I want a single wizard I can walk a prospect through to generate demo data without explaining file formats.
- As an **Implementation Consultant**, I want to preview depot/truck/stop counts before downloading so I can verify the scenario matches my intent.
- As a **bootcamp reviewer**, I want a deployed URL where I can complete the wizard and download files in one session.

## Non-functional requirements

- Wizard works in Chrome/Edge on bootcamp laptops without plugins.
- Form state preserved when navigating back to prior steps within a session.
- Accessible labels on all form inputs (basic a11y for demo).

## Implementation guidance

- **Files likely affected:**
  - `app/` or `frontend/` — Next.js pages and components
  - `components/wizard/` — step components (TruckQuestions, StopQuestions, Preview, Download)
  - `lib/api.ts` — client calls to truck and stop generation endpoints
  - `lib/wizard-types.ts` — shared TypeScript types mirroring backend schemas
- **Files NOT to modify:**
  - Backend generator logic except API route paths/contracts agreed with SPEC-001/002
  - `.spec/` other than this spec's own files
- **Patterns to follow:**
  - Match repo-instructions.md: Next.js App Router, TypeScript, component colocation under `components/`
  - Question order must match PRD Phase 1 (truck) then Phase 2 (stop) tables
- **Test expectations:**
  - Component tests for form validation on required fields (weeks > 0, at least one depot address, etc.)
  - E2E or integration test: mock API → wizard completes → download triggered (if Playwright/Cypress available; otherwise manual demo script)
