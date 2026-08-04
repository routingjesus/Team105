---
id: SPEC-004
title: "Local one-command wizard runner and shareable link"
category: feature
owner: Tyler Corr                         # git config user.name
authored_by: augmented                # augmented | automated
---

## Problem statement

The dataset-creation wizard (SPEC-003) only runs when a developer manually
starts two processes in two terminals — the FastAPI backend and the Next.js UI —
after hand-installing `uv`, Node, a Python venv, and npm dependencies, and after
working around a series of locked-down bootcamp Windows gotchas (stale PATH,
reserved port 8000, PowerShell execution policy, corporate TLS). SPEC-003's
AC7 ("a deployed bootcamp URL a reviewer can walk through") was waived because
no hosted target existed.

This blocks two audiences:

- **Reviewers/demo watchers**, who have no URL to try the wizard on.
- **Teammates** (three people on their own bootcamp machines), who cannot easily
  reproduce the working setup we assembled interactively.

The goal is the simplest reliable way to (a) run the full stack with **one
command** on any team member's Windows machine, self-bootstrapping the
prerequisites without admin, and (b) **optionally** expose a shareable public
URL for a demo — satisfying the intent behind SPEC-003 AC7 without standing up
hosting infrastructure.

## Acceptance criteria

1. Running `run-local.cmd` (or `powershell -ExecutionPolicy Bypass -File
   scripts/run-local.ps1`) from the repo root on a machine that already has the
   prerequisites starts both the FastAPI API and the Next.js UI, waits until the
   API responds, then opens the wizard in a browser at the served URL. Both
   `POST /api/trucks/generate` and `POST /api/stops/generate` succeed when driven
   through the UI, with no CORS error in the browser console.
2. The launcher selects a bindable TCP port for the API (probing, preferring
   8080 when free), passes it to uvicorn, and sets the Next.js rewrite target to
   that same port **before** building/starting the UI, so the `/api/*` proxy
   reaches the API regardless of which port was chosen.
3. When `NEXT_PUBLIC_API_BASE_URL` is empty or unset, `lib/api.ts` issues
   requests to relative paths (e.g. `/api/trucks/generate` with no host prefix)
   so they flow through the Next.js proxy same-origin; when the variable is
   explicitly set to an absolute URL, requests go to that base (existing
   direct-to-API behavior is unchanged). A unit test in `lib/api.test.ts`
   asserts the relative-path behavior for the empty/unset case.
4. On a checkout on a machine without Node or `uv`, running the launcher
   bootstraps the missing prerequisites without admin — `uv`, Node, the Python
   venv + `backend/requirements.txt`, and `npm install` — and reaches a working
   wizard; or, if a step is blocked by machine policy, it exits with a clear
   message naming the blocked step and its documented manual fallback. A
   `-CheckOnly` flag reports readiness (tools, ports, execution policy) without
   starting any servers.
5. Running the launcher with `-Share` starts a Cloudflare quick tunnel to the UI
   port and prints a public `https://<random>.trycloudflare.com` URL; a browser
   on another device can load that URL and complete the full wizard flow
   (generate and download both files) through the proxied API. Without `-Share`,
   no tunnel process is started.
6. From a **fresh clone into a new directory** on the developer's own machine,
   following only the README "Team setup" section and running the one command
   reaches a working wizard: the bootstrap detects and reuses already-present
   tools, installs anything missing, and starts the stack without any manual
   two-terminal steps. Any step that cannot be automated on a locked-down machine
   is documented as a manual fallback. (This clean-clone self-run is the
   replicability check; an actual teammate run is a nice-to-have, not required for
   done.)
7. The existing test suites stay green (frontend vitest and backend pytest) and
   `npm run build` succeeds with the rewrite configured. No backend generator,
   schema, spatial, or wizard request-mapping code is modified.

## Research

Findings are synthesized from four research lanes; inline provenance notes the
contributing lane(s).

