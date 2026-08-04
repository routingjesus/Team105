# Local One-Command Runner + Shareable Link — Design

- **Date:** 2026-08-04
- **Status:** Draft (brainstorming output)
- **Related:** SPEC-003 (Dataset Creation Wizard UI, merged in PR #5); satisfies the intent behind SPEC-003 **AC7** (a URL a reviewer can walk the wizard through)

## Problem / goal

SPEC-003 AC7 wants a "deployed bootcamp URL" a reviewer can complete the wizard
on in under 3 minutes. There is no hosting infrastructure, and the team works on
locked-down bootcamp Windows machines: no preinstalled Node/`uv`/Docker, no
admin rights, stale integrated-terminal PATH, blocked/reserved ports, and a
PowerShell execution policy that blocks `npm.ps1`.

Goal: the simplest reliable way to (a) run the full stack (FastAPI API + Next.js
UI) with **one command** on any team member's machine, and (b) optionally expose
a **shareable public URL** for a demo. Primary audience is the three team members
on their own machines; a shareable link is a bonus.

## Chosen approach: native self-bootstrapping launcher + same-origin proxy + optional tunnel

Alternatives considered and rejected:

- **Docker Compose** — clean in principle, but neither Docker nor WSL is
  installed and installing them needs admin + reboot. The heaviest path given
  the constraints, not the simplest.
- **Free PaaS (Render/Railway/Fly)** — a real always-on URL, but requires an
  account, service config, hosting the ~1.5 MB `location_db.xlsx`, and split
  UI/API with public CORS. Overkill for a mainly-local demo.

### Architecture

Two local processes orchestrated by one script, made shareable by a same-origin
proxy:

- **FastAPI** (uvicorn) on an auto-picked free port (default **8080**).
- **Next.js** on **3000**.
- A **Next.js server-side rewrite** proxies `/api/:path*` →
  `http://127.0.0.1:<API_PORT>/api/:path*`. The browser only ever talks to the
  Next origin, so (a) there is no CORS concern locally, and (b) a single tunnel
  to the Next app exposes the whole application.

### Components (files)

- `scripts/run-local.ps1` — orchestrator **and** self-bootstrap:
  - **Preflight/bootstrap** (no admin): detect and install prerequisites the way
    we did manually in-session — `uv` via winget (+ `UV_SYSTEM_CERTS` for the
    corporate TLS proxy), Node via a user-local zip (+ persist PATH), create the
    venv via `uv`, `npm install`.
  - Session PATH setup for `uv`/Node; auto-pick a free API port; production
    `build` then `next start` + `uvicorn`; health-wait; open the browser.
  - Flags: `-Share` (Cloudflare quick tunnel via `cloudflared`, downloaded on
    demand), `-Dev` (`next dev` for iteration), `-CheckOnly` (bootstrap/readiness
    report only, no servers).
  - Ctrl+C stops both child processes.
- `run-local.cmd` — double-click wrapper that invokes the `.ps1` with
  `-ExecutionPolicy Bypass` (sidesteps the `npm.ps1` policy error).
- `next.config.ts` — add `rewrites()` targeting `API_PROXY_TARGET`
  (default `http://127.0.0.1:8080`).
- `lib/api.ts` — use a **relative** `/api` base when `NEXT_PUBLIC_API_BASE_URL`
  is empty (proxy mode); unchanged behavior when the var is set.
- `.env.example` + README "Team setup" section — the one command, the known
  manual fallbacks, and the fresh-terminal note.

### Data flow

Browser (`localhost:3000` or the tunnel URL) → Next app → wizard →
`fetch('/api/trucks/generate')` → **Next rewrite** → uvicorn `:<PORT>` →
response → download. Stops follow the same path. Remote visitors work
identically: their browser hits the Next origin, and the Next *server* (on the
host machine) reaches the local API.

### Error handling / edge cases

- **Port busy** (8000 was blocked in-session): probe and pick a free port, pass
  it to both uvicorn and the proxy target.
- **Missing tools**: bootstrap installs them; on a locked-down machine where
  automation can't (winget blocked, user-local install forbidden), emit a clear
  message and a documented manual fallback rather than failing silently.
- **Execution policy**: the `.cmd` wrapper avoids it.
- **`cloudflared` missing** (only under `-Share`): download the official single
  binary to a user dir, else skip with a message — never blocks the local run.
- **First run needs network** (through the corporate proxy, handled via
  `UV_SYSTEM_CERTS` and PowerShell's schannel).
- **Integrated-terminal PATH staleness** after first-run installs: documented
  (open a fresh terminal / restart the editor).
- **Prod build default** gives a clean demo (no dev hydration warning); `-Dev`
  is available for iteration.

### Replicability across the team (explicit)

The self-bootstrapping launcher is what makes a clean clone → one command →
working wizard on a teammate's machine, matching the manual fixes done
in-session. This is an explicit acceptance criterion, not an afterthought:
acceptance includes a second team member running the one command on a clean
checkout and reaching the wizard, with any non-automatable step documented.

### Testing

- Unit guardrail in `lib/api.test.ts`: an empty base ⇒ requests target the
  relative `/api/...` path (locks the proxy contract).
- `npm run build` succeeds with the rewrite; existing suites stay green
  (37 frontend / 83 backend).
- Manual smoke = the AC7 acceptance: one command → wizard generates + both
  downloads; `-Share` → open the tunnel URL from another device and complete the
  flow in under 3 minutes for the demo scenario (Chesapeake, VA depot; 2 weeks;
  ~20 stops).

## Acceptance criteria (seeds for the spec)

1. One command (`run-local.cmd`) from the repo root starts both services and
   opens the wizard, reachable in a browser.
2. From a clean checkout on a machine without Node/`uv`, the launcher bootstraps
   prerequisites without admin and reaches a working wizard — or emits a clear,
   documented fallback if a step is blocked.
3. The wizard generates and downloads both files through the proxy (no CORS),
   verified with the demo depot.
4. `-Share` produces a public `https` URL a remote browser can complete the full
   flow on.
5. A second team member follows the README "Team setup" on their machine and
   reaches the wizard; any manual step is documented.
6. Existing frontend/backend test suites remain green; a unit test locks the
   relative-base proxy contract.

## Out of scope

- Cloud/PaaS hosting, always-on public deployment, custom domains, TLS certs.
- Authentication, multi-user, persistence beyond the browser session.
- CI/CD pipelines.

## Risks

- Locked-down teammate machines may block winget or user-local installs —
  mitigated by a clear fallback and the `-CheckOnly` report.
- `cloudflared` quick-tunnel URLs are ephemeral and randomly named (fine for a
  demo, not a stable address).
- Teammate machines can't be validated from the authoring environment, so
  replication proof requires a real teammate run (captured in AC 5).
