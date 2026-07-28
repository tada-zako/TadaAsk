# TadaAsk Agent Instructions

These instructions apply to all agents working in this repository.

## Project Overview

TadaAsk is an open-source AI knowledge-base assistant with a widget-first integration model.

- Backend: Python, FastAPI, async SQLAlchemy, and SQLite.
- Frontend: Vue 3, TypeScript, Vite, and Pinia.

The project name is **TadaAsk**. Do not introduce or restore old project names.

## Setup, Build, and Test Commands

Use Python 3.13 and uv for the backend:

```bash
cd backend
uv sync --group dev
uv run uvicorn app.main:app --reload
uv run ruff check app tests
uv run pytest -m "not live"
uv run pytest -m "not live" --cov=app --cov-report=term-missing
```

After changing Python, format only the files touched by the task:

```bash
uv run ruff format path/to/changed_file.py
```

Run `uv run pytest --run-live -m live` only when explicitly requested; live tests may use network access, credentials, or paid providers.

Use Node.js 24 and pnpm 11 for the frontend:

```bash
cd frontend
pnpm install
pnpm dev
pnpm dev:widget
pnpm test:run
pnpm test:coverage
pnpm typecheck
pnpm build
```

Start the complete Docker deployment from the repository root:

```bash
docker compose up -d --build
```

- Run focused tests first, then the default suite when shared behavior may be affected. Tests are regression protection, not a complete specification.
- Default frontend tests must not use real backends, credentials, providers, or public-network access.
- Frontend tests should verify observable behavior without freezing unstable page structure, styling, CSS classes, or private implementation details.
- Documentation-only changes usually do not require the full test suites.

## Code Style Guidelines

### Basic Rules

1. Read the relevant implementation before editing. Preserve existing patterns unless the requested change requires otherwise.
2. After changing Python, run Ruff formatting on the changed files and `uv run ruff check app tests`. Do not mix unrelated repository-wide formatting into a feature or fix.
3. Frontend formatting is not mandatory. Preserve surrounding style and do not run a broad formatting sweep unless explicitly requested.
4. Use English for internal log messages. Keep logs concise, actionable, and free of secrets.
5. Comments should explain **everything the code cannot express directly**: non-obvious behavior, protocols, concurrency, state transitions, constraints, and design tradeoffs. Comments may use Chinese or English.
6. Add internal flow comments to long business logic, especially top-level services. Use short section comments for major stages, branches, nested loops, async coordination, cleanup, and important recovery paths. Prefer sufficient comments over under-documenting complex code.
7. Do not translate obvious assignments, calls, or function names into comments. Keep comments synchronized with the implementation.
8. When a Python docstring is needed, use Google style with `Args:`, `Returns:`, and `Raises:` as applicable. Avoid boilerplate docstrings on trivial code.
9. Keep HTTP handlers thin, orchestration in services, persistence in database-facing code, and provider SDK usage behind provider abstractions. Keep Console and Widget able to evolve independently.
10. Prefer async-first database, file, network, provider, and indexing code. Keep sync/async bridging next to the component that owns the blocking work.

### KISS, YAGNI, and Occam's Razor

Follow the KISS and YAGNI principle during development. Implement the smallest correct change with direct, readable control flow. Do not add features, switches, compatibility layers, dependencies, types, error handling, or abstractions unless they directly solve the current problem and have clear evidence of need. Reuse existing entities before creating base classes, managers, factories, registries, or wrappers.

### Inline-First and Helpers

1. **Inline first:** Keep a logic block in the main function when it fits without harming readability.
2. **Strict justification:** Extract a helper when substantially identical logic appears in at least three places, or when inlining makes the function clearly too long—roughly over 50 lines—or obscures its main flow.
3. **Boundary exception:** A one-use helper may protect a clear protocol, security, transaction, resource-lifecycle, complex pure-computation, or framework callback boundary.
4. **No fragmentation:** Do not split linear logic, one-time mapping, simple validation, or a single API call into tiny helpers. Do not restructure existing functions only for stylistic preference.

## Security Considerations

- Never hardcode, commit, log, or expose passwords, tokens, API keys, encryption keys, or populated environment files.
- Use centralized settings and environment variables for secrets, paths, providers, models, and deployment-specific values.
- Preserve authentication, authorization, encryption, CORS, Origin, upload, and safe-redirect boundaries; run focused tests when changing them.
- Default tests must use fake providers and isolated data. External or paid calls require explicit opt-in.
- Do not deploy, migrate production data, modify production credentials, or perform destructive storage operations unless explicitly requested.

## Git, PR, and Other Guidance

1. Keep changes scoped to the request. Avoid unrelated refactors, renames, dependency updates, generated reports, or documentation expansion.
2. Respect existing worktree changes. Never revert files you did not intentionally modify.
3. Source code, runtime behavior, and current OpenAPI are the source of truth. Follow the implementation when older documentation disagrees and report relevant mismatches.
4. Do not create large specification or summary document sets unless requested.
5. Commit only when explicitly asked. Use Conventional Commits with an English type and optional scope, and prefer Chinese for the subject and body: `fix(backend): <Chinese summary>`.
6. Prefer `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, and `ci`.
7. PR and handoff descriptions should state the goal, important behavior or risks, and validation performed.