- **No orchestrator exists today; this spec is net-new glue, not a refactor.**
  There is no root `scripts/` directory, no `run-local.*`, and no npm script that
  starts both processes — the README's two-terminal instructions are the only
  "launcher" (repo-analyst). The stack today runs uvicorn on the default port
  8000 (`backend.main:app`, no `--port`) and `npm run dev` on 3000, with
  `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` (repo-analyst).

- **Same-origin proxy is the right dev/demo topology, and it is already
  compatible with the endpoints.** All four API routes are under `/api/...`
  (`backend/main.py`), and the wizard's runtime calls are `postJson("/api/trucks/
  generate")` and `postJson("/api/stops/generate")` in `lib/api.ts` (downloads
  are decoded from base64 client-side, so only the generate surface must work
  through the proxy). A `/api/:path*` rewrite preserves the prefix end-to-end,
  and the browser stays on the Next origin, so CORS is bypassed locally
  (repo-analyst, prior-art). Proxying is preferred over CORS for local dev
  because CORS is browser-only (curl/pytest pass while the UI fails) and each new
  origin — a tunnel URL, a colleague's machine — would otherwise need backend
  allowlist edits (prior-art; corroborated by SPEC-003's CORS learning in
  `api-contracts.yaml`).

- **Correction to the design doc: the client default must be an empty string,
  not `"/api"`.** `postJson` builds `` `${API_BASE_URL}${path}` `` where `path`
  already begins with `/api/...`; a `"/api"` base would produce
  `/api/api/trucks/generate`. The proxy-mode default must be `""`. Also, `??`
  will not treat an explicit empty string as "unset", so base resolution must use
  `||` or an explicit trim/empty check (repo-analyst).

- **`next.config` env is inlined at build time — port selection must precede the
  build.** Next.js generates rewrites and inlines `process.env` reads in
  `next.config` at `next build` time (Vercel maintainer confirmation via docs
  lane). The launcher must probe the free port and set the proxy target env
  (e.g. `API_PROXY_TARGET`) in the same session **before** `next build` +
  `next start`; for `-Dev`, set it before `next dev` (config is read at dev-server
  start). Rewrites apply to both dev and production with the same config
  (docs-researcher). Verified current repo `next.config.ts` is minimal
  (`reactStrictMode` only), so adding an async `rewrites()` is a clean addition
  (repo-analyst).

- **No health route exists; readiness must poll an HTTP endpoint, not just an
  open port.** `backend/main.py` has no `/health`; FastAPI auto-serves
  `/openapi.json` and `/docs` (repo-analyst). Robust launchers poll an HTTP
  readiness endpoint before opening the browser, because port-open ≠ app-ready
  and TCP-only waits cause flaky demos (prior-art). Plan: poll
  `GET /openapi.json` on the API port.

- **Tunnel only the frontend port; the backend stays on loopback.** With a
  same-origin proxy, exposing the Next port is sufficient — the visitor's browser
  hits the tunnel host, and the Next *server* (on the host) reaches
  `127.0.0.1:<API_PORT>`; the tunnel hostname is irrelevant to the backend fetch
  (docs-researcher, prior-art). Cloudflare quick tunnels need an explicit
  `cloudflared tunnel --url http://localhost:<ui-port>`, require no account, print
  a random ephemeral `trycloudflare.com` URL, and cap at ~200 concurrent requests
  with no SSE — acceptable for a demo (docs-researcher). `cloudflared.exe` is a
  single binary downloadable without admin from GitHub releases (docs-researcher).
  Security caveat: a tunnel bypasses local firewall/NAT — keep it opt-in, treat
  the URL as a secret, expose only the proxied frontend, and never demo with real
  PII or production credentials (prior-art).

