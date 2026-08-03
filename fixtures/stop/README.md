# Stop file fixtures

## Golden column-order templates

`TEMPLATE_NewConfigStopFile.xls` (customer-facing, 70 columns -- canonical
for P0 output) and `TEMPLATE_AnalystStopFile.xls` (internal/analyst
variant, 69 columns, adds `LocationTimeZone`) are owner-supplied
DirectRoute stop-file templates. Each has two sheets:

- `Header Desc.` -- field name, description, and required flag per column
- `Stop File` -- the header row itself, in authoritative column order

`backend/generators/stop.py`'s `COLUMN_ORDER` is derived from the
customer-facing template's `Stop File` header row, with the two generic
volume slots (`Cube`, `Weight`) collapsed into one dynamic segment since
the template's own field description says a volume column "can be named
anything."

## Sample location database

`sample_location_db.xlsx` is a small (56-row) **synthetic** candidate
database used by tests -- fabricated names/addresses across a dense
Columbus, OH cluster and a sparse Texas cluster, with a `Test DC` record
for exact-address depot-coordinate resolution. Regenerate it with
`python fixtures/stop/make_sample_location_db.py`.

## Production database

**`backend/data/location_db.xlsx` is now bundled** -- see
`backend/data/README.md` for what it contains (real geography, synthetic
names) and how it was built. Before it landed, `/api/stops/generate` and
`/api/stops/download` returned `503`; that path is still exercised by
`tests/test_stop_api.py::TestLocationDbPrerequisite` whenever the file is
absent (e.g. a fresh clone before running `prepare_location_db.py`). All
unit tests in this repo use the synthetic `sample_location_db.xlsx`
instead of the production file, so they're unaffected either way.
