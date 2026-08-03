# Bundled location database

`location_db.xlsx` is the static candidate-location pool `/api/stops/*`
selects from (SPEC-002). It does **not** ship real customer identities:

- **Addresses, cities, states, zips, and lat/long are real** (a real 2015
  "Customer Sites" store-location export, ~21.9k rows) -- the owner
  confirmed real geography is fine to bundle.
- **Names are synthetic**, replaced with deterministic `Customer 00001`,
  `Customer 00002`, ... placeholders. The original store names/brands are
  proprietary and were never committed to this repo.
- **Contact/Phone/ID2/ID3 are passed through** from the source (mostly
  blank in the original export).

Regenerate from a source workbook with the same `store locations` sheet
shape (`Store #`, `Address`, `City`, `State`, `Zip`, `Latitude`,
`Longitude`, ...):

```powershell
.venv\Scripts\python.exe backend\data\prepare_location_db.py "<path to source .xls>"
```

See `prepare_location_db.py` for the exact column mapping and the
name-scrambling step.
