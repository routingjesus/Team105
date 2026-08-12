# Coords-or-address location completeness — Design

- **Date:** 2026-08-12
- **Status:** Approved (brainstorming output)
- **Related:** SPEC-019 (session coords paste; address still required),
  SPEC-001 (truck file generator), SPEC-002 (stop file / manual stops)

## Problem / goal

After SPEC-019, operators can paste Google Maps coordinates for a depot or
manual stop, but street, city, state, and ZIP remain required even when
coordinates are present. That blocks a common case: the user has a pin and
does not have (or does not want to type) a full street address.

Goal: if the user pastes valid Google coordinates, those four fields are not
required. The same rule applies to **depots** (truck file) and **manual
stops** (stop file). When the fields are left blank, generated files write
empty Address / City / State / Zip cells. Coordinates still write as they do
today. Without coordinates, the four fields stay required. Both address and
coordinates together remain valid.

## Chosen approach: shared either-or completeness rule (Approach 1)

Keep one location shape. A location is complete when it has pasted
coordinates **or** all four address fields (or both). Neither is invalid.

Alternatives considered and rejected:

- **Two location types (Approach 2)** — discriminated union of
  coords-location vs address-location. Would fight the existing flat
  `LocationFields` object and the shared `LocationEntryPanel` used by both
  depots and manual stops.
- **Always-optional address (Approach 3)** — drop required checks with no
  either-or rule. Would accept a location with neither coordinates nor
  address, which leaves radius gating and DirectRoute with an empty pin.

### Architecture

One location shape stays in place for depots and manual stops. Completeness
is a cross-field rule, not a second form type.

- Valid: pasted coordinates, or street + city + state + ZIP, or both.
- Invalid: neither coordinates nor a complete address quartet.
- Partial address with coordinates is valid; blank fields write as empty
  cells.

Frontend: `locationFieldsSchema` in `lib/wizard-schema.ts` (already shared by
`depotSchema` and `manualStopSchema`) switches those four fields to optional
ASCII text, then `superRefine`s with the existing `hasValidCoordinates`
helper. If coordinates are missing, empty address fields get the same
`"Required"` errors they do today.

Backend: `DepotSpec` and `ManualStop` drop `min_length=1` on those fields
(default `""`) and share one `model_validator` helper so the two models
cannot drift. Generators do not change: they already write the field values,
including empty strings. Radius already prefers pasted depot coordinates, so
a coords-only depot still unlocks radius mode. Manual stops already name a
blank address `Manual stop N`.

### Components

| Piece | Change |
|--------|--------|
| `lib/location-utils.ts` | Keep `hasValidCoordinates`. Add `hasCompleteAddress` (all four fields non-empty after trim) so schema and tests share one definition of address identity. |
| `lib/wizard-schema.ts` | `locationFieldsSchema` uses optional ASCII for address / city / state / ZIP, then `superRefine`s: if `hasValidCoordinates`, pass; otherwise require the four fields. `depotSchema` and `manualStopSchema` keep inheriting this. |
| `backend/schemas/truck_config.py` | `DepotSpec` address fields default to `""`. Shared either-or helper lives next to `DepotSpec`. ASCII checks stay; empty strings are valid ASCII. |
| `backend/schemas/stop_config.py` | `ManualStop` uses the same helper (imported from truck schema module). |
| `components/wizard/location-entry-panel.tsx` | Same paste control. When coordinates are present, the four labels read as optional (for example `City (optional)`). Clearing coordinates restores required behavior because validation re-runs on the live values. No new buttons. |
| Generators / radius / naming | Unchanged. Truck and stop emitters already write empty strings. Radius prefers inline depot coords (`spatial.py`). `_manual_stops_frame` already uses `stop.address.strip() or f"Manual stop {index + 1}"`. |

### Data flow

1. User pastes Google `lat, long` and clicks **Use coordinates** (or presses
   Enter). Latitude/longitude are set on that depot or manual stop.