- **Self-bootstrapping on locked-down Windows has a known playbook (from
  SPEC-001/003), which this launcher must automate.** Reusable constraints
  (`environment.yaml` ledger + docs-researcher): winget installs may create no
  PATH shim without Developer Mode/admin, and running shells do not inherit PATH
  changes — the launcher must prepend tool dirs to `$env:Path` in-session and/or
  invoke binaries by absolute path, and prefer user-local installs (uv's
  `install.ps1` to `%USERPROFILE%\.local\bin`; Node's official `win-x64.zip`
  extracted to a user dir) over MSI installers that need admin (winget Node MSI
  failed with exit 1603). `UV_SYSTEM_CERTS=true` is required for uv/pip downloads
  through the corporate TLS proxy (`UV_NATIVE_TLS` is deprecated). PowerShell
  execution policy blocks `npm.ps1`, so use `npm.cmd` and a `.cmd` wrapper with
  `-ExecutionPolicy Bypass`; a Group-Policy-enforced policy cannot be bypassed and
  must be detected with a clear error (prior-art). Running the API via
  `.venv\Scripts\python.exe -m uvicorn` avoids needing `uv` on PATH at all
  (repo-analyst, environment.yaml).

- **Windows process teardown is manual — the launcher owns killing the tree.**
  Windows has no real SIGINT propagation to grandchildren; a parent script must
  explicitly kill the child process tree on Ctrl+C/exit or orphan uvicorn/next/
  cloudflared processes (prior-art). "One dies → stop the others" should be the
  default contract.

- **Existing stop generation depends on the already-merged `location_db`
  whitespace fix; the demo depot is known-good.** SPEC-003's fix to
  `load_location_db` is in tree, so teammates on a clean clone inherit it; docs
  should steer users to the verified demo depot `1216 Greenbrier Parkway,
  Chesapeake, VA 23320` to avoid stop-match failures (learnings-curator,
  `directroute-file-formats.yaml`). The bootstrap must not reintroduce compiled
  Python deps (e.g. `python-calamine`) that fail on bootcamp TLS; current
  `backend/requirements.txt` is already clean (learnings-curator).

- **No prior learning exists for launchers or public share links** — this is the
  first spec touching that class of problem, so the ledger has no directly
  reusable tunnel/launcher entry to carry forward (learnings-curator).

## Scope boundaries

- Out of scope: cloud/PaaS hosting, always-on public deployment, custom or
  stable domains, and TLS certificate provisioning.
- Out of scope: authentication, multi-user support, or persistence beyond the
  existing browser session.
- Out of scope: CI/CD pipelines and containerization (Docker/WSL) — locked-down
  Windows without admin cannot run them.
- Out of scope: any change to generation logic, Pydantic schemas, geocoding, or
  the wizard's request/response contract.
- Out of scope: a non-Windows (bash) launcher with feature parity. PowerShell is
  the target; other OSes are covered by the documented manual steps only.

## User scenarios

- **Solo demo (primary).** Tyler runs `run-local.cmd` from a fresh clone; the
  launcher bootstraps anything missing, starts both services, and opens the
  wizard. He generates a dataset for the demo depot and imports it into
  DirectRoute.
- **Remote reviewer.** Tyler runs `run-local.cmd` (or `-File ... -Share`), sends
  the printed `trycloudflare.com` link to a reviewer on another machine, who
  completes the wizard end-to-end in under three minutes.
- **Teammate onboarding.** A teammate clones the repo and follows the README
  "Team setup" section — one command — and reaches a working wizard on their own
  bootcamp machine without hand-holding.

## Non-functional requirements

- The demo flow completes in under 3 minutes for the demo scenario (2 weeks,
  ~20 stops), matching SPEC-003's target.
- The bootstrap is idempotent — safe to re-run on a partially-set-up machine.
- The tunnel is strictly opt-in (`-Share`); the default run stays local-only.
  Surface a short security note (ephemeral URL, no PII/prod credentials, only the
  proxied frontend is exposed).
- Runs on Windows PowerShell 5.1+ or PowerShell 7+, no admin rights required.
- Failure messages are actionable: name the blocked step and its manual
  fallback rather than failing silently.

## Implementation guidance

