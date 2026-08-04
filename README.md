# Team105 — Dataset Creation Wizard

Generates synthetic, import-ready DirectRoute datasets: a tab-delimited
`.TRUCK` truck file and (upcoming) an `.XLSX` stop file, driven by a guided
wizard. Bootcamp capstone for AI Bootcamp Cohort 3, Team 105.

## Status

| Piece | Spec | State |
|-------|------|-------|
| Truck file generator + API | SPEC-001 | Done ([PR #2](https://github.com/routingjesus/Team105/pull/2)) |
| Stop file generator | SPEC-002 | Done ([PR #3](https://github.com/routingjesus/Team105/pull/3)) |
| Wizard UI (Next.js) | SPEC-003 | In progress |

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

Endpoints (same request body per generator, two delivery shapes each):

- `POST /api/trucks/generate` / `POST /api/stops/generate` — JSON metadata
  with base64-encoded file content
- `POST /api/trucks/download` / `POST /api/stops/download` — raw file
  bytes with `Content-Disposition`

Interactive docs at `http://127.0.0.1:8000/docs`.

## Wizard UI (frontend)

A Next.js (App Router) wizard walks a user through route and stop questions,
previews the dataset, then generates and downloads both files via the API
above. It consumes the backend contract directly — no file formats are exposed
to the user.

```powershell
# Node is not preinstalled on bootcamp hosts; install once:
winget install OpenJS.NodeJS.LTS   # or unzip an official Node build to a user dir

npm install
copy .env.example .env             # points NEXT_PUBLIC_API_BASE_URL at the API
npm run dev                        # wizard at http://localhost:3000/datasets/new
```

Build, lint, and test the frontend:

```powershell
npm run build
npm run lint
npm test
```

The wizard calls `POST /api/trucks/generate` then `POST /api/stops/generate`
(stop generation consumes the truck response), decodes the base64 file content
from each response, and offers one download button per file. Set
`NEXT_PUBLIC_API_BASE_URL` to the deployed API origin (the backend must allow
CORS for the wizard origin, or proxy through a Next Route Handler).

## Backend tests

```powershell
.venv\Scripts\python.exe -m pytest tests/
```

A few tests skip by design:

- The truck generator's golden byte-parity test awaits a known-good
  "Explode my Trucks" macro sample — see `fixtures/truck/README.md` to add it.
- One stop-API test only runs when `backend/data/location_db.xlsx` is
  *absent* (a fresh-clone scenario) — see `backend/data/README.md`.

## Layout

- `backend/schemas/` — Pydantic request/response contracts (canonical for all specs)
- `backend/generators/` — pure file emitters, no I/O
- `backend/services/` — supporting logic with I/O or numeric work (e.g. `spatial.py`)
- `tests/` — pytest suite (backend)
- `app/` — Next.js App Router pages (`/` landing, `/datasets/new` wizard)
- `components/wizard/` — wizard step components and orchestrator
- `lib/` — API client, Zod schema/types mirroring the backend contract, config mappers
- `hooks/` — session persistence for in-progress answers
- `.spec/` — Creator specs, lifecycle metadata, and curated learnings ledger
