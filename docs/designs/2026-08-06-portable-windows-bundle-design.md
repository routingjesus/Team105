# Portable Self-Contained Windows Bundle — Design

- **Date:** 2026-08-06
- **Status:** Approved (brainstorming output)
- **Related:** SPEC-004 (local runner + share), SPEC-013 (launcher readiness),
  SPEC-017 (writable location DB / geocoding); evolves distribution beyond
  `run-local.cmd` without replacing the in-repo developer launcher

## Problem / goal

The Dataset Creation Wizard is a two-process local web app (Next.js UI +
FastAPI API). Today, anyone who wants to run it must clone the repo and use
`run-local.cmd`, which bootstraps Node/`uv`, installs deps, and may rebuild the
UI on each machine. That is fine for developers; it is not a
**self-contained** deliverable for “anyone on Windows.”

Goal: ship a **portable Windows zip** that embeds the runtimes and a prebuilt
UI so an end user can extract and double-click — no Git, no Node/Python
install, no `npm install`, no `next build` on their machine. Delivery format is
flexible (zip folder now; optional installer wrapper later). True single-file
`.exe` that embeds Next SSR + pandas is out of scope.

## Chosen approach: portable runtime folder (Approach 1)

Alternatives considered and rejected:

- **Static Next export + PyInstaller/Nuitka (Approach 2)** — closer to one
  runtime family, but drops Next server features, reworks the `/api` proxy
  model, and makes pandas packaging the hard path. More rewrite risk than
  needed.
- **Electron/Tauri shell (Approach 3)** — feels app-like, but still ships Node +
  Python sidecars and adds shell/signing surface without removing the
  multi-runtime problem.

### Architecture

Deliverable: `Team105-Wizard-win-x64.zip` → extract → double-click
`Team105-Wizard.cmd` (or a thin `.exe` stub that invokes the same script).

Conceptual layout:

```
Team105-Wizard/
  Team105-Wizard.cmd
  runtime/
    node/                 # embedded Node win-x64
    python/               # embedded CPython + preinstalled site-packages
  app/
    backend/              # FastAPI + data/ (location_db, DRProject.config)
    .next/ or standalone/ # prebuilt Next production output
  scripts/
    launch.ps1            # start API + UI, open browser, tear down
```

Runtime topology (same idea as SPEC-004, packaged differently):

1. Launcher requires API port **8080** free (dual-stack probe).
2. Starts uvicorn from embedded Python against bundled `backend`.
3. Starts Next from embedded Node against **prebuilt** UI (no build on user PC).
4. Opens `http://127.0.0.1:<ui-port>/datasets/new`; `/api/*` stays same-origin
   via Next rewrites.

**Hard constraint:** `API_PROXY_TARGET` in `next.config.ts` is baked at
**build** time. The package job builds once with
`API_PROXY_TARGET=http://127.0.0.1:8080`. The launcher therefore **must** bind
the API on 8080 (or fail clearly). UI port may float (prefer 3000). A thin
outer reverse proxy for flexible API ports is a later enhancement, not v1.

**Build-time vs run-time:**

- **Package job (dev/CI):** embed runtimes → install Python deps → `npm ci` →
  `next build` with fixed proxy target → assemble zip.
- **End user:** unzip → launch → no downloads, no build.

**Out of scope for v1:** Electron/Tauri, `-Share` / cloudflared, code signing,
Program Files install with AppData data migration, rewriting to static export.

### Components

1. **Package builder** (`scripts/package-portable.ps1` or equivalent) — pinned
   Node + Python into `runtime/`, preinstall backend requirements, build Next
   with fixed `API_PROXY_TARGET`, copy app + data + launcher, emit the zip.
2. **Launcher** — `Team105-Wizard.cmd` → `scripts/launch.ps1`, evolved from
   `scripts/run-local.ps1` with bootstrap downloads removed; paths relative to
   bundle root; SPEC-013-style deep readiness probes retained in spirit.
3. **Embedded runtimes** — official Node win-x64; standalone/embeddable Python
   with wheels (pandas/numpy/openpyxl/fastapi). No `uv` at run time.
4. **App payload** — FastAPI `backend/` including `data/location_db.xlsx` and
   `DRProject.config`; prebuilt Next; client keeps relative `/api/...`
   (`lib/api.ts`).
5. **Optional later:** Inno/NSIS installer that unpacks the same folder and
   adds a Start Menu shortcut — not required for v1.

The existing in-repo `run-local.cmd` / `scripts/run-local.ps1` remains the
developer path; the portable launcher is a separate distribution artifact.

### Data flow

**Package time:** pinned runtimes → Python deps in `runtime/python` → `npm ci`
→ `API_PROXY_TARGET=http://127.0.0.1:8080` → `next build` → copy
`backend/` + UI build + launcher → zip.

**Run time:** double-click → uvicorn on **8080** + Next on a free UI port →
browser → relative `/api/...` → Next rewrite (baked to 8080) → FastAPI →
generators use bundled `backend/data/*` → downloads as today.

**Network:**

- Offline: truck / stop / DRProject / stops CSV from bundled location DB.
- Online: manual geocoding (SPEC-017) needs `TRIMBLE_MAPS_API_KEY` in the
  environment — document how to set it; do not ship a key in the zip.

**Writability:** v1 assumes extract to a user-writable location (Desktop /
Documents) so `location_db.xlsx` appends work. Locked Program Files installs
are out of scope until an AppData data directory exists.

### Error handling

- **8080 busy** → clear exit; do not silently move the API.
- **UI port busy** → probe next free port (preferred 3000+).
- **Missing/corrupt runtime or prebuilt UI** → fail naming the path; no
  download/rebuild on the user machine.
- **API readiness timeout** → kill children; surface a useful hint.
- **Ctrl+C / child death** → tear down the process tree.
- **Geocoding without key** → existing API error behavior.
- **Execution policy** → `.cmd` uses `-ExecutionPolicy Bypass`; GPO block →
  message and stop.
- **Builder failures** → fail the package job; do not publish a half bundle.
- **SmartScreen / AV** → document first-run Unblock / Run anyway; signing is
  follow-on.

### Testing

- Existing frontend vitest and backend pytest stay green; packaging must not
  change generator/API contracts.
- Builder smoke: zip contains expected roots; unzip + launch → API ready →
  wizard path responds; happy-path generate truck + stop (and optionally
  DRProject).
- Launcher negatives: 8080 occupied → port-busy message; missing
  `runtime/node` (or Python) → named failure.
- Offline: core generate/download works without network when geocoding unused.
- Non-goals for v1 tests: signing, installer UI, `-Share`, Program Files +
  AppData.

## Success criteria (for a future spec)

1. A user with no Node/Python/Git can extract the zip, run the launcher, and
   complete the wizard’s core generate/download flow.
2. No end-user bootstrap downloads or `next build`.
3. API forced to 8080 with a clear failure if unavailable; UI port may float.
4. Bundled `location_db.xlsx` and `DRProject.config` are present and usable;
   location appends work when the extract dir is writable.
5. Developer `run-local` path remains intact for day-to-day work.

## Follow-ons (explicitly deferred)

- Inno/NSIS installer wrapper around the same folder
- Code signing to reduce SmartScreen friction
- Outer reverse proxy so the API port can float
- AppData data directory for non-writable install locations
- Optional `-Share` in the portable launcher