2. On step validation / submit, the shared schema runs: coordinates present →
   address fields may be blank; coordinates absent → the four fields must be
   filled.
3. The wizard POST body already sends those fields. Backend repeats the same
   either-or check so a client cannot skip it.
4. Truck rows write `Address` / `City` / `State` / `Zip` as given (empty if
   blank) and `Latitude` / `Longitude` as today (six-decimal pasted values, or
   empty if omitted).
5. Manual stop rows do the same for address columns. `Name` / `ID1` still
   fall back to `Manual stop N` when street address is blank.
6. Radius mode still uses pasted depot coordinates first, so a coords-only
   depot can use radius. State/zip selection does not need depot address.

### Error handling

- **No coordinates and a blank address field** — that field shows
  `"Required"`, same message as now. If all four are blank, all four error.
- **Coordinates present** — blank address fields are not errors. Non-ASCII in
  a filled field is still rejected.
- **Invalid paste** — existing paste errors stay (format, bounds, `(0, 0)`).
  A failed paste does not clear a previously accepted pair.
- **Clear coordinates** while address is still blank — the four fields become
  required again on the next validation.
- **Backend 422** — if a request has neither coordinates nor a complete
  address, Pydantic rejects it. Existing API error mapping onto wizard fields
  still applies.
- **Partial address + coordinates** — allowed; no extra warning.

No new “provide address or coordinates” banner. Field-level `"Required"` on
the four blanks (when coords are missing) is the primary signal.

### Testing

- **Wizard schema (Vitest)** — Address-only depot still valid. Coords-only
  depot valid. Coords-only manual stop valid. Neither (blank address and no
  coords) invalid. Partial address without coords still invalid. Existing
  non-ASCII rejection still applies to filled fields.
- **`hasCompleteAddress` (Vitest)** — Trim-aware: `"  "` is not complete.
- **Pydantic (pytest)** — Same matrix on `DepotSpec` and `ManualStop` so the
  shared helper cannot drift.
- **Generators** — Coords-only depot: `Address`/`City`/`State`/`Zip` cells
  empty; lat/long populated. Coords-only manual stop: address cells empty;
  `Name`/`ID1` are `Manual stop N`.
- **Unchanged** — Radius still available when at least one depot has coords;
  paste parser tests stay as they are.

No DirectRoute import CI; empty address cells with coords is the agreed file
behavior.

## Out of scope

- New location types or a coords-vs-address discriminated union
- Making address always optional with no either-or check
- Placeholders in Address / City / State / Zip cells (empty cells are
  intentional)
- New geocoding, reverse geocode, or DMS paste formats
- Changes to radius / state / zip selection logic beyond what coords-only
  depots already unlock
- Unrelated wizard step redesign (costs, volumes, downloads, etc.)

## Files likely affected

- `lib/location-utils.ts`, `lib/location-utils.test.ts`
- `lib/wizard-schema.ts`, `lib/wizard-schema.test.ts`
- `components/wizard/location-entry-panel.tsx`
- `backend/schemas/truck_config.py`
- `backend/schemas/stop_config.py`
- `tests/test_truck_generator.py`, `tests/test_truck_api.py` (coords-only
  depot emission / request validation)
- Stop generator / schema tests covering `ManualStop` and
  `_manual_stops_frame`

## Files NOT to modify

- `backend/generators/truck.py` and `backend/generators/stop.py` unless a
  test proves emission of empty strings is not already correct
- `backend/services/spatial.py` (inline coords already preferred)
- Radius / zip / state UI gating in `stop-questions.tsx` (already uses
  `hasValidCoordinates`)
- Location database, geocoding remnants, download / packaging paths

## Design references

- Brainstorming Q&A (2026-08-12): apply to depots **and** manual stops;
  empty address cells when fields are blank; shared either-or rule; labels
  show optional when coordinates are present.
