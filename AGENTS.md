# TadaAsk Agent Instructions

Applies to all AI agents working in this repository.

This file is a lightweight implementation guide for agents. It is not a full
business specification, architecture document, API contract, or frontend design
standard.

---

## Project Context

TadaAsk is an open-source AI knowledge-base assistant with a widget-first
integration model.

Current stack:

- Backend: FastAPI, SQLAlchemy async, SQLite.
- Frontend: Vue 3, TypeScript.

This is a personal learning and MVP-stage project. Prefer clarity, fast
iteration, and easy refactoring over heavy process or premature abstraction.

The project name is **TadaAsk**. Do not introduce or restore old project names.

---

## Source Of Truth

- Source code is the primary source of truth.
- Backend API behavior should be checked against the FastAPI implementation and
  the runtime `/openapi.json` or `/docs` output.
- Lightweight backend integration notes live under `backend/docs/`.
- `backend/docs/tutorial/source-map.md` is the preferred backend file-location
  guide for frontend/backend integration work.

Do not treat older design notes, generated specs, or large documentation files as
binding if they disagree with the current implementation.

This project does not use strict SDD. Do not create large specification sets
unless the user explicitly asks for them.

---

## Working Principles

- Read the relevant existing code before making changes.
- Keep changes scoped to the user's request.
- Do not perform broad refactors, rewrites, renames, formatting sweeps, or
  documentation expansions unless they are directly requested.
- Preserve existing patterns unless there is a clear reason to change them.
- If a business boundary is unclear, discuss it with the user before encoding it
  into code or documentation.
- When implementation and documentation disagree, prefer implementation and note
  the mismatch if it matters.
- Avoid adding types, error handling, abstractions, files, or
  dependencies that are not needed for the current change.

---

## Backend Boundaries

Use the current backend layering as a working habit, not as a frozen architecture
spec:

```text
Router -> Service -> CRUD / Provider / Search / Indexing / Storage
```

- Keep HTTP handlers thin.
- Put business orchestration in service modules.
- Keep persistence details in CRUD/database-facing modules.
- Keep LLM/provider-specific SDK usage behind provider abstractions.
- Keep search, indexing, and storage details inside their existing modules.
- Use centralized settings/configuration. Do not hardcode secrets, local paths,
  provider names, or model names in feature code.

Before changing RAG behavior, read the relevant source under:

- `backend/app/services/search/`
- `backend/app/services/indexing/`
- `backend/app/services/sources/`
- `backend/app/db/`

Do not restate detailed RAG, Source/SourceItem, citation, vector-store, FTS, or
CAS behavior in this file. Those are current implementation details and should be
verified from source code when needed.

---

## Async And I/O

- Prefer async-first code for database, file, network, LLM, crawl, and indexing
  flows.
- Keep sync/async bridging close to the component that owns the blocking or
  CPU-heavy work.
- Do not add a task queue or background worker system for MVP work unless the
  user explicitly asks for that direction.
- Use existing concurrency patterns in the touched module instead of inventing a
  new local style.

---

## Code Style

Follow Occam's Razor: the simplest sufficient solution is preferred.

- For vibe coding and generated code, always add appropriate, concise code
  comments where they help future readers. Prefer Chinese comments, while
  allowing English when it fits surrounding code, APIs, or domain terms better.

For Python backend code:

- Prefer Pythonic, readable code over clever abstractions.
- Use clear names, small functions, and direct control flow.
- Avoid unnecessary base classes, managers, factories, registries, wrappers, and
  configuration layers.
- Reuse existing schemas, helpers, services, and provider interfaces before
  introducing new entities.
- Add abstraction only when it removes real duplication or protects an existing
  boundary.

For frontend code:

- Use Vue 3 and TypeScript conventions already present in the project.
- Non-essential entities should not be added: avoid unnecessary components,
  stores, composables, types, wrappers, and configuration files.
- Avoid premature abstraction in MVP work. Keep code direct at first; split files,
  helpers, or layers only after code becomes heavy, duplicated, or has a clear
  boundary.
- Write comments mainly in Chinese. Prefer comments that explain intent,
  tradeoffs, protocol boundaries, or non-obvious behavior; avoid restating
  obvious code.
- Keep admin-console and visitor-widget code able to evolve independently.
- Prefer explicit client-server contracts based on OpenAPI and backend source
  over duplicated handwritten protocol documents.

---

## Documentation Policy

Documentation should help navigation and integration, not slow MVP development.

- Keep backend docs lightweight.
- Prefer entry documents, source maps, and runtime OpenAPI over large manual
  specs.
- Do not create or expand business-contract documents unless requested.
- When adding documentation, make it clear whether it is current behavior,
  implementation guidance, or future design thinking.
- Avoid strict promises about APIs, SSE events, citation rendering, storage, or
  RAG internals unless they are enforced by current code.

---

## Testing And Validation

- `backend/tests` contains the maintained core backend regression suite.
- The suite covers the most important unit and integration paths for security,
  Source/indexing, retrieval, chat, jobs, database behavior, and representative
  APIs/provider contracts.
- This project is not TDD, and the tests are not a complete business
  specification. Confirm changing or unclear behavior against the current source
  code and runtime OpenAPI.
- For backend code changes, run the relevant focused tests first, then run the
  default backend suite when the change can affect shared behavior.
- Tests marked `live` require an explicit `--run-live` opt-in and may require
  network access, credentials, or incur provider costs. Do not run them by
  default.
- Prefer validation proportional to the change: tests plus syntax checks, type
  checks, focused smoke checks, or direct inspection as appropriate.
- For documentation-only changes, tests are usually unnecessary.

---

## Change Discipline

- Respect the user's existing worktree changes. Do not revert files you did not
  intentionally change.
- Do not introduce large dependency changes without discussion.
- Do not change project identity, naming, or product language unless requested.
- If a change would turn a lightweight MVP decision into a long-term contract,
  ask the user first.
