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

- **The header-alias mechanism already exists and already covers `ID2`/`ID3`
  — this spec is a UX/gating change, not new backend machinery**
  (repo-analyst, learnings-curator). `backend/schemas/stop_config.py`
  (`AliasConfig`, `ALIAS_FIELD_MAP`) and `backend/generators/stop.py`
  (`build_header()` / `_alias()`, lines 78–96) already substitute a
  user-supplied alias for the literal `ID2`/`ID3` header text, falling back
  to the technical name when the alias is `None`/empty — exactly AC1–4's
  behavior. This shipped as part of SPEC-002 (`done`; AC9: "alias
  preferences for Name, Contact, Phone, ID1, ID2, ID3, Address_2 ... output
  headers use aliases where specified while preserving required field
  data").
- **Row values are keyed independently of header text, so aliasing is
  already display-only** (repo-analyst). `build_rows()` in
  `backend/generators/stop.py` assembles row cells by canonical column key
  (`"ID2"`, `"ID3"`), never by the aliased header string. Renaming the
  header cannot change which data lands in the column (AC4 is already
  satisfied by the existing implementation).
- **The gap is that `ID2`/`ID3` aliasing is buried inside a 7-field
  "Rename output columns" advanced toggle, not surfaced as its own
  always-available prompt** (repo-analyst). In
  `components/wizard/stop-questions.tsx` (lines 284–299), `aliasId2`/
  `aliasId3` text fields exist but only render when the user checks
  `aliasesEnabled`. In `lib/build-config.ts`'s `buildAliases()` (lines
  33–47), the entire aliases object — including `id2`/`id3` — is discarded
  (`return null`) unless `aliasesEnabled` is checked, even if the user
  filled in `aliasId2`/`aliasId3` before the checkbox existed conceptually.
  AC1 ("the wizard prompts the user for an optional alias ... ") reads as
  an always-visible prompt, which the current advanced-toggle gating does
  not provide.
- **The existing "blank alias → technical name" fallback already matches
  AC3 exactly and needs no new code** (repo-analyst, docs-researcher).
  Frontend: form field defaults to `""`, `optionalAscii` Zod validation
  permits blank, and `buildAliases()`'s `clean()` helper (line 35) maps
  blank/whitespace-only to `null`. Backend: `_alias()` (line 78) treats
  `None`/falsy as "use the default". No behavior change for users who
  never touch the fields — consistent with AC3.
- **Golden-template precedent already treats the `ID1` slot as
  alias-friendly in production** (repo-analyst). `COLUMN_ORDER` in
  `backend/generators/stop.py` uses the literal string `"Store #"` (not
  `"ID1"`) as the default header for that slot — the repo already ships a
  non-technical default header for an ID column, which supports that
  renaming `ID2`/`ID3` headers is a safe, established pattern rather than
  new risk surface.
- **Public DirectRoute (Trimble Appian) documentation describes `ID2`/`ID3`
  as user-configurable label slots, not fixed literal strings** (docs-
  researcher): Trimble's file-import docs describe `ID2`/`ID3` as
  "user defined field[s] (in Preferences/Config settings)" and show other
  columns (volume names) using fully custom header text on import. This is
  external precedent, not a repo-verified guarantee — the docs do not state
  whether DirectRoute matches columns by header text or position, so a
  manual DirectRoute import smoke test (already an existing informal repo
  practice per SPEC-001/002 learnings) remains the way to confirm a given
  alias imports cleanly; this is unchanged from the risk profile aliasing
  already carries in production today.
- **No existing test exercises `ID2`/`ID3` aliasing specifically, and none
  test the `aliasesEnabled` gating path this spec changes** (repo-analyst,
  verified directly): `tests/test_stop_generator.py::TestBuildHeader` only
  asserts `name`/`id1` aliases (`test_aliases_override_default_headers`);
  `lib/build-config.test.ts` only asserts the *absence* of aliases when
  disabled (line 78), never a partial ID2/ID3-only case; `lib/wizard-
  schema.test.ts` has no alias-field cases. This is a genuine coverage gap
  to close, not a sign the feature is unbuilt.
- **Industry precedent (prior-art-researcher, external — not repo fact)**:
  canonical-field-vs-display-label header aliasing with "blank = default"
  is the standard pattern across CSV/data-export tooling (e.g. Laracsv,
  Filament, KendoReact, SSIS, ElasticRoute). The main external risk
  documented for this pattern is downstream consumers that treat headers
  as a strict machine contract (e.g. reject on rename) versus consumers
  that map by header name — DirectRoute's own docs suggest the latter for
  `ID2`/`ID3`, consistent with the repo's own `ID1` → `"Store #"`
  precedent above. Standard mitigations (worth confirming during
  implementation, not blocking): reject/sanitize alias text containing
  delimiter or formula-trigger characters, reject duplicate headers, trim
  whitespace-only input to "blank." The existing `optionalAscii` Zod
  validation and backend `_validate_ascii` already reject non-ASCII,
  tabs, and line breaks for alias text, covering the sharpest edges of
  these external pitfalls.
