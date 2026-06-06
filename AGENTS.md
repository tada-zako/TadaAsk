# OpenKapa — Agent Instructions

Applies to all AI agents (GitHub Copilot, Claude, Cursor, etc.).
Full requirements document: `docs/requirements.md`. RAG implementation details: `backend/docs/rag-pipeline.md`.

---

## Project Identity

Open-source AI knowledge-base assistant with a widget-first integration model (reference: kapa.ai).
Tech stack: FastAPI + SQLAlchemy async + SQLite backend; Vue 3 + TypeScript frontend.
Personal learning project — no commercial scale constraints; prioritize architectural clarity over premature optimization.

---

## Backend Layer Boundaries

```
Router (HTTP, thin)  →  Service (orchestration)  →  Provider / RAG / CRUD (leaf modules)
```

- Handlers stay thin — all business logic belongs in the service layer.
- Layer rule: `router → service → (crud | rag | provider | storage)`. No cross-layer shortcuts.
- LLM/Provider abstractions must stay behind the `Model` Protocol; service and router layers must not import vendor SDKs directly.
- Vector-store logic stays behind `VectorDatabase` Protocol; FTS logic stays behind `FTSProvider` Protocol.
- All configuration via centralized `settings` (pydantic-settings). No hardcoded secrets, paths, or model names.

---

## Async Patterns

- Prefer async-first for all I/O-heavy flows (DB, file, network).
- CPU-intensive sync operations (parse, embed, tokenize, AST scan) must run inside `asyncio.to_thread()`.
- **Encapsulation rule**: the component that knows it is CPU-intensive is responsible for wrapping itself in `to_thread` — not the caller.
- Use `asyncio.gather()` for concurrent multi-collection vector queries.
- No Celery / task queue for MVP. `asyncio.to_thread()` is the sole async-sync bridge.
- jieba tokenization does **not** release the GIL → must be wrapped in `asyncio.to_thread()`.
- fastembed (ONNX) **does** release the GIL → safe inside `asyncio.to_thread()`.

---

## RAG Architecture Constraints

- SQL (`DocumentChunk.chunk_content`) is the **authoritative content store**. ChromaDB stores vectors only (`{source_item_id}` metadata).
- `vector_id = uuid5(RAG_NAMESPACE, f"{source_item_id}_{chunk_index}")` — globally unique bridge key between SQL and ChromaDB.
- FTS5 virtual table `documents_fts` is bound to `document_chunks.chunk_tokens` (chunk-level granularity).
- One `Source` = one ChromaDB collection. Multi-source queries use `asyncio.gather()` + SQL-layer RRF merge.
- Hybrid search order: `QueryExpander` → parallel FTS + vector search → RRF fusion (k=60) → `RerankProvider`.
- `DocumentContent.document_content` stores **parser output (Markdown text)** — used to skip re-parsing during re-indexing.

---

## File Storage

- **Content-addressable storage (CAS)**: `storage_key = f"{hash[:2]}/{hash}{ext}"` — path is derived from content hash, independent of which Source the file belongs to.
- `FileStorage` is a Protocol (MVP impl: `LocalFileStorage`; future swap: S3-compatible impl).
- `SourceItem.storage_key` holds the CAS key. Cross-source deduplication: same physical file on disk, but each Source has its own `SourceItem` + `DocumentChunk` rows.

---

## Ingestion API Pattern

- **Upload** (`POST /items/upload`) and **process** (`POST /document/ingest`) are **two separate endpoints**.
- Upload: stores the file, creates `SourceItem` (`status=PENDING`), returns immediately.
- Process: SSE-streamed via `AsyncGenerator` yielding `ProgressEvent` (stage, message, progress), served with sse-starlette's `EventSourceResponse`.
- Never combine upload and processing logic in a single blocking HTTP request.

---

## Frontend Rules (Vue)

- Use Vue 3 + TypeScript; keep framework choices consistent within each feature area.
- Keep UI modules reusable so the widget and admin console can evolve independently.
- Keep client-server contracts explicit and consistent with backend payload conventions.
- Frontend directory structure is expected to change for widget/admin adaptation; avoid coupling to fixed layouts.

---

## Roadmap Alignment

- Favor protocol-oriented abstractions supporting multiple LLMs (Gemini/OpenAI-compatible/Ollama) and vector DBs (Chroma → Qdrant/LanceDB).
- Prefer additive changes that make crawler ingestion, GitHub repo ingestion, and owner-side MCP operations easier to add later.
- SQLite is the metadata/config baseline. `Source.is_public` controls visitor-facing RAG access.
- For MVP, prioritize grounded answers from known knowledge sources over broad web search.

---

## Quality Expectations

- Keep boundaries explicit: `router → service → provider/rag/core`.
- Avoid shortcut coupling that bypasses existing layers; document the reason if it is truly necessary.
- For architecture-impacting changes, include a brief note on extensibility impact.
- Only make changes that are directly requested or clearly necessary; do not add comments, type annotations, or error handling to code that was not part of the change.
