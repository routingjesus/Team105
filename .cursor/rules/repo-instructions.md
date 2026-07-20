# Repo Instructions

Baseline rules for agent-first development in Team105.

## Project overview

- **Name:** Team105
- **Description:** Team105 product application — description to be refined after initial prototyping.
- **Primary language:** Python (backend/services) and TypeScript (frontend)
- **Framework:** Next.js (frontend); Python backend framework to be decided — revisit after prototyping (FastAPI and Django are common pairings with Next.js)
- **Package manager:** `uv` or `pip` (Python); `pnpm` preferred for Node, `npm` acceptable

## Coding conventions

### Style and formatting

- Follow the existing code style in the repo — consistency over personal preference.
- Use the project's configured formatter (Prettier for TypeScript/JSON, Ruff or Black for Python) before committing.
- Prefer explicit over clever. Code should be readable without comments explaining what it does.

### Naming

- **TypeScript/JavaScript:** `camelCase` for variables and functions; `PascalCase` for components, types, and classes; `kebab-case` for file and directory names in the Next.js app.
- **Python:** `snake_case` for functions, variables, and modules; `PascalCase` for classes.

### Error handling

- Never swallow errors silently.
- **TypeScript:** use typed errors and propagate meaningful messages; handle async failures with `try/catch` or `.catch()` at API boundaries.
- **Python:** raise typed exceptions with context; return structured error responses from API handlers rather than bare status codes.

## File organization

- **Frontend:** Next.js App Router layout under `app/` (or `src/app/` if using a `src/` root); shared UI in `components/`, hooks in `hooks/`, utilities in `lib/` or `utils/`.
- **Backend:** Python service code under `api/` or `backend/` mirroring domain modules (routes, services, models).
- **Specs:** Creator specs live under `.spec/`; do not mix spec artifacts into application source trees.
- Keep files focused — one module, class, or component per file unless there is a strong reason to co-locate.
- **Tests:** TypeScript tests as `*.test.ts` / `*.test.tsx` next to source or under `__tests__/`; Python tests in a parallel `tests/` directory mirroring package structure.

## Commit message format

Use these defaults for Creator-managed commits:

```
Spec-driven work:
<type>(SPEC-<n>): <short summary>

Non-spec workflows:
<type>: <short summary>

<optional body explaining why, not what>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

These six types are a **closed set** for this project.

#### Squash-merge commits

When a PR is squash-merged, the resulting commit on the default branch follows the **PR title format** (`SPEC-<n>: <short title>`), not the per-commit format.

Use the current or source spec ID as the scope for spec-driven work. Do not invent placeholder or fake `SPEC-*` scopes when no active or source spec exists.

Examples:
- `feat(SPEC-001): add user dashboard`
- `fix(SPEC-002): correct API validation on signup`
- `chore: scaffold Creator process files`

## PR title format

```
Single-spec PRs:
SPEC-<n>: <short title from the spec>

Non-spec or multi-spec PRs:
<descriptive title without a SPEC-* prefix>
```

Examples:
- `SPEC-001: Add user dashboard`
- `Scaffold Creator process files` (non-spec)

## Test expectations

- Every new feature or bug fix should include tests.
- **Frontend:** unit and integration tests with Vitest or Jest; component tests with React Testing Library.
- **Backend:** unit tests with `pytest`.
- Tests should be independent and not rely on execution order.
- Use descriptive test names that explain the scenario and expected outcome.
- **Coverage:** no enforced threshold yet — add a CI gate once the test suite is established.

## Dependencies

- Prefer well-maintained, widely-used libraries over custom solutions.
- Pin dependency versions for reproducibility (`package-lock.json` / `pnpm-lock.yaml` for Node; lockfile or pinned versions for Python).
- Security review required before adding new production dependencies with network, auth, or data-handling scope.
- Prefer standard library or framework builtins when they are sufficient.

## Agent-specific guidance

- Always read existing code before writing new code. Check for established patterns before introducing new ones.
- Do not refactor code outside the scope of the current spec.
- When a spec lists "files NOT to modify", respect that boundary strictly.
- Prefer small, focused commits over large monolithic changes.
