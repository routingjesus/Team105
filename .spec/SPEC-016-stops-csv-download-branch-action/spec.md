---
id: SPEC-016
title: "CSV stops download with Branch and Action columns"
category: feature
owner: Tye Lofts
authored_by: augmented
---

## Problem statement

On the final download page, users can download the generated stops workbook
(`.xlsx`) but not an equivalent `.csv`. Some DirectRoute / OIS workflows
need CSV with two leading operational columns: a user-supplied `Branch`
name as the first column, and an `Action` column as the second. Most rows
should be `Modify`; approximately 10% should be `Delete`. Without this,
users must manually convert and annotate the stop file before import.

Reference format inspiration: an OIS stop template (`Template_OIS_Stop.xls`
style) — use as a column/layout reference during research; do not hard-code
machine-local paths into the product.

## Acceptance criteria

1. **Given** a completed dataset generation, **when** the user is on the
   final download page, **then** they are offered an option to generate /
   download a stops `.csv` in addition to the existing stops `.xlsx`.
2. **Given** the user chooses the CSV option, **when** prompted, **then**
   they must provide a non-empty `Branch` name before the CSV is produced.
3. **Given** a generated CSV, **when** inspecting columns, **then** column
   1 is `Branch` (every data row = the user-supplied branch name) and
   column 2 is `Action`, followed by stop content that matches the
   generated stops `.xlsx` (same rows and remaining columns/values,
   including aliased headers from `build_header`).
4. **Given** a generated CSV with N ≥ 1 data rows, **when** counting
   `Action` values, **then** exactly
   `k = min(N, max(1, round(0.1 * N)))` rows are `Delete` and the
   remaining `N − k` rows are `Modify`. Delete row indices are chosen with
   `random.Random(config.seed).sample(range(N), k)` on a dedicated RNG
   instance created after stop rows are materialized (not sharing the
   `build_rows` RNG stream). Identical `StopConfig` + seed + Branch →
   identical CSV bytes.
5. **Given** the user declines or skips the CSV option, **when** finishing
   the wizard, **then** existing truck / stop `.xlsx` / DRProject.config
   downloads remain available and unchanged.

## Research

Research gate completed 2026-08-05.

**Additive fourth download artifact, not a replacement** (learnings-curator,
repo-analyst): SPEC-012 established the download page as a multi-artifact
surface (truck `.TRUCK`, stops `.xlsx`, `DRProject.config`) via paired
`generate`/`download` endpoints and one button per artifact in
`components/wizard/download.tsx`. SPEC-016 adds a stops CSV beside the
existing stops `.xlsx` without changing truck, xlsx, or DRProject paths
(AC5).

**Server-side, on-demand CSV from the same row builder** (repo-analyst,
docs-researcher, prior-art-researcher, learnings-curator): Stops are built
in `backend/generators/stop.py` (`build_header` / `build_rows` /
`generate_stop_file`). The frontend has no xlsx parser dependency.
Branch is unknown until the user acts on the download page, so pre-baking
CSV into the initial `/api/stops/generate` response is wrong. Preferred
shape: paired `POST /api/stops-csv/{generate,download}` that accepts
`StopConfig` plus a non-empty `branch` string, regenerates rows with the
same seed (xlsx parity), prepends Branch/Action, and returns CSV
(base64 JSON and/or raw bytes). Client-side conversion of
`stop_file_base64` is rejected — fragile type coercion and no SheetJS in
`package.json`.

**Plumb `StopConfig` into the download step** (repo-analyst): Today
`dataset-wizard.tsx` keeps only generation responses on the download step;
`StopConfig` is discarded after `generateStops`. On-demand CSV needs the
config (plus Branch). Pass `stopConfig` into `Download` (store it on the
generation result or rebuild via `buildStopConfig`). Do not persist Branch
into wizard form / `use-wizard-persistence` — it is download-time only.

**OIS stop template confirms Branch/Action as required leading columns**
(repo-analyst [inline verification], docs-researcher, prior-art-researcher):
Inspection of an OIS stop template shows sheet `Stop File` headers
starting `Branch`, `Action`, then stop columns; `Header Desc.` marks both
required. Action vocabulary is `Add` / `Modify` / `Delete` with guidance
to use Modify in lieu of Add. Sample rows use a repeated Branch literal
and include both Modify and Delete. Public Trimble OIS docs list Branch
and Action as optional import fields (Action: Add, Modify, Delete, Delete
All) but do not document column order — the template is the layout
authority. Full OIS column-set parity (e.g. `EstShipDate`) remains out of
scope; this spec prepends Branch/Action to the wizard’s existing stop
column set.

**CSV dialect: `utf-8-sig` + `csv.excel` (CRLF, QUOTE_MINIMAL)**
(docs-researcher, prior-art-researcher): Python `csv.excel` uses comma,
`QUOTE_MINIMAL`, `\r\n`. Encode with `utf-8-sig` so Excel on Windows
double-click-opens UTF-8 correctly (Microsoft UTF-8 CSV guidance; Python
codecs docs). MIME `text/csv` (optionally `charset=utf-8`). Prefer
`csv.writer` over pandas `to_csv` defaults (no BOM; `os.linesep` may be
LF on Linux). Addresses with commas need proper quoting — do not
hand-build CSV strings. Open risk: some machine importers dislike BOM;
if OIS rejects BOM in smoke testing, document a follow-up — Excel-first
default stays `utf-8-sig`.