- **Resolved product decision**: decoupling `ID2`/`ID3` from
  `aliasesEnabled` also removes the `aliasId2`/`aliasId3` fields from the
  "Rename output columns" advanced block — `ID2`/`ID3` aliasing moves
  entirely to the new always-visible prompt, with no duplicate entry point.
  The other five alias fields (`aliasName`, `aliasContact`, `aliasPhone`,
  `aliasId1`, `aliasAddress2`) keep their current advanced-toggle behavior
  unchanged, per the scope boundary. The backend `AliasConfig` model keeps
  all seven fields regardless — no API contract change.

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not add aliasing for any column other than `ID2`/`ID3` — the
  backend `AliasConfig` model and its other five alias fields (name,
  contact, phone, id1, address_2) are unaffected and keep their current
  advanced-toggle behavior/API shape; this spec only relocates `ID2`/`ID3`
  out of that advanced block into their own always-visible prompt.
- Does not change the API contract's field names or shape — `StopConfig.
  aliases.id2`/`id3` already exist and are reused as-is; only the wizard's
  UI placement of `aliasId2`/`aliasId3` changes (moved out of the
  `aliasesEnabled`-gated block, no longer requiring that toggle).
- Does not attempt to validate against a specific customer's DirectRoute
  Preferences label configuration; a manual DirectRoute import smoke test
  (existing informal practice) is the acceptance mechanism for import
  compatibility, not an automated check.

## User scenarios

<!-- (Recommended) Who uses this and how — user stories, journeys, or scenario descriptions. -->

## Non-functional requirements

<!-- (Recommended) Performance, security, accessibility, or other cross-cutting concerns. -->

## Implementation guidance

<!-- (Recommended) File paths to modify, patterns to follow, test expectations.
     Use repo-root-relative paths for repo files, and describe local-only artifacts
     generically instead of pasting machine-specific paths like `/home/...` or `/Users/...`. -->

- **Files likely affected:**
  - `components/wizard/stop-questions.tsx` (lines 284–299) — remove the
    `aliasId2`/`aliasId3` `TextField`s from the `aliasesEnabled`-gated
    "Rename output columns" block entirely (the other five fields —
    `aliasName`, `aliasContact`, `aliasPhone`, `aliasId1`,
    `aliasAddress2` — stay there unchanged), and add a new always-visible
    optional block (e.g. near the stop-identity fields) with its own
    `aliasId2`/`aliasId3` `TextField`s and helper text such as "Leave
    blank to use ID2"/"Leave blank to use ID3".
  - `lib/build-config.ts`'s `buildAliases()` (lines 33–47) — send
    `id2`/`id3` when non-blank regardless of `aliasesEnabled`; the other
    five fields keep their existing `aliasesEnabled`-gated behavior
    unchanged.
  - `components/wizard/review.tsx` — optionally surface the chosen ID2/ID3
    aliases (or "using default ID2/ID3") in the review summary; currently
    no alias fields are shown there at all.
- **Files NOT to modify:**
  - `backend/schemas/stop_config.py` (`AliasConfig`, `ALIAS_FIELD_MAP`) —
    already correct; no new fields, no shape change.
  - `backend/generators/stop.py`'s `build_header()`/`_alias()` — already
    implements the exact fallback behavior AC2–4 require.
  - `lib/wizard-types.ts` — `AliasConfig` type already has `id2`/`id3`.
- **Patterns to follow:**
  - Reuse the existing `optionalAscii` Zod pattern
    (`lib/wizard-schema.ts` lines 23–24) for `aliasId2`/`aliasId3` — do not
    introduce a new optional-string helper.
  - Reuse the existing `clean()` blank-to-`null` mapper in `buildAliases()`
    — do not duplicate the trimming logic elsewhere.
  - Follow the `TextField` component pattern already used for other
    `stop-questions.tsx` fields (label + optional `hint`) for the
    promoted ID2/ID3 fields, per the NN/G progressive-disclosure guidance
    surfaced in research: persistent label + helper text, not
    placeholder-only defaults.
- **Test expectations:**
  - `tests/test_stop_generator.py::TestBuildHeader` — add a case setting
    only `AliasConfig(id2=..., id3=...)` and asserting both aliased
    headers appear and the literal `"ID2"`/`"ID3"` strings do not; add a
    case confirming blank/`None` id2/id3 still falls back to `"ID2"`/
    `"ID3"` (mirrors the existing `test_aliases_override_default_headers`
    / `test_default_headers_used_without_aliases` pair).
  - `lib/build-config.test.ts` — add a case where only `aliasId2`/
    `aliasId3` are filled in and `aliasesEnabled` is `false` (or removed),
    asserting `config.aliases` is `{ id2: "...", id3: "...", ...rest
    null }` rather than `null` (current line-78 test only covers the
    all-blank case).
  - `lib/wizard-schema.test.ts` — add cases confirming blank
    `aliasId2`/`aliasId3` pass validation and non-ASCII values are
    rejected, consistent with other `optionalAscii` field tests.
  - Manual/visual check (no automated test needed): the "Rename output
    columns" advanced block no longer shows `ID2 column alias`/`ID3
    column alias` fields, and the new always-visible prompt shows them
    exactly once with no duplicate entry point.
