---
id: SPEC-018
title: "Portable self-contained Windows wizard bundle"
category: feature
owner: Tye Lofts                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

The Dataset Creation Wizard runs as a two-process local web app (Next.js UI +
FastAPI API). Today the only supported path for a non-developer is clone the
repo and run `run-local.cmd`, which bootstraps Node/`uv`, installs dependencies,
and may rebuild the UI on each machine. That blocks “anyone on Windows” who
should be able to extract a package and double-click — without Git, without
installing Node or Python, and without `npm install` / `next build` on their PC.

This matters for demos and handoffs to reviewers or teammates who should not
need the developer toolchain. The in-repo `run-local` path remains the day-to-day
developer workflow; this spec adds a separate **portable distribution artifact**.

## Acceptance criteria

1. A packaging script (run on a developer/CI machine) produces a Windows zip
   (e.g. `Team105-Wizard-win-x64.zip`) whose contents include embedded Node and
   Python runtimes, a prebuilt Next UI, the FastAPI `backend/` tree with
   `backend/data/location_db.xlsx` and `backend/data/DRProject.config`, and a
   double-clickable launcher (`.cmd` and/or thin stub). The zip must not require
   the consumer to have Node, Python, Git, or a repo clone.
2. On a clean Windows machine (or a directory with no project toolchain),
   extracting the zip and running the launcher starts the API on port **8080**
   and the UI on a free port (prefer 3000), opens the wizard at
   `/datasets/new`, and allows completing core generate/download for truck and
   stop files through the UI without any end-user bootstrap download or
   `next build`.
3. If port **8080** is unavailable, the launcher exits with a clear
   human-readable error and does **not** silently bind the API to a different
   port (prebuilt Next `API_PROXY_TARGET` is fixed at package time to
   `http://127.0.0.1:8080`).
4. If a required embedded runtime or prebuilt UI path is missing/corrupt, the
   launcher exits naming the missing path and does not attempt to download or
   rebuild on the end-user machine.
5. Existing developer workflow is unchanged: `run-local.cmd` /
   `scripts/run-local.ps1` still bootstrap and run from a repo checkout; existing
   frontend vitest and backend pytest suites stay green; generator/API contracts
   are not changed by this packaging work.
6. README (or a short bundle README inside the zip) documents: extract to a
   writable location, how to launch, the 8080 requirement, SmartScreen/unblock
   guidance, and that optional geocoding needs `TRIMBLE_MAPS_API_KEY` in the
   environment (no key shipped in the zip).

## Research

Findings synthesized from four research lanes; inline provenance notes
contributing lane(s). Design baseline:
`docs/designs/2026-08-06-portable-windows-bundle-design.md`.

- **Portable delivery is a folder zip with embedded runtimes + prebuilt UI,
  not a fused single-exe.** Industry and docs align on Node win-x64 zip +
  vendored Python + Next standalone (or full `next start` payload) + `.cmd`
  launcher. PyInstaller-style onefile is a poor fit for pandas-sized payloads
  (temp unpack, AV scans). (prior-art-researcher, docs-researcher)

- **Package-time bake of `API_PROXY_TARGET=http://127.0.0.1:8080` and empty
  `NEXT_PUBLIC_API_BASE_URL` (via `.env.local`) is mandatory.**
  `next.config.ts` rewrites are build-time; Windows cannot inject an empty
  process env var for Next. Dev `run-local` may float the API port; the
  portable launcher **must** require 8080 or fail clearly — do not silently
  rebind. (repo-analyst, learnings-curator)

- **Reuse launcher mechanics from `scripts/run-local.ps1`; do not replace the
  developer path.** Dual-stack port probes (`IPv6Any` + DualMode +
  `Get-NetTCPConnection`), `Start-Tracked` + `taskkill /T /F` teardown,
  `Wait-HttpReady` on `/openapi.json`, SPEC-013 deep import probes with
  `$ErrorActionPreference` relaxed inside probes, `.cmd` with
  `-ExecutionPolicy Bypass`. Portable drops bootstrap downloads/`next build`
  on the end-user machine. (repo-analyst, learnings-curator)

- **Prefer Next `output: 'standalone'` for a smaller UI payload.** After
  build, manually copy `public` → `standalone/public` and `.next/static` →
  `standalone/.next/static`; launch with `node server.js` (not `next start`).
  Alternative (simpler, larger): ship enough of `node_modules` + `next start`.
  Rewrites still bake at build either way. (docs-researcher, repo-analyst)

- **Embeddable CPython has no runtime pip — vendor wheels at package time.**
  Use `pip install --target` (or equivalent) into the embedded tree during
  `package-portable`; may need `pythonXX._pth` / `import site`. Pandas/numpy
  dominate size. No `uv` at end-user runtime; builder may still use uv with
  `UV_SYSTEM_CERTS=true` on corporate TLS hosts. (docs-researcher,
  learnings-curator)