**Delete selection rule locked to eq_code-style exact count**
(repo-analyst, docs-researcher, learnings-curator, prior-art-researcher):
`backend/generators/stop.py` already does
`count = max(1, round(len(stops) * fraction))` then `rng.sample` for EQ
codes. Adopt the same math for Action with fraction `0.1`:
`k = min(N, max(1, round(0.1 * N)))` for N ≥ 1. This guarantees at least
one Delete for Modify/Delete demos (N = 1–5 inflate above 10%; N ≥ 10
tracks ~10%). Use a **dedicated** `random.Random(config.seed)` after rows
are built so Delete indices stay stable if `build_rows` RNG consumption
changes. Do **not** use Bernoulli/`TABLESAMPLE`-style probability —
acceptance needs exact `k`. Tests: fixed-seed exact Delete indices/count
(SPEC-006 pattern) plus optional large-N threshold check (SPEC-009).

**Header aliasing parity** (learnings-curator): CSV trailing headers must
come from `build_header(config)` (aliased display names such as
`Store #`), not raw `COLUMN_ORDER` technical names — same as xlsx.

**Prior learnings curation:** Clean signal — ledger + raw learnings are
architecturally relevant (SPEC-012 third-artifact pattern, paired
endpoints, aliasing, seeded RNG testing). No CSV dialect prior learning
existed; dialect decided from docs + prior art. Soft contradiction on
`max(1, …)` vs plain `round` resolved toward `max(1, …)` for demo
Delete visibility and eq_code precedent (noted above).

## Scope boundaries

- Does not replace the `.xlsx` stop download — CSV is additive.
- Does not auto-write files into the user's DirectRoute directory.
- Does not change truck-file download formats.
- Exact OIS template parity beyond Branch/Action + matching stop content
  is out of scope unless research finds a hard import requirement.
- Does not emit Action=`Add` or `Delete All` (Modify/Delete only).

## User scenarios

- As a Sales Engineer preparing an OIS-style import, I enter a Branch name
  and download a CSV whose stop rows match my `.xlsx`, with Branch and
  Action prepended for Modify/Delete testing.

## Non-functional requirements

- CSV encoding and quoting: UTF-8 with BOM (`utf-8-sig`), `csv.excel`
  dialect (comma, `QUOTE_MINIMAL`, CRLF) so Excel and common importers
  open cleanly.
- Action Delete selection is deterministic for a given `StopConfig.seed`
  and N (dedicated seeded RNG after row materialization).

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — CSV emitter reusing `build_header` /
    `build_rows`; prepend Branch/Action; Delete index selection
  - `backend/schemas/stop_config.py` — request model extending StopConfig
    with required non-empty `branch` (and CSV response shape)
  - `backend/main.py` — paired `POST /api/stops-csv/generate` +
    `/api/stops-csv/download` (mirror truck/stop/DRProject contract)
  - `components/wizard/download.tsx` — inline Branch text field (reuse
    wizard `TextField`/`FormRow` patterns; no modal primitive in
    `components/`) + CSV download control; keep existing three buttons
    unchanged
  - `components/wizard/dataset-wizard.tsx` — plumb `stopConfig` into
    `Download`
  - `lib/api.ts` — client helper + `STOP_CSV_MIME` (`text/csv`)
  - `lib/wizard-types.ts` — TS types for CSV response
  - `tests/test_stop_generator.py` and/or new `tests/test_stop_csv_*.py` —
    Delete count/seed determinism, header parity, Branch column
  - `components/wizard/dataset-wizard.test.tsx` — CSV control + Branch
    gate smoke coverage as needed

- **Files NOT to modify:**
  - `backend/generators/truck.py`, `backend/generators/drproject_config.py`
  - `backend/services/spatial.py`, `backend/schemas/truck_config.py`
  - `lib/build-config.ts` (Branch is download-time, not wizard StopConfig)
  - `hooks/use-wizard-persistence.ts`
  - `.cursor/skills/` Creator kit files
  - Existing `/api/stops/{generate,download}` response shape for xlsx
    (add sibling routes; do not overload the xlsx payload)

- **Patterns to follow:**
  - SPEC-012 third-artifact pattern: new sibling generator/routes +
    download-page control; reuse `StopConfig` as the base request body
    with an added `branch` field (ledger: api-contracts /
    SPEC-012 learnings)
  - Paired JSON+base64 `generate` and raw-bytes `download` endpoints as
    in `backend/main.py` for trucks/stops/DRProject
  - EQ-code subset selection in `build_rows` as the math precedent for
    Delete count (`max(1, round(N * fraction))` + `rng.sample`)
  - Frontend downloads via `downloadBase64` / `downloadBlob` in
    `lib/api.ts`
  - Branch UX: inline required Branch field + secondary CSV download
    button (repo has no dialog/modal primitive); do not block the three
    existing one-click downloads. Consider `_validate_ascii` on `branch`
    to match other DirectRoute text fields.

- **Test expectations:**
  - Fixed seed + known N: assert exact `k = min(N, max(1, round(0.1 * N)))`
    Delete count and stable Delete indices across two generations
  - Row/header parity: CSV columns after Branch/Action equal xlsx
    headers/values for the same `StopConfig` + seed
  - Every data row’s Branch cell equals the supplied branch string
  - Empty/whitespace Branch rejected (422 / client gate)
  - Skipping CSV leaves truck / stops.xlsx / DRProject downloads
    unchanged (existing three-artifact tests still pass)
  - Encoding smoke: leading bytes are UTF-8 BOM (`EF BB BF`) when using
    `utf-8-sig`
