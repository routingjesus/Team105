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

Research gate completed 2026-08-04. Framework/UX/library findings come from the
2026-07-30 four-lane pass (repo-analyst, docs-researcher, prior-art-researcher,
learnings-curator); the API-contract findings are refreshed against the now-`ready`
SPEC-002 and the implemented SPEC-001 (open PR on the `SPEC-001-truck-file-generator`
branch). The earlier blocker — "sibling API contracts undefined" — is now resolved.

### Backend API contract (now defined — mirror it, don't invent)

- **The backend is FastAPI + Pydantic v2 under `backend/`, and SPEC-001 is already
  implemented** (open PR, stacked on the `SPEC-001-truck-file-generator` branch); SPEC-002
  is `ready` and stacks on it (repo-analyst, refreshed from SPEC-002's research). SPEC-003
  is a thin client over these APIs and must consume their real contract rather than a
  redefined one.
- **Paired-endpoint file-delivery pattern** established by SPEC-001 and mirrored by SPEC-002:
  `POST .../generate` returns JSON metadata **plus base64-encoded file content**, and
  `POST .../download` returns **raw bytes with `Content-Disposition`**. SPEC-002 exposes
  `POST /api/stops/generate` and `POST /api/stops/download`; by symmetry SPEC-001 exposes
  the truck pair (confirm the exact truck path against `backend/main.py` — inferred
  `/api/trucks/generate` + `/api/trucks/download`).
- **Canonical request/response shapes live in `backend/schemas/truck_config.py`**:
  `DepotSummary` (address/city/state/zip/truck_count), `VolumeSpec` (name/capacity), and
  `TruckGenerationResponse` (weeks, territory_count, depots, volume_names, seed). Stop-side
  shapes are in `backend/schemas/stop_config.py` and **extend** the truck contract (they
  import `DepotSummary`/`VolumeSpec`/`TruckGenerationResponse`, not redefine them). SPEC-003's
  `lib/wizard-types.ts` should mirror these exact shapes.
- **Two files, delivered per-file (no zip needed):** truck output is the tab-delimited
  `.TRUCK`; stop output is the `.XLSX`. Each has its own generate/download pair, so the
  wizard can either decode the base64 from each `generate` response or hit each `download`
  endpoint — favor **two explicit labeled download buttons** (one gesture each) over auto
  dual-download to avoid popup-blocker issues (prior-art-researcher). This settles AC 6.
- **Sequencing is contract-driven:** stop generation consumes the truck config output
  (`TruckGenerationResponse`), so the truck `generate` call must precede the stop `generate`
  call. In the wizard: collect truck answers → call truck generate → collect stop answers →
  call stop generate (passing truck output) → present both downloads. Volume names/depots
  are user inputs captured in the truck phase, so stop-phase questions can be populated
  client-side without waiting on the API; the preview summary can show truck metadata from
  the truck `generate` response.
- **Backend conventions to respect at the boundary:** ASCII-only text validation
  (SPEC-001's `_validate_ascii`) means the wizard should validate/normalize text inputs to
  ASCII before submit to surface errors early; and structured FastAPI 422 errors (see below)
  are the error contract.

### Frontend architecture and framework (2026-07-30 lanes, still valid)

- **The repo is greenfield** — no `package.json`/`tsconfig`/`next.config`/source exists;
  SPEC-003 scaffolds the whole Next.js/TypeScript project, not just wizard components
  (repo-analyst).
- **Build one client-managed wizard** on a single route (e.g. `app/datasets/new/`): a
  `'use client'` component with a step index; keep the page shell a Server Component.
  Route-per-step and Server Actions add persistence/round-trip complexity that fights
  session-local state and opaque binary responses from an external FastAPI backend
  (docs-researcher). This also matches multi-page wizard precedent for branching, gated
  setup flows (prior-art-researcher).

### Form state, validation, and progressive disclosure

- **One React Hook Form instance + `FormProvider` + `zodResolver`.** Keep
  `shouldUnregister: false` so values survive step unmount (satisfies AC 5 + the state NFR).
  Validate the active step on Next via `trigger(stepFields)`, full schema on submit; never
  validate stop fields while on a truck step; don't re-validate on Back; use `mode: onTouched`
  (docs-researcher). Zod schemas are the single source of truth for validation + TS types
  (`z.infer`); compose per-step with `.pick()`/`.merge()`.
- **Hide file types by labeling steps as user tasks** ("Route details" → "Stop details"),
  invisible branching, honest progress ("Step 2 of 4"); don't bury required inputs behind
  collapsed panels (prior-art-researcher; GOV.UK, NN/g). Satisfies AC 1–2.

### Preview, generation, download, errors, a11y, demo hardening

- **AC 3 preview = a "check your answers" summary** grouped by user-facing section with
  Change links returning to the owning step then back to review; outcome-named action
  ("Generate dataset"); WCAG G98 backs review-before-irreversible-action (prior-art-researcher).
- **Download** via `fetch` → guard on `response.ok`/`Content-Type` → `response.blob()` →
  `URL.createObjectURL` → programmatic `<a download>` → `revokeObjectURL`; or decode the
  base64 content from the `generate` response (docs-researcher). Treat generation as an async
  action with determinate progress and a guarded (single-fire) submit (prior-art-researcher).
- **AC 5 error handling:** FastAPI returns 422 `{ detail: [{ loc, msg, type }] }`; map each
  `loc` to a field via RHF `setError(name, { type: 'server', message })`, use
  `setError('root.serverError', …)` for non-field errors, stay on the step, and never
  `reset()` on failure (docs-researcher).
- **API base URL** via `NEXT_PUBLIC_API_BASE_URL` (inlined at `next build`); backend needs
  CORS for the Next origin, or a Next Route Handler can proxy (docs-researcher).
- **A11y baseline:** `<label htmlFor>`/`id`, `aria-invalid` + `aria-describedby` to visible
  (not color-only) errors, submit-time `role="alert"` summary, `aria-current="step"`, focus
  the step heading (`tabindex="-1"`) on transitions, `shouldFocusError`, WCAG 3.3.7 (pre-fill
  reused values) (docs-researcher, prior-art-researcher).
- **Demo hardening:** persist to `sessionStorage` (clear on success); push history per step so
  browser Back decrements the step; determinate progress if generation >~2–3s
  (prior-art-researcher). Supports AC 7.

### Prior learnings

- No prior Creator learnings applied directly to SPEC-003 as of the 2026-07-30 pass
  (learnings-curator, NO-SIGNAL on the local checkout). Note: SPEC-002's later research found
  a `.spec/_ledger/` (`api-contracts.yaml`, `directroute-file-formats.yaml`, `environment.yaml`)
  on SPEC-001's unmerged branch — worth checking that branch's ledger for boundary conventions
  (ASCII validation, Windows `uv`/TLS bootcamp constraint) during implementation.

### Remaining open questions / assumptions (low risk)

1. **Exact truck endpoint path** is inferred (`/api/trucks/...`) by symmetry with SPEC-002's
   stop pair; confirm against SPEC-001's `backend/main.py` at implementation start.
2. **Exact Phase 1/2 question fields** live in the Team 105 PRD in Notion (`meta.yaml` `source`);
   field-level copy/order must be pulled from there, though the field *semantics* are now known
   from SPEC-001/002 (depots, volumes, weeks, territories, costs, work rules; radius/state,
   density, Frequency, time windows, EqCode, consolidation, aliases).
3. **Execution ordering:** SPEC-001 (implemented, unmerged) and SPEC-002 (`ready`) are not yet on
   `main`; SPEC-003 is `parallel_safe: false` and should be built on a branch stacked on the
   SPEC-002 branch (which stacks on SPEC-001), mirroring the established stacking, or after both
   merge. This is a branch-base setup detail, not a spec-definition gap.

Version notes (2026): Next.js 16.x (App Router), Zod 4 (stable), FastAPI validation errors use
HTTP 422; `NEXT_PUBLIC_*` values are frozen at build time.

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

- **Files likely affected / created** (greenfield — scaffold the project; repo-root-relative,
  `kebab-case` filenames per repo rules):
  - Project scaffold: `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `next.config.ts`,
    `.env.example` (documenting `NEXT_PUBLIC_API_BASE_URL`), Prettier + ESLint config
  - `app/layout.tsx`, `app/page.tsx`, wizard route `app/datasets/new/page.tsx` (Server shell)
  - `components/wizard/dataset-wizard.tsx` — `'use client'` orchestrator (step index,
    `FormProvider`, history + `sessionStorage`)
  - `components/wizard/truck-questions.tsx`, `stop-questions.tsx`, `review.tsx`,
    `download.tsx`, `step-indicator.tsx`
  - `lib/wizard-schema.ts` — Zod per-step + combined schemas
  - `lib/wizard-types.ts` — TS types mirroring `backend/schemas/truck_config.py`
    (`DepotSummary`, `VolumeSpec`, `TruckGenerationResponse`) and `backend/schemas/stop_config.py`
  - `lib/api.ts` — client calls to the truck + stop `generate`/`download` endpoints; blob/base64
    download helper
  - `hooks/` — optional extraction of step/state/sessionStorage logic
- **Files NOT to modify:**
  - Backend generator/schema/route code (SPEC-001 `backend/`, SPEC-002 `backend/`) — consume the
    contract, don't edit it
  - `.spec/` other than this spec's own files; the `SPEC-001-*` and `SPEC-002-*` directories
  - `.cursor/skills/` and other Creator kit files
- **Patterns to follow:**
  - `.cursor/rules/repo-instructions.md`: Next.js App Router, TypeScript, `camelCase` vars,
    `PascalCase` components/types, `kebab-case` files, colocation under `components/`, Prettier
  - Consume the real backend contract: paired `POST .../generate` (JSON metadata + base64 content)
    and `POST .../download` (raw bytes + `Content-Disposition`); truck generate before stop
    generate, passing `TruckGenerationResponse` into the stop request
  - Single `useForm` + `FormProvider` + `zodResolver`; `shouldUnregister: false`; per-step
    `trigger()`; `mode: onTouched`; Zod as the single source of validation + TS types
  - Task-labeled steps with invisible truck/stop branching; "check your answers" review with
    Change links; two labeled download buttons (avoid auto dual-download / no client zip)
  - Map FastAPI 422 `detail[].loc` → RHF `setError`; keep step + values on failure (no `reset()`)
  - ASCII-normalize/validate text inputs client-side to match the backend `_validate_ascii` boundary
  - Pull exact Phase 1/2 question fields/order from the Notion PRD (`meta.yaml` `source`)
- **Test expectations** (Vitest/Jest + React Testing Library per repo rules):
  - Per-step validation: `weeks > 0`, ≥1 depot address, required stop fields
  - State preservation on Back navigation (values retained across step unmount)
  - Server-error mapping: a mocked 422 maps `detail[].loc` → field errors, stays on the step,
    preserves entered values
  - API-client contract test: request/response shapes match `TruckGenerationResponse` and the
    stop config schema; download helper handles both base64-in-JSON and raw-bytes responses
  - Integration/E2E (Playwright if adopted, else a documented manual demo script): mock the
    truck+stop APIs → complete wizard → both downloads triggered (AC 4/6); manual end-to-end
    DirectRoute import smoke test for AC 8
- **Contract confirmation before coding `lib/api.ts`:** verify the exact truck endpoint path and
  the JSON envelope of each `generate`/`download` response against SPEC-001's `backend/main.py`
  (the shapes are defined; only the truck route string is inferred here).
