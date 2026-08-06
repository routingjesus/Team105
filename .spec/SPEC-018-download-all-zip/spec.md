---
id: SPEC-018
title: "Download All button on wizard step 4 (zip export)"
category: feature
owner: mpierce                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

After completing the dataset wizard, users land on step 4 ("Download") and must
click three separate buttons to collect the generated dataset files
(`fleet.truck`, `stops.xlsx`, `DRProject.config`). For repeated dataset
creation and demo prep this is tedious and error-prone — it is easy to grab the
truck and stop files but forget `DRProject.config`, producing a broken
DirectRoute import later. A single "Download All" button that packages every
file generated in step 3 into one zip archive guarantees the complete set
lands on the user's machine in one click.

## Acceptance criteria

1. Step 4 of the wizard displays a "Download All" button alongside the
   existing per-file download buttons.
2. Clicking "Download All" downloads exactly one `.zip` archive to the user's
   machine via the browser's normal download mechanism.
3. The archive contains exactly three entries — `fleet.truck`, `stops.xlsx`,
   and `DRProject.config` — at the archive root (no nested folders).
4. Each archive entry is byte-identical to the file produced by its
   corresponding individual download button, preserving the original file
   type generated in step 3 (tab-separated `.truck`, Excel `.xlsx`,
   XML `.config`).
5. "Download All" works without filling in the optional "Branch name" field;
   the on-demand stops CSV is not part of the archive.
6. If preparing the archive fails, an error message appears near the button
   (matching the existing stops-CSV error presentation) and the individual
   download buttons remain usable.
7. The three existing individual download buttons and the stops CSV download
   continue to work unchanged.

## Research

- **Decision: zip client-side from the base64 payloads already in browser
  memory; do not add a backend zip endpoint.** Backend regeneration cannot
  guarantee byte-identical output for `stops.xlsx`: the XlsxWriter emitter
  (`backend/generators/stop.py`, `pd.ExcelWriter(engine="xlsxwriter")`)
  stamps wall-clock `dcterms:created`/`dcterms:modified` timestamps into
  `docProps/core.xml`, so two generations seconds apart differ (verified
  empirically). The individual step-4 buttons download the in-memory base64
  via `downloadBase64`, so only zipping those same bytes satisfies AC 4.
  (repo-analyst, docs-researcher, prior-art-researcher)
- **A backend endpoint would also need request plumbing that step 4 lacks.**
  The `Download` component receives only `stopConfig` plus the three
  generation responses; truck-only config fields (`mi_cost`, `hr_cost`,
  `fixed_cost`, `max_work`, `max_drive`, `pre_trip`, `post_trip`, `sp_eq`)
  are not recoverable from `StopConfig` or `TruckGenerationResponse`, so
  regenerating `fleet.truck` server-side would need new plumbing of
  `TruckConfig` to step 4. (repo-analyst)
- **Library choice: `fflate`.** ~7–8 kB tree-shakeable, zero dependencies,
  built-in TypeScript types, actively maintained (~6M weekly downloads);
  `zipSync({...})` takes `Uint8Array`s keyed by entry name — exactly what we
  hold. JSZip's last release is 3.10.1 (Aug 2022) at ~90 kB with a legacy
  dependency chain. The browser Compression Streams API produces only
  gzip/deflate streams, not `.zip` containers, so a no-dependency native
  path is not realistic. (docs-researcher)
- **New npm dependency requires explicit user approval** (repo policy). The
  environment ledger notes bootcamp Windows hosts run user-local Node
  installs, so any frontend dependency must be pure JS with no native
  postinstall step — `fflate` qualifies. (learnings-curator, docs-researcher)
- **Zip construction details:** store the already-deflate-compressed
  `stops.xlsx` entry with `level: 0` (fflate README explicitly recommends
  this for pre-compressed formats); text entries (`fleet.truck`,
  `DRProject.config`) can use default compression. `fflate` stamps entry
  `mtime` with the current time by default, so whole-archive bytes are not
  reproducible across runs — tests must compare extracted entry bytes, not
  archive bytes (or pass a fixed `mtime`). (docs-researcher)
