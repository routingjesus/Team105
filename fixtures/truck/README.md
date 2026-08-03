# Truck file golden fixtures

Known-good output samples from the legacy "Explode my Trucks.xlsxm" macro,
used by the byte-parity golden test in `tests/test_truck_generator.py`.

## Status

**Open item (SPEC-001):** no macro sample has landed yet. The golden parity
test skips until one exists. Header and row logic were implemented from the
PRD's documented 76-column schema; `TrkID` composition
(`T01-Wk1-SU`) is provisional until verified against a real sample.

## Adding a fixture

1. Run the macro for a single-depot scenario and save the raw `.TRUCK`
   output here as `single_depot_baseline.truck`. Do not open/re-save it in
   an editor — byte fidelity (CRLF, encoding, trailing whitespace) matters.
2. Add `single_depot_baseline.json` next to it containing the matching
   `TruckConfig` request body (weeks, depot address, costs, etc.).
3. Run `pytest tests/test_truck_generator.py -k golden` — the test compares
   raw bytes, not parsed rows.
