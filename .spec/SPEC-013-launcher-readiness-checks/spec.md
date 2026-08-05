---
id: SPEC-013
title: "Launcher readiness checks miss half-installed dependencies"
category: bug
owner: Tyler Corr                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

`scripts/run-local.ps1` (the SPEC-004 one-command launcher) decides whether to
skip its bootstrap steps using shallow readiness probes:

- `Test-BackendReady` imports only `uvicorn` and `fastapi`, but the API's
  import chain also needs `pandas`, `numpy`, `openpyxl`, `xlrd`, and
  `xlsxwriter` (see `backend/requirements.txt`).
- `Ensure-FrontendDeps` only tests that the `node_modules` *folder exists*,
  not that the install completed (the `node_modules\.bin\next.cmd` shim that
  `npm run build`/`npm run start` invoke).

An interrupted first-time bootstrap (Ctrl+C, network drop, or corporate-TLS
failure partway through `uv pip install` or `npm install`) leaves a partial
state that passes both probes. On re-run the launcher reports `[ok]`, skips
the installs, and crashes at runtime instead: uvicorn dies with
`ModuleNotFoundError: No module named 'pandas'` and the UI build fails with
`'next' is not recognized`.

This hits exactly the audience the launcher exists for — teammates
bootstrapping fresh Windows machines. Observed in the wild on a pod member's
machine on 2026-08-05.

## Acceptance criteria

1. With a `.venv` that imports `fastapi`/`uvicorn` but is missing at least one
   backend runtime dependency (e.g. `pandas` uninstalled), running
   `run-local.cmd` re-installs `backend/requirements.txt` into the existing
   venv (no `[ok] Backend venv + dependencies present` skip) and the API
   starts and answers its readiness probe.
2. With `node_modules` present but `node_modules\.bin\next.cmd` absent,
   running `run-local.cmd` runs `npm install` (no `[ok] node_modules present`
   skip) and the UI build/start succeeds.
3. `run-local.cmd -CheckOnly` reports each half-installed state above as a
   warning naming the repair the launcher would perform, not as `[ok]`.
4. On a fully healthy machine the launcher's fast path is unchanged: both
   installs are skipped and total startup behavior is identical to today.

## Reproduction

- **Input:** Fresh clone; run `.\run-local.cmd`; interrupt the first bootstrap
  partway (after `fastapi`/`uvicorn` wheels install but before `pandas`, and
  after `npm install` creates `node_modules` but before it links the `next`
  shim into `node_modules\.bin`). Re-run `.\run-local.cmd`.
- **Actual output:** `[ok] Backend venv + dependencies present`,
  `[ok] node_modules present`; both installs skipped; uvicorn traceback ending
  `ModuleNotFoundError: No module named 'pandas'` (raised from
  `backend/generators/stop.py` line 17 via `backend/main.py`); `next build`
  fails with `'next' is not recognized as an internal or external command`.
- **Expected output:** launcher detects both incomplete installs, re-runs
  `uv pip install -r backend/requirements.txt` and `npm install`, then starts
  both services normally.
- **Environment:** Windows 10/11, PowerShell 5.1 via `run-local.cmd`; Node
  v24.14.1; uv-managed CPython 3.12 venv; observed on a teammate's machine
  2026-08-05.

## Research

- The shallow backend probe is a designed-in trade-off, not an accident:
  SPEC-004 recorded the decision "skip the uv install entirely when the venv
  already imports its deps" with a two-package sample. The fix must deepen the
  probe while preserving that fast path — skip installs when the venv is
  *truly* complete (learnings-curator, repo-analyst).
- Probe what the launcher runs next, not a sample of dependencies. Industry
  precedent ranks deep entry-point probes first for high-frequency launchers
  with existing idempotent repair paths: `import backend.main` is exactly what
  uvicorn executes, and `node_modules\.bin\next.cmd` is exactly what
  `npm run build`/`start`/`dev` resolve (npm v11 still creates `.cmd` shims in
  `.bin` via cmd-shim on Windows) (prior-art-researcher, docs-researcher).
- `import backend.main` is a safe probe: `backend/main.py` does no file I/O at
  import time — `location_db.xlsx` and the DRProject XML template both load
  lazily inside request handlers. The import pulls the full runtime chain
  (pandas, numpy, excel libs) and exits non-zero on any ImportError. Cost is a
  cold pandas/numpy import (~seconds once per launch) — acceptable; a
  hash-stamp fast path layered on top is the future optimization if latency
  ever matters, explicitly out of scope here (repo-analyst,
  docs-researcher, prior-art-researcher).
- CWD constraint is load-bearing: `backend` is not installed into the venv, so
  the probe resolves it only when the repo root is the working directory
  (`python -c` prepends CWD to `sys.path`). `Ensure-Backend` already runs from
  repo root, but the `-CheckOnly` block (line ~365) calls `Test-BackendReady`
  from the invoker's CWD — the probe must `Push-Location $RepoRoot` itself
  (repo-analyst, docs-researcher).
- `-CheckOnly` has *duplicate* inline shallow checks (lines ~373–377 test bare
  `.venv` / `node_modules` folder existence) that would keep printing `[ok]`
  on half-installed machines even after the helpers are fixed. AC3 requires
  aligning or removing them (repo-analyst).
