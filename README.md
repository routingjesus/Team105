# Team105 — Dataset Creation Wizard

Generates synthetic, import-ready DirectRoute datasets: a tab-delimited
`.TRUCK` truck file and (upcoming) an `.XLSX` stop file, driven by a guided
wizard. Bootcamp capstone for AI Bootcamp Cohort 3, Team 105.

## Status

| Piece | Spec | State |
|-------|------|-------|
| Truck file generator + API | SPEC-001 | Done ([PR #2](https://github.com/routingjesus/Team105/pull/2)) |
| Stop file generator | SPEC-002 | Ready |
| Wizard UI (Next.js) | SPEC-003 | Ready |

Specs live under `.spec/`; see `spec-dashboard.html` (generate via the
`spec-dashboard` skill) for current status.

## Backend setup (Windows)

No Python toolchain ships on the bootcamp machines — use [uv](https://docs.astral.sh/uv/):

```powershell
winget install astral-sh.uv
$env:UV_SYSTEM_CERTS = 'true'   # required behind corporate TLS interception
uv venv --python 3.12 .venv
uv pip install -r backend/requirements.txt
```

## Run the API

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Endpoints (same request body, two delivery shapes):

- `POST /api/trucks/generate` — JSON routing metadata with base64-encoded
  `.TRUCK` content
- `POST /api/trucks/download` — raw `.TRUCK` file with `Content-Disposition`

Interactive docs at `http://127.0.0.1:8000/docs`.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest tests/
```

One test skips by design: the golden byte-parity test awaits a known-good
"Explode my Trucks" macro sample — see `fixtures/truck/README.md` to add it.

## Layout

- `backend/schemas/` — Pydantic request/response contracts (canonical for all specs)
- `backend/generators/` — pure file emitters, no I/O
- `tests/` — pytest suite
- `.spec/` — Creator specs, lifecycle metadata, and curated learnings ledger
