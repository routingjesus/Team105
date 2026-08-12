# Team105 — Dataset Creation Wizard

Generates synthetic, import-ready DirectRoute datasets: a tab-delimited
`.TRUCK` truck file, an `.XLSX` stop file, and a `DRProject.config`
project file, driven by a guided wizard. Bootcamp capstone for AI Bootcamp
Cohort 3, Team 105.

## Status

Completed specs so far:

| Area | Spec | PR |
|------|------|-----|
| Truck file generator + API | SPEC-001 | [#2](https://github.com/routingjesus/Team105/pull/2) |
| Stop file generator + API | SPEC-002 | [#3](https://github.com/routingjesus/Team105/pull/3) |
| Wizard UI (Next.js) | SPEC-003 | [#5](https://github.com/routingjesus/Team105/pull/5) |
| Local one-command runner + share link | SPEC-004 | [#6](https://github.com/routingjesus/Team105/pull/6) |
| Stop lat/long carry-through fix | SPEC-005 | [#9](https://github.com/routingjesus/Team105/pull/9) |
| Fractional frequency validation | SPEC-006 | [#13](https://github.com/routingjesus/Team105/pull/13) |
| Pattern column stray-dash fix | SPEC-007 | [#12](https://github.com/routingjesus/Team105/pull/12) |
| Volume range variance fix | SPEC-008 | [#10](https://github.com/routingjesus/Team105/pull/10) |
| Time-window business-hours bias | SPEC-009 | [#11](https://github.com/routingjesus/Team105/pull/11) |
| ID2/ID3 column alias prompts | SPEC-010 | [#15](https://github.com/routingjesus/Team105/pull/15) |
| Optional stop shape/color | SPEC-011 | [#14](https://github.com/routingjesus/Team105/pull/14) |
| DRProject.config generator + download | SPEC-012 | [#17](https://github.com/routingjesus/Team105/pull/17) |
| Launcher readiness checks | SPEC-013 | [#19](https://github.com/routingjesus/Team105/pull/19) |
| Static stop Size 28 with shapes/colors | SPEC-014 | [#21](https://github.com/routingjesus/Team105/pull/21) |
| Matching shape/color per customer line items | SPEC-015 | [#22](https://github.com/routingjesus/Team105/pull/22) |
| Stops CSV download (Branch/Action) | SPEC-016 | [#24](https://github.com/routingjesus/Team105/pull/24) |
| Manual location entry with geocoding | SPEC-017 | [#23](https://github.com/routingjesus/Team105/pull/23) |
Specs live under `.spec/`; see `spec-dashboard.html` (generate via the
`spec-dashboard` skill) for the full lifecycle view.

### What's next

The core wizard scope is complete. Sensible follow-ons:

- **Demo to a reviewer:** `.\run-local.cmd -Share` prints a public tunnel URL.
- **New work:** run `create-spec` to scaffold the next backlog item.
- **DirectRoute verification:** run the [smoke test checklist](#directroute-smoke-test) once on a machine with DirectRoute 26.x installed.

## Team setup (one command)

On Windows, from a fresh clone, run the launcher from the repo root — it
bootstraps every prerequisite (no admin required) and opens the wizard:

```powershell
.\run-local.cmd
```

Invoking PowerShell directly is equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

What it does, idempotently — detecting and reusing anything already installed:

1. Installs Node (official `win-x64` zip to a user dir) and `uv` if missing.
2. Creates the Python venv and installs `backend/requirements.txt`
   (`UV_SYSTEM_CERTS=true` for corporate TLS interception) — skipped when the
   venv already has its dependencies.
3. Runs `npm install`.
4. Probes bindable TCP ports (prefers API `8080` / UI `3000`), wires the
   Next.js `/api/*` proxy to the chosen API port, starts both servers, waits
   for the API to respond, then opens `http://localhost:<ui-port>/datasets/new`.

Both servers shut down together on Ctrl+C (or if either process exits). The UI
talks to the API through a same-origin proxy, so there is no CORS to configure
and the same command works behind a tunnel or on a teammate's machine.

### Flags

| Flag | Effect |
|------|--------|
| `-CheckOnly` | Report readiness (tools, ports, execution policy) and exit; starts nothing. |
| `-Dev` | Run the UI with `next dev` (hot reload) instead of a production build. |
| `-Share` | Also start a Cloudflare quick tunnel to the UI and print a public `https://<random>.trycloudflare.com` URL. |

```powershell
.\run-local.cmd -Share       # demo to a reviewer on another machine
.\run-local.cmd -CheckOnly   # just report what's installed and what's free
```

**`-Share` security:** the tunnel URL is ephemeral, world-reachable, and
bypasses your firewall/NAT. Treat it as a secret, only the proxied frontend is
exposed, and never demo with real PII or production credentials.

### Known-good demo depot

For a quick demo, enter **1216 Greenbrier Parkway, Chesapeake, VA 23320** and
pick stops by **state** (e.g. `VA`) or **zip** — coordinates are optional.
Paste Google Maps lat/long when you want **radius** selection (~191 candidates
within 50 miles for that address). See the depot note under
[Run the full stack manually](#run-the-full-stack-manually-fallback).

### Manual fallbacks (locked-down machines)

If a machine policy blocks a step, the launcher exits naming the blocked step
and its fallback. Common cases:

- **PATH not updated after an install:** a running shell does not inherit PATH
  changes, and user-local installs may create no global shim without Developer
  Mode/admin. The launcher prepends tool dirs in-session; if a manual command
  still can't find a tool, open a new terminal (or restart Cursor) and re-run.
- **Group-Policy execution policy:** the `.cmd` wrapper uses
  `-ExecutionPolicy Bypass` and the launcher always calls `npm.cmd` (never the
  blocked `npm.ps1`), but a GPO-enforced `Restricted`/`AllSigned` policy cannot
  be bypassed — contact IT. `-CheckOnly` flags this.
- **Reserved/held port:** port `8000` is often reserved on bootcamp images; the
  launcher probes for a bindable port (dual-stack) automatically, so no action
  is needed.
- **Corporate TLS breaks `uv`/`pip`:** the launcher sets `UV_SYSTEM_CERTS=true`.
  For manual installs, set it first: `$env:UV_SYSTEM_CERTS='true'`.

Non-Windows machines are not covered by the launcher — use the manual steps
below.

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

- `POST /api/trucks/generate` / `POST /api/stops/generate` /
  `POST /api/drproject-config/generate` / `POST /api/stops-csv/generate` —
  JSON metadata with base64-encoded file content
- `POST /api/trucks/download` / `POST /api/stops/download` /
  `POST /api/drproject-config/download` / `POST /api/stops-csv/download` —
  raw file bytes with `Content-Disposition`
  (`/api/stops-csv/*` also requires a non-empty `branch` on the request body)

Interactive docs at `http://127.0.0.1:8000/docs`.

The API allows CORS from the wizard's local dev origins (`http://localhost:3000`
and `http://127.0.0.1:3000`) out of the box. To point a differently-hosted UI
at it, set a comma-separated `WIZARD_ALLOWED_ORIGINS` before launching, e.g.
`$env:WIZARD_ALLOWED_ORIGINS = 'https://wizard.example.com'`.

## Wizard UI (frontend)

A Next.js (App Router) wizard walks a user through route and stop questions,
previews the dataset, then generates and downloads the truck, stop workbook,
and `DRProject.config` files via the API above. An optional stops CSV (with
Branch/Action columns) can be generated on the final download step. It
consumes the backend contract directly — no file formats are exposed during
the question flow.

```powershell
# Node is not preinstalled on bootcamp hosts; install once:
winget install OpenJS.NodeJS.LTS   # or unzip an official Node build to a user dir

npm install
copy .env.example .env             # proxy mode by default (NEXT_PUBLIC_API_BASE_URL left empty)
npm run dev                        # wizard at http://localhost:3000/datasets/new
```

Build, lint, and test the frontend:

```powershell
npm run build
npm run lint
npm test
```

The wizard calls `POST /api/trucks/generate`, then `POST /api/stops/generate`
(stop generation consumes the truck response), then
`POST /api/drproject-config/generate` (same `StopConfig` body), decodes the
base64 file content from each response, and offers one download button per
file. On the download step the user may optionally enter a Branch name and
request `POST /api/stops-csv/download` for an OIS-style stops CSV. Set
`NEXT_PUBLIC_API_BASE_URL` to the deployed API origin — its value is inlined at
`npm run build` time, so set it *before* building, not after. When the API is a
different origin, add that origin to the backend's `WIZARD_ALLOWED_ORIGINS`.

### Run the full stack manually (fallback)

Prefer `run-local.cmd` above. If you need to run the two processes by hand
(non-Windows, debugging, or a policy blocked the launcher), start them from the
repo root. Leaving `NEXT_PUBLIC_API_BASE_URL` empty keeps the UI in same-origin
proxy mode; the proxy defaults to `http://127.0.0.1:8080`, so run the API there:

```powershell
# Terminal 1 — API on 8080 (avoids the often-reserved port 8000)
.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8080 --reload

# Terminal 2 — wizard UI (proxy mode: relative /api -> 127.0.0.1:8080)
npm install
npm run dev                     # http://localhost:3000/datasets/new
```

To instead hit the API directly (no proxy), set
`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080` in `.env` *before* building —
the backend already allows the `localhost:3000` origin via CORS.

**Depot coordinates are optional.** Paste a Google Maps `lat, long` pair when
you have one; leave coords blank for address-only runs. The wizard defaults
stop selection to **state** (and offers **zip**); **radius** appears only when
at least one depot has valid coordinates. There is no geocode lookup or
runtime Save to `location_db.xlsx` — session manual stops go straight into
this run's stop file.

Radius mode still needs resolvable depot coordinates (pasted, or a match in
`backend/data/location_db.xlsx` by street then city+state+zip). For a
known-good radius demo use:

> **1216 Greenbrier Parkway, Chesapeake, VA 23320** (≈191 candidate stops
> within 50 miles when coords resolve)

State and zip modes filter `location_db` candidates directly and do not need
depot coordinates. Any real city/state/zip present in the database works for
matching (whitespace- and case-insensitive).

### Import into DirectRoute

The wizard produces three primary files:

- `fleet.truck` — tab-delimited truck/fleet file (SPEC-001)
- `stops.xlsx` — stop file (SPEC-002)
- `DRProject.config` — DirectRoute project configuration XML (SPEC-012)

Optionally download `stops.csv` (SPEC-016) from the same step after entering a
Branch name — leading Branch/Action columns plus the same stop content as the
xlsx, for OIS-style import testing.

Download the primary three from the final wizard step. Copy `DRProject.config`
into the DirectRoute user data directory configured under **File → Preferences**
(this app cannot write to that path from the browser). Then import the truck
and stop files into DirectRoute (trucks first, then stops) to build a routing
solution.

### DirectRoute smoke test

Run this once on a machine with DirectRoute 26.x installed to close the
manual acceptance criteria waived in CI:

1. Start the wizard: `.\run-local.cmd`
2. Walk through with the [known-good demo depot](#known-good-demo-depot)
3. Download all three files from the final step
4. Copy `DRProject.config` into your DirectRoute user data directory
5. Open DirectRoute — confirm the directory loads without config errors
6. Import the truck file, then the stop file — confirm no schema exceptions

The automated test suite covers the generator chain
(`tests/test_three_artifact_integration.py`) but cannot launch DirectRoute
itself.

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