- **Files likely affected:**
  - `scripts/run-local.ps1` (new) — orchestrator + self-bootstrap. Responsibilities:
    preflight/`-CheckOnly` readiness report; install missing prerequisites without
    admin (uv via `install.ps1` or `winget --scope user`; Node via official
    `node-v<VER>-win-x64.zip` to a user/cache dir; `uv venv` + `uv pip install -r
    backend/requirements.txt` with `UV_SYSTEM_CERTS=true`; `npm.cmd install`);
    prepend tool dirs to `$env:Path` in-session; probe a free API port via
    `[System.Net.Sockets.TcpListener]::Create(0)` (prefer 8080); set
    `API_PROXY_TARGET=http://127.0.0.1:<port>` before `next build`; start API via
    `.venv\Scripts\python.exe -m uvicorn backend.main:app --port <port>`; build +
    `next start` (or `next dev` under `-Dev`); poll `GET /openapi.json` until
    ready; open the browser; under `-Share`, download/run `cloudflared tunnel
    --url http://localhost:3000` and print the URL. Kill the child process tree on
    Ctrl+C/exit. Flags: `-Share`, `-Dev`, `-CheckOnly`.
  - `run-local.cmd` (new) — double-click wrapper calling the `.ps1` with
    `-ExecutionPolicy Bypass -File`.
  - `next.config.ts` — add an async `rewrites()` returning
    `{ source: '/api/:path*', destination: `${API_PROXY_TARGET}/api/:path*` }`,
    defaulting `API_PROXY_TARGET` to `http://127.0.0.1:8080` when unset.
  - `lib/api.ts` — change base-URL resolution so an empty/unset
    `NEXT_PUBLIC_API_BASE_URL` yields `""` (relative), using `||`/explicit empty
    check rather than `??`; keep the trailing-slash strip and the explicit-set
    path unchanged.
  - `lib/api.test.ts` — add a test locking the relative-base contract (set env to
    `""`, `vi.resetModules()` + dynamic import, or test an extracted
    `resolveApiBaseUrl()` helper; assert the fetched URL is exactly
    `/api/trucks/generate`).
  - `.env.example` — document proxy mode (leave `NEXT_PUBLIC_API_BASE_URL` empty)
    and `API_PROXY_TARGET`.
  - `README.md` — add a "Team setup" one-command section; note the known-good demo
    depot; update stale port-8000 guidance; document manual fallbacks and the
    fresh-terminal PATH note.

- **Files NOT to modify:** `backend/generators/truck.py`, `backend/generators/
  stop.py`, `backend/schemas/*.py`, `backend/services/spatial.py`,
  `backend/main.py` (endpoints + CORS already correct for both modes),
  `components/wizard/*`, `lib/build-config.ts`, `lib/wizard-schema.ts`,
  `lib/wizard-types.ts`, backend `tests/**`, and the completed
  `.spec/SPEC-001-*` / `.spec/SPEC-002-*` / `.spec/SPEC-003-*` directories.

- **Patterns to follow:** bootstrap sequence from README + `.spec/_ledger/
  environment.yaml`; the existing `lib/api.ts` default-base pattern (extend, don't
  rewrite); vitest stub-`fetch`-and-inspect-`mock.calls` pattern already in
  `lib/api.test.ts`; wizard entry at `app/datasets/new/page.tsx`
  (`http://localhost:3000/datasets/new`).

- **Test expectations:** new `lib/api.test.ts` case for the relative base;
  existing frontend suite (37 tests) and backend suite (83 tests) stay green;
  `npm run build` succeeds with the rewrite. Launcher behavior (bootstrap,
  tunnel) is validated by manual smoke = AC1/AC4/AC5, since it is environment- and
  network-dependent.

- **Local-only artifacts:** describe tool/cache locations generically (a user
  profile dir, a repo-local cache) rather than pasting machine-specific absolute
  paths; do not commit `.venv/`, `node_modules/`, `.next/`, `.env`, or downloaded
  binaries (already gitignored).