- **Pitfalls to avoid:** decode base64 to `Uint8Array` binary-safely (reuse
  the existing `base64ToBlob`/`atob`-to-`Uint8Array` path in `lib/api.ts` —
  string-based handling corrupts binary xlsx); trigger the download through
  the existing `downloadBlob` helper, which already handles the
  single-user-gesture and object-URL lifecycle. (prior-art-researcher — lane
  returned a thin final message, key findings salvaged from its summary;
  docs-researcher)
- **Established repo patterns to follow:** step 4 (`components/wizard/
  download.tsx`) is the settled surface for extra download actions
  (SPEC-012, SPEC-016); the busy-state + `role="alert"` error presentation
  next to the button mirrors the SPEC-016 stops-CSV control. The paired
  generate/download API contract (`.spec/_ledger/api-contracts.yaml`)
  remains untouched by this spec. (learnings-curator, repo-analyst)
- **Test precedent:** `components/wizard/dataset-wizard.test.tsx` stubs
  `URL.createObjectURL`/`revokeObjectURL` and spies
  `HTMLAnchorElement.prototype.click`; a Download All test can assert a
  single anchor click, and a unit test on the zip helper can decode the
  produced archive and compare entry bytes to the fixture base64.
  (repo-analyst)

## Scope boundaries

- The on-demand stops CSV (Branch/Action columns, SPEC-016) is **not**
  included in the archive — it is generated in step 4 with a user-supplied
  branch name, not in step 3.
- No changes to generation logic, file contents, or file formats — the zip
  only packages what step 3 already produced.
- No changes to wizard steps 1–3 (question forms, review, generation flow).
- No renaming of files inside the archive; entries keep the exact filenames
  used by the individual download buttons.

## User scenarios

- A demo builder finishes the wizard and clicks "Download All" to get every
  file needed for a DirectRoute import in one archive, instead of three
  separate downloads scattered in the downloads folder.
- A user regenerating datasets repeatedly (tuning answers, re-running) grabs
  the full set each iteration with one click and never ships an incomplete
  file set.

## Non-functional requirements

- Archive preparation for typical dataset sizes (stop files up to a few MB)
  should feel immediate; if preparation is asynchronous, the button shows a
  busy state consistent with the existing "Preparing CSV…" pattern.
- The download must trigger from the single user gesture (popup-safe), the
  same guarantee the existing `downloadBlob` helper provides.

## Implementation guidance

- **Chosen approach (from research):** client-side zip with `fflate`. Decode
  the three base64 payloads the `Download` component already receives
  (`truck.truck_file_base64`, `stop.stop_file_base64`,
  `drprojectConfig.drproject_config_file_base64`) to `Uint8Array`s, build
  the archive with `zipSync` (entry `stops.xlsx` with `level: 0`; entries at
  archive root), and trigger the download as `dataset.zip` via the existing
  `downloadBlob` helper. No backend changes.
- **Files likely affected:**
  - `package.json` / `package-lock.json` — add `fflate` (approved new
    dependency)
  - `lib/api.ts` (or a small new `lib/zip.ts`) — base64 → `Uint8Array`
    decode reuse + zip-and-download helper
  - `components/wizard/download.tsx` — add the "Download All" button and
    error presentation
  - `components/wizard/dataset-wizard.test.tsx` — UI coverage
- **Files NOT to modify:** `backend/**` (no backend changes at all),
  `lib/wizard-schema.ts`, wizard step components other than `download.tsx`
  (`truck-questions.tsx`, `stop-questions.tsx`, `review.tsx`,
  `location-entry-panel.tsx`).
- **Patterns to follow:** `base64ToBlob`/`downloadBlob` in `lib/api.ts` for
  binary-safe decoding and single-gesture download; SPEC-016's busy-state
  and `role="alert"` error placement next to the button.
- **Test expectations:**
  - UI test in `components/wizard/dataset-wizard.test.tsx` (existing
    `URL.createObjectURL` stub + anchor `click` spy pattern): "Download All"
    renders on step 4 and one click produces exactly one download without
    requiring the Branch field.
  - Unit test on the zip helper: unzip the produced archive and assert it
    contains exactly `fleet.truck`, `stops.xlsx`, `DRProject.config` with
    bytes matching the decoded fixture base64. Compare entry bytes, not
    whole-archive bytes (fflate stamps current-time `mtime` unless fixed).