- **`location_db.xlsx` must remain writable in the extract directory.**
  `backend/services/location_store.py` uses filelock + atomic replace beside
  the workbook (SPEC-017). Document extract-to-Documents/Desktop; Program
  Files / AppData migration stays out of scope. Do not ship
  `TRIMBLE_MAPS_API_KEY` in the zip. (repo-analyst, learnings-curator)

- **SmartScreen + MOTW are expected first-run friction for unsigned zips.**
  Document “More info → Run anyway” and `Unblock-File` (or unblock before
  extract) so `RemoteSigned` does not block the `.ps1`. Code signing is
  deferred. (docs-researcher, prior-art-researcher; no prior ledger learning)

- **Keep generator/API contracts and `lib/api.ts` untouched.** Relative
  `/api/...` client paths already match proxy mode; packaging should not
  change CORS/direct-URL behavior. (repo-analyst, learnings-curator)

## Scope boundaries

- Inno/NSIS installer wrapper, code signing, and Auto-update
- Electron/Tauri (or other desktop shells)
- Collapsing the UI to static export + PyInstaller/Nuitka
- Outer reverse proxy so the API port can float
- Program Files install with AppData data-directory migration
- Portable-launcher `-Share` / cloudflared
- Non-Windows bundles
- Changing truck/stop/DRProject/CSV generator behavior or API schemas

## User scenarios

- **Reviewer / teammate without toolchain:** Receives the zip, extracts to
  Documents/Desktop, double-clicks the launcher, completes the wizard, downloads
  files — no clone or install steps.
- **Developer packaging:** Runs the package script on a machine that already
  builds the project, produces the zip for distribution.
- **Developer day-to-day:** Continues using `run-local.cmd` from a git checkout;
  portable bundle is optional distribution, not a replacement.

## Non-functional requirements

- Bundle may be hundreds of MB (embedded Node + Python + pandas); size is
  acceptable for v1.
- Prefer no admin rights to run (user-writable extract location).
- Unsigned artifacts may trigger SmartScreen; document, do not block on signing.
- Core generation works offline; geocoding remains optional/online.

## Implementation guidance

- **Design reference:** `docs/designs/2026-08-06-portable-windows-bundle-design.md`
- **Files likely affected:**
  - `scripts/package-portable.ps1` (new) — pin/download Node + embeddable
    Python, vendor `backend/requirements.txt`, set
    `API_PROXY_TARGET=http://127.0.0.1:8080` and empty
    `NEXT_PUBLIC_API_BASE_URL` via `.env.local`, `next build`, assemble zip
  - `scripts/launch-portable.ps1` (new) — or similarly named bundle launcher
    (ports, uvicorn, Next server, readiness, teardown); no bootstrap downloads
  - Bundle root `Team105-Wizard.cmd` (emitted into the zip, may live under
    `packaging/` or be generated by the package script)
  - Bundle `README.txt` / short docs inside the zip
  - `next.config.ts` — add `output: 'standalone'` if choosing the standalone
    path (additive; keep existing rewrites)
  - `package.json` — optional `package:portable` script
  - Root `README.md` — link how to build/distribute the portable zip
- **Files NOT to modify:**
  - `run-local.cmd`, `scripts/run-local.ps1` (developer path stays as-is;
    may **copy** helpers, not rewrite behavior)
  - `lib/api.ts`, `backend/main.py`, `backend/generators/**`,
    `backend/schemas/**`, `backend/services/spatial.py`,
    `backend/services/geocoding.py`, `backend/services/location_store.py`
  - Generator tests’ behavioral expectations (`tests/**` API contracts)
- **Patterns to follow:**
  - Port/process/readiness/teardown: `scripts/run-local.ps1`
    (`Test-PortFree`, `Start-Tracked`, `Wait-HttpReady`, dual-stack probes)
  - Proxy bake: `next.config.ts` rewrites + SPEC-004 `.env.local` empty
    `NEXT_PUBLIC_API_BASE_URL=` pattern
  - Deep readiness probes: SPEC-013 (`import backend.main`, `next.cmd` presence)
  - Standalone asset copy: Next `output` docs / with-docker example
    (`public` + `.next/static` into standalone tree)
  - Embedded Node: official `node-v*-win-x64.zip` (same source as launcher
    bootstrap), not winget MSI
  - Working directory for uvicorn must resolve `backend.main` (bundle `app/`
    root equivalent to today’s repo root)
- **Test expectations:**
  - Existing frontend vitest + backend pytest remain green
  - Package script smoke: zip contains `runtime/node`, embedded Python,
    `backend/data/location_db.xlsx`, `DRProject.config`, prebuilt UI, launcher
  - Unzip + launch: API on 8080, wizard reachable, truck + stop generate/download
  - Negatives: 8080 occupied → clear failure (no silent API port change);
    missing `runtime/node` (or Python) → named path error
  - Offline: core generate works without network when geocoding unused
