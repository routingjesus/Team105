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

The API allows CORS from the wizard's local dev origins (`http://localhost:3000`
and `http://127.0.0.1:3000`) out of the box. To point a differently-hosted UI
at it, set a comma-separated `WIZARD_ALLOWED_ORIGINS` before launching, e.g.
`$env:WIZARD_ALLOWED_ORIGINS = 'https://wizard.example.com'`.

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
`NEXT_PUBLIC_API_BASE_URL` to the deployed API origin — its value is inlined at
`npm run build` time, so set it *before* building, not after. When the API is a
different origin, add that origin to the backend's `WIZARD_ALLOWED_ORIGINS`.

### Run the full stack locally

Two processes, from the repo root (the wizard is a browser client of the API):

```powershell
# Terminal 1 — API
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload

# Terminal 2 — wizard UI
npm install
copy .env.example .env          # NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm run dev                     # http://localhost:3000/datasets/new
```

**Depot addresses must exist in the static location database.** Stop generation
resolves each depot to coordinates by matching its address against
`backend/data/location_db.xlsx` — first by exact street address, then by
city + state + zip. A made-up address fails with
`No location_db match for depot ...`. For a known-good demo depot use:

> **1216 Greenbrier Parkway, Chesapeake, VA 23320** (≈191 candidate stops
> within the default 50-mile radius)

Any real city/state/zip present in the database also works (matching is
whitespace- and case-insensitive). State-selection mode filters candidates by
state directly and does not need the depot to resolve.

### Import into DirectRoute

The wizard produces two files:

- `fleet.truck` — tab-delimited truck/fleet file (SPEC-001)
- `stops.xlsx` — stop file (SPEC-002)

Download both from the final wizard step, then import them into DirectRoute
(trucks first, then stops) to build a routing solution. This end-to-end import
is the manual acceptance step (AC8) that can't be automated here.

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
