# GitHub Copilot Instructions — TadaAsk

All architectural rules, layer boundaries, async patterns, RAG constraints, and roadmap alignment
are defined in [`AGENTS.md`](../AGENTS.md). Read that file first for full project context.

The sections below are Copilot-specific supplements.

---

## Code Generation Defaults

- Default to async functions for any new I/O-bound code (DB, file, network).
- When generating new service methods that wrap sync CPU work, apply `asyncio.to_thread()` at the
  call site inside the service — not in the router or the leaf module caller.
- Never emit `import` statements for vendor LLM SDKs (e.g. `google.generativeai`, `openai`) in
  service or router files; use the existing `Model` / `EmbeddingProvider` / `RerankProvider`
  Protocol abstractions instead.
- Prefer `Mapped[T]` column declarations (SQLAlchemy 2.x style) over `Column(T)` for any new ORM
  model fields.

## Suggestion Scope

- Only suggest changes that are **directly requested** or **clearly necessary** for the task.
- Do not add docstrings, comments, or type annotations to code that was not part of the change.
- Do not introduce new dependencies without noting the addition explicitly.

## Key File References

| Purpose | Path |
|---------|------|
| Backend API contract | Runtime `/openapi.json` or `/docs` |
| Backend source map | `backend/docs/tutorial/source-map.md` |
| Backend documentation entry | `backend/docs/README.md` |
| ORM models | `backend/app/db/models.py` |
| Search and retrieval services | `backend/app/services/search/` |
| Source and upload services | `backend/app/services/sources/` |
| Indexing services | `backend/app/services/indexing/` |
| Admin endpoints — source | `backend/app/api/admin/endpoints/source.py` |
| Visitor Widget endpoints | `backend/app/api/visitor/endpoints/chat.py` |
