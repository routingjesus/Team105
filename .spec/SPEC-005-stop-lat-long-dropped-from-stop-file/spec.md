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

- **Root cause confirmed and isolated to one file** (repo-analyst): `COLUMN_ORDER` in `backend/generators/stop.py:35-47` already includes `"Longitude"`/`"Latitude"` (positions 28-29, between `Pattern2` and `Symbol`), and the candidates `DataFrame` retains both columns intact all the way through `filter_by_radius`, `filter_by_state`, and `thin_to_target` (`backend/services/spatial.py:98-166` — none of them drop columns). The drop happens purely in the row-assembly stage: `SelectedStop` (`backend/generators/stop.py:154-168`) has no coordinate fields, `selected_stops_from_candidates()` (lines 177-195) never reads `Latitude`/`Longitude` off the candidate row, and `build_rows()`'s `row_by_col` dict (lines 238-256) never sets those two keys — so `row_by_col.get(col, "")` at line 262 always renders `""`. Live verification against `fixtures/stop/sample_location_db.xlsx` confirmed candidates carry real coordinates (e.g. `[39.473441, -83.324345]`) while output rows are blank.
- **This is a scoped behavior reversal, not a regression** (repo-analyst): `.spec/SPEC-002-stop-file-generator/spec.md:38,50` explicitly scoped `Longitude`/`Latitude`/`GeoResult` as optional-with-fallback for P0 ("DirectRoute will populate thru Geocoding process" per the golden template's own field description) — SPEC-002 never wired coordinate carry-through by design, it wasn't broken. SPEC-005 intentionally changes that: since `location_db.xlsx` already has geocoded coordinates for every candidate (used today for depot-DC resolution in `spatial.py`), carrying them into the stop file avoids relying on DirectRoute's own geocoding for data we already have. `backend/generators/truck.py` (SPEC-001) has the same empty-coordinate behavior and is explicitly out of scope here.
- **Coordinate types and precision** (repo-analyst): both `backend/data/location_db.xlsx` and the test fixture (`fixtures/stop/make_sample_location_db.py:36-37,58-59`) store `Latitude`/`Longitude` as `float64` with up to 6 decimal places, 0 nulls in the production file (first 100 rows verified). No `ALIAS_FIELD_MAP` entry exists for either column (`backend/schemas/stop_config.py:26-34`) and none is needed — `build_header()` already passes them through as literal column names.
- **No pandas/xlsxwriter quirk explains the drop** (docs-researcher): `to_excel(engine="xlsxwriter")` writes numeric columns via `write_number()` with standard IEEE-754 precision (~15 significant digits) — well beyond the 6-dp precision these values need, so there's no library-level cause; this is purely the application-side mapping gap above.
- **Prior learnings corroborate the fix surface and testing approach** (learnings-curator, ledger + SPEC-002/SPEC-003 meta.yaml): (1) the bundled `location_db.xlsx` intentionally kept real lat/long geography even while scrambling names/IDs (SPEC-002 meta.yaml) — the source data is trustworthy; (2) `location_db.xlsx` is whitespace-padded fixed-width text requiring normalization on load (`.spec/_ledger/directroute-file-formats.yaml`), and SPEC-003's fixture-vs-real-DB testing gap ("unit fixtures were too clean") means this fix's new tests should exercise the real `backend/data/location_db.xlsx` in addition to the lightweight sample fixture; (3) SPEC-002's self-review found that "column present in the header ≠ value populated" bugs (e.g. the `Open1`/`Close1` zero-falsy bug) are only caught by explicit AC-by-AC assertions, not incidental test-suite passing — directly applicable to writing the new coordinate assertion.
- **Common pitfall pattern matches exactly** (prior-art-researcher): "field silently dropped while carrying a value from source record to output row" bugs are most commonly caused by an output row-mapping dict/dataclass that was never updated when the field was needed downstream — exactly what happened here. The recommended regression-proofing pattern is a direct equality/parity assertion between the source record field and the rendered output cell, not just a presence/non-blank check.
- **Consolidation interacts with the fix** (repo-analyst, open consideration): when `config.consolidation.enabled` produces multiple output rows (`ID2` line items) per physical stop, all lines for that stop should carry the same lat/long, mirroring existing `Address` duplication behavior (`backend/generators/stop.py:236-256`) — not explicitly called out in the ACs but implied by "each row."

## Scope boundaries

<!-- What is explicitly out of scope. -->

- Does not change how depot/stop addresses are matched against the location
  database (matching logic itself is out of scope).
- Does not add new columns beyond latitude/longitude carry-through.

## Error evidence

No exceptions or logged errors — this is a silent data-loss bug (output rows generate successfully but with blank `Longitude`/`Latitude` cells). Confirmed via direct interpreter run: candidates returned by `select_candidates()` retain real coordinates (e.g. `[39.473441, -83.324345]`), but `build_rows()` output has empty strings at those column positions for every row.

## Root cause analysis

Introduced by SPEC-002's original implementation, which never wired coordinate carry-through because its own research explicitly scoped `Longitude`/`Latitude`/`GeoResult` as optional/emit-blank for P0 (golden template said DirectRoute geocodes on import). The row-assembly pipeline (`SelectedStop` dataclass → `selected_stops_from_candidates()` → `row_by_col` dict in `build_rows()`) was built to carry only the fields SPEC-002 needed (Name, Contact, Phone, ID1/ID2/ID3, Address, Address2, City, State, Zip) and never extended to include coordinates, even though `COLUMN_ORDER` already reserved the `Longitude`/`Latitude` slots and the candidate `DataFrame` has always carried real values through the entire filter/thin pipeline. The fix should add coordinate fields to `SelectedStop`, populate them in `selected_stops_from_candidates()`, and add the two keys to `row_by_col` in `build_rows()`.

## Blast radius

Isolated to `backend/generators/stop.py`'s row-assembly functions. `backend/services/spatial.py` needs no changes (already preserves coordinates correctly). `backend/main.py`'s stop endpoints delegate entirely to `select_candidates`/`generate_stop_file` and pick up the fix automatically. `backend/generators/truck.py` (SPEC-001's truck file, which has its own independent empty-coordinate behavior) is untouched and out of scope. No schema or API contract changes.

## Implementation guidance

- **Files likely affected:**
  - `backend/generators/stop.py` — add `latitude: float` / `longitude: float` to the `SelectedStop` dataclass (lines 154-168); read `Latitude`/`Longitude` off the candidate row in `selected_stops_from_candidates()` (lines 177-195); add `"Longitude"`/`"Latitude"` keys to the `row_by_col` dict in `build_rows()` (lines 238-256) — `COLUMN_ORDER` renders `Longitude` before `Latitude` (line 39), so key names must match exactly
  - `tests/test_stop_generator.py` — extend or add a test asserting output coordinates match the source `location_db` values, following the `test_required_columns_are_populated_for_every_row` pattern (lines 226-233); use the `location_db`/`base_config` fixtures already defined in this file (lines 40-58)
- **Files NOT to modify:**
  - `backend/services/spatial.py` — already correctly preserves `Latitude`/`Longitude` through `filter_by_radius`, `filter_by_state`, `thin_to_target`; no column-dropping bug there
  - `backend/generators/truck.py` — SPEC-001's truck file has its own independent empty-coordinate behavior; out of scope
  - `backend/schemas/stop_config.py` — no alias handling needed; `Latitude`/`Longitude` are not in `ALIAS_FIELD_MAP` and don't need to be
  - `backend/main.py` — thin wrapper over the generator; fixed automatically once `stop.py` is fixed
- **Patterns to follow:**
  - Passthrough mapping: extend `selected_stops_from_candidates()` and `row_by_col` the same way existing fields like Address/City/State/Zip are carried (`backend/generators/stop.py:188-192, 245-249`)
  - Numeric-in-string-row rendering: match existing numeric formatting conventions in the same file, e.g. `f"{frequency:g}"` / `f"{value:.2f}"` (lines 205-206, 255); DB values are `float64` with up to 6 decimal places, so preserve full precision (e.g. `str(value)` or `f"{value:.6f}"`) rather than truncating
  - Consolidation: when multiple `ID2` line items are generated per physical stop (`config.consolidation.enabled`), repeat the same lat/long across all lines for that stop, mirroring existing `Address` duplication behavior
- **Test expectations:**
  - Assert every output row's `Longitude`/`Latitude` cells are non-blank and numerically match (`pytest.approx(..., abs=1e-6)`, following the float-comparison pattern in `tests/test_spatial.py:41-42`) the source `location_db` record for that stop's `Address`
  - Coerce both sides to `float` before comparing, since `build_rows()` emits string cells but `location_db` values are native floats
  - Cover the consolidation case: assert all line-item rows for one physical stop share identical coordinates
  - Per the learnings-curator lane's fixture-vs-real-DB lesson (SPEC-003), consider running at least one assertion against the real `backend/data/location_db.xlsx` in addition to the lightweight `fixtures/stop/sample_location_db.xlsx`, since past bugs in this data path were masked by overly-clean test fixtures
