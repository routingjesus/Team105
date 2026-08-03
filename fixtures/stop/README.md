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

## Open item: bundled production database

**`backend/data/location_db.xls` does not exist yet.** SPEC-002's
implementation guidance calls for the owner to supply the real master
location database (the full candidate pool the generator selects from in
production); it's a bundling/deployment prerequisite, not something this
spec's code can fabricate. Until it's added, `/api/stops/generate` and
`/api/stops/download` return `503` with a message pointing at the missing
path. All unit tests use `sample_location_db.xlsx` instead and are
unaffected by this gap.