- Keep the existing repair commands; do not "upgrade" them.
  `uv pip install -r` is documented as additive/idempotent into an existing
  venv (installs missing packages, keeps the rest) — correct for repair.
  `uv pip sync` must NOT be used (`backend/requirements.txt` pins only 9
  top-level packages; sync strips unlisted transitives), and `npm ci` deletes
  `node_modules` wholesale — wrong latency profile for a per-demo launcher
  (docs-researcher, prior-art-researcher).
- Graph-consistency tools were evaluated and rejected as gates: `uv pip check`
  and `npm ls` verify that *installed* packages are mutually consistent, not
  that everything in requirements/lockfile is present — a missing `pandas`
  with no installed dependent can pass `uv pip check`, and `npm ls` has
  exit-code noise on peer/extraneous/optional deps (docs-researcher,
  prior-art-researcher).
- Accepted residual gap: `next.cmd` existing does not prove the optional
  platform SWC binary (`@next/swc-win32-x64-msvc`) installed; `npm run build`
  itself catches that, and its existing `Stop-WithError` fallback already
  names the manual repair (docs-researcher).
- Regression guardrails from the ledger: keep dual-stack port probing, keep
  `npm.cmd` (never `npm.ps1`), keep `UV_SYSTEM_CERTS=true`, and don't disturb
  the `.env.local` proxy-forcing block while editing the script
  (learnings-curator).

## Scope boundaries

- No changes to application code: `backend/**`, `app/**`, `components/**`,
  `lib/**`, `next.config.ts`, `package.json`, `backend/requirements.txt`.
- No lockfile/integrity verification (`npm ci`, hash checks, `uv sync`) — this
  spec only deepens the readiness probes and reuses the existing repair paths.
- No retry/resume logic for interrupted downloads; a failed install still
  exits with the existing `Stop-WithError` guidance.
- Non-Windows launcher support stays out of scope (unchanged from SPEC-004).

## Error evidence

```text
[ok]   Backend venv + dependencies present
[ok]   node_modules present
==> Starting API (uvicorn) on 127.0.0.1:8080
...
  File "C:\...\Team105\backend\generators\stop.py", line 17, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'

> team105-dataset-wizard@0.1.0 build
> next build
'next' is not recognized as an internal or external command
ERROR: next build failed (exit 1).
```

## Root cause analysis

Introduced with the launcher itself in SPEC-004 (PR #6). `Test-BackendReady`
(`scripts/run-local.ps1`, ~lines 159–163) was written to answer "can we skip
installing uv?" and only samples two packages; `Ensure-FrontendDeps`
(~lines 200–204) equates folder existence with install completion. Neither
probe models the interrupted-install state, which is common on first runs
(corporate TLS, impatient Ctrl+C during multi-minute downloads). The fix is to
make each probe verify what the launcher actually runs next: the API's real
import chain, and the `next` shim that `npm run build`/`start` resolve.

## Blast radius

Single PowerShell script used only for local development orchestration; no
application, API, or CI surface. Worst case is a false-negative probe causing
a redundant (idempotent) `uv pip install` / `npm install` on startup.

## Implementation guidance

- **Files likely affected:** `scripts/run-local.ps1` only, in three places:
  - `Test-BackendReady` (~lines 159–163): replace
    `-c "import uvicorn, fastapi"` with `-c "import backend.main"`, and make
    the function `Push-Location $RepoRoot` / `Pop-Location` around the probe
    so it is CWD-independent (the `-CheckOnly` path at ~line 365 calls it from
    the invoker's CWD).
  - `Ensure-FrontendDeps` (~lines 200–204): probe
    `Test-Path (Join-Path $RepoRoot 'node_modules\.bin\next.cmd')` instead of
    the bare `node_modules` folder.
  - `-CheckOnly` report block (~lines 358–400): the duplicate inline `.venv` /
    `node_modules` folder checks at ~373–377 must use the same deep probes (or
    be folded into the helper-based lines) so degraded states emit
    `Write-Warn2` in the established phrasing, e.g.
    `"node_modules incomplete (next shim missing) - launcher would run npm install"`.
- **Files NOT to modify:** `backend/**`, `app/**`, `components/**`, `lib/**`,
  `next.config.ts`, `package.json`, `backend/requirements.txt`,
  `run-local.cmd`.
- **Patterns to follow:** keep the existing repair paths untouched —
  `uv pip install --python $VenvPython -r backend/requirements.txt` (additive,
  idempotent; do not switch to `uv pip sync`) and `& $npmCmd install` (do not
  switch to `npm ci`). Follow the script's `Write-Ok` / `Write-Warn2` /
  `Stop-WithError` conventions and the `-CheckOnly`
  `"... - launcher would <repair>"` warning shape. Verified on a healthy
  install: `.venv\Scripts\python.exe -c "import backend.main"` succeeds from
  the repo root (no import-time file I/O), and `.bin` contains `next`,
  `next.cmd`, `next.ps1` after a completed `npm install`.
- **Test expectations:** manual simulation on a healthy checkout —
  (a) `uv pip uninstall pandas --python .venv\Scripts\python.exe`, then
  `run-local.cmd -CheckOnly` warns (not `[ok]`) and a full run re-installs and
  starts the API (AC1/AC3); (b) rename `node_modules\.bin\next.cmd` away,
  same expectations for the UI side (AC2/AC3); (c) restore both, confirm the
  fast path skips both installs (AC4); (d) run `-CheckOnly` from a directory
  other than the repo root on a healthy install — must still report `[ok]`
  (CWD independence). Existing suites (`npm test`, `npm run build`, pytest)
  stay green — no app code changes.
