# Backend RAG Pipeline — Development Notes

## 1. Module Map

```
backend/app/
├── services/rag/
│   ├── rag.py              RAGService — ingestion orchestration (WIP)
│   └── source_item.py      SourceItemService — upload + file storage
├── rag/
│   ├── chromadb.py         VectorDatabase protocol + ChromaDB impl
│   ├── fts.py              FTSProvider protocol + SQLiteFTSProvider
│   ├── embedding.py        EmbeddingProvider protocol + FastEmbeddingAdapter
│   ├── rerank.py           RerankProvider + FastRerankAdapter
│   ├── query_expand.py     QueryExpander + ExpandedQuery schema
│   ├── text_splitter.py    TextSplitter / TokenAwareTextSplitter / ASTAwareTextSplitter
│   └── utils/
│       ├── breakpoint_scanner.py   MarkdownBreakpointScanner, ASTBreakpointScanner
│       ├── fts_tokenizer.py        FTSTokenizer (jieba-based)
│       └── tokenizer.py            EmbeddingTokenizer (token budget counting)
├── db/
│   ├── models.py           SQLAlchemy ORM models
│   └── fts.py              FTS5 DDL + triggers
├── parser/                 FileParser protocol + PDF/Markdown impls
└── storage/                FileStorage protocol + LocalFileStorage
```

---

## 2. Data Model Overview

### Key Relationships

```
Project ←→ ProjectSourceLink ←→ Source
                                  ↓ (1:N)
                              SourceItem
                                  ↓ (1:1)
                          DocumentContent  ← parser output (markdown text)
                                  ↓ (1:N)
                          DocumentChunk    ← indexed unit for RAG
```

### DocumentChunk fields

| Field | Type | Purpose |
|-------|------|---------|
| `id` | int PK | FTS rowid (via trigger) |
| `vector_id` | str unique | Bridge key to ChromaDB = `uuid5(RAG_NAMESPACE, f"{source_item_id}_{chunk_index}")` |
| `chunk_index` | int | Position ordering within source item |
| `chunk_hash` | str | Content hash for dedup / change detection |
| `chunk_content` | str | Raw text — authoritative content for RAG |
| `chunk_tokens` | str | Space-separated jieba tokens — FTS index input |
| `chunk_pos` | int | Byte offset in original document |
| `page_number` | int? | PDF page (resolved post-split via `page_boundaries`) |
| `section_header` | str? | Nearest preceding markdown heading |
| `source_item_id` | int FK | Parent source item |

### SourceItem fields

| Field | Type | Purpose |
|-------|------|---------|
| `title` | str | Display name (original filename) |
| `storage_key` | str | CAS key: `{hash[:2]}/{hash}{ext}` |
| `origin_url` | str? | Source URL for web/GitHub ingestion |
| `item_hash` | str | SHA-256 of raw file bytes |
| `status` | enum | `PENDING → PROCESSING → COMPLETED / FAILED` |

### Source fields (relevant)

| Field | Purpose |
|-------|---------|
| `collection_name` | ChromaDB collection (system-generated, `c_{uuid16}`) |
| `is_public` | `True` = visible to visitor-facing RAG queries |

---

## 3. File Storage Design

### Content-Addressable Storage (CAS)

Files are stored by content hash, not by source or filename:

```
storage/uploads/
  ab/
    abcdef1234...{ext}    ← {item_hash}{ext}, prefixed by hash[:2] for directory sharding
```

**Why CAS:**
- Same file uploaded to two different Sources only stores one physical copy.
- `SourceItem.storage_key` from both sources points to the same path.
- No cross-source symlinks or path rebasing needed.

**Deduplication on upload:**
1. Compute `item_hash = SHA256(file_bytes)`.
2. Derive `storage_key = f"{item_hash[:2]}/{item_hash}{ext}"`.
3. `FileStorage.exists(storage_key)` → skip write if already present.
4. Always create a new `SourceItem` row (even if file exists) — the item is unique per source.

**Deletion / GC:**
- On `SourceItem` delete: count remaining rows with same `storage_key`.
- Delete physical file only when count reaches 0.
- Alternative: periodic GC scan comparing `storage/uploads/` vs `SourceItem.storage_key` column.

### FileStorage Protocol

```python
class FileStorage(Protocol):
    async def save_file(self, key: str, content: bytes) -> None: ...
    async def load_file(self, key: str) -> bytes: ...
    async def delete_file(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
```

MVP impl: `LocalFileStorage` (reads/writes under `settings.storage_path`).
Future swap: S3-compatible impl, same interface.

---

## 4. Ingestion Pipeline (Full Flow)

### 4.1 Phase 1 — Upload (`SourceItemService.upload_file`)

**Endpoint:** `POST /sources/{source_uid}/items/upload`  
**Service:** `SourceItemService` (in `services/rag/source_item.py`)  
**Status:** Implemented ✅

Steps:
1. `valid_files` dependency validates file type, size, and count.
2. For each file:
   - `calculate_file_hash(content)` — SHA-256.
   - Resolve unique display filename (adds `(N)` suffix if collision within this source).
   - Derive `storage_key` from hash.
   - `file_storage.exists(key)` → save if not exists.
   - Build `SourceItemInternal` (title, storage_key, item_hash, status=PENDING).
3. Bulk insert via `SourceCRUD.add_source_items()`.
4. Return `list[SourceItemRead]`.

**Key design note:** Upload is intentionally non-blocking. It does not trigger any parsing or embedding. The returned items have `status=PENDING`.

### 4.2 Phase 2 — Ingest (`RAGService.process_document_with_progress`)

**Endpoint:** `POST /sources/{source_uid}/document/ingest`  
**Service:** `RAGService` (in `services/rag/rag.py`)  
**Status:** Skeleton exists, full implementation pending ⚠️

Accepts `{ "itemUids": [...] }` in request body. Iterates over each `SourceItem` and runs the full pipeline, streaming `ProgressEvent` via SSE.

#### Pipeline stages per SourceItem

```
PARSING   → parser.parse(file_bytes, filename)  → ParsedDocument
SPLITTING → text_splitter.split_text(text, file_path)  → list[TextChunk]
EMBEDDING → embedding.embed_documents(chunk_texts)  → list[NDArray]
INDEXING  → save to SQL (DocumentChunk) + ChromaDB
COMPLETED / FAILED
```

#### Async/thread boundaries

| Operation | Thread strategy |
|-----------|----------------|
| File read (`Path.read_bytes`) | `asyncio.to_thread()` |
| `parser.parse()` | `asyncio.to_thread()` |
| `text_splitter.split_text()` — markdown/token splitting | pure async (no CPU block) |
| `text_splitter.split_text()` — AST splitting | `await _load_grammar()` then `asyncio.to_thread(_sync_split)` |
| `fts_provider.tokenize_for_index()` (jieba) | `asyncio.to_thread()` |
| `embedding.embed_documents()` (fastembed ONNX) | `asyncio.to_thread()` |
| `reranker.rerank()` (fastembed ONNX) | `asyncio.to_thread()` |
| DB writes (SQLAlchemy async) | native async |
| ChromaDB writes | `asyncio.to_thread()` |

#### SSE Progress Design

`RAGService.process_document_with_progress()` is an **AsyncGenerator** that yields `ProgressEvent`:

```python
@dataclass
class ProgressEvent:
    stage: str     # PARSING | SPLITTING | EMBEDDING | INDEXING | COMPLETED | FAILED
    message: str
    progress: float  # 0.0 – 1.0
```

**Why AsyncGenerator, not callbacks:**
- `to_thread()` + callback requires `call_soon_threadsafe(queue.put, event)` + async queue polling — complex, race-prone.
- Each pipeline stage is naturally separated by an `await` point. Yield before and after each stage — zero cross-thread coordination needed.
- Limitation: cannot report fine-grained progress *within* a single `to_thread` call (e.g., embedding 50/100 chunks). Stage-level granularity is sufficient for MVP.

The SSE endpoint wraps this generator:

```python
@router.post("/{source_uid}/document/ingest")
async def upsert_document(...):
    async def event_stream():
        async for event in rag_service.process_document_with_progress(source_items=source_items):
            yield {"data": json.dumps({"stage": event.stage, "message": event.message, "progress": event.progress})}
    return EventSourceResponse(event_stream())
```

---

## 5. Hybrid Search Pipeline

### 5.1 Flow

```
query
  → QueryExpander.expand_query()
      .keywords              → SQLiteFTSProvider.keywords_search()  → FTSResult(chunk_id, score)
      .hypothetical_document → EmbeddingProvider.embed()
      .alternative_queries   → EmbeddingProvider.embed() (each or averaged)
  → VectorDatabase.query_collection() per source
      → VectorQueryResult(vector_id, distance)
  → resolve vector_id → DocumentChunk.id via SQL
      SELECT id FROM document_chunks WHERE vector_id IN (...)
  → RRF merge (k=60) across FTS ranks and vector ranks
  → SQL: SELECT chunk_content FROM document_chunks WHERE id IN (rrf_ids)
  → RerankProvider.rerank(query, chunks)  → final ranked list
```

### 5.2 Multi-Source Query

```python
tasks = [
    asyncio.to_thread(vector_db.query_collection, collection_name=s.collection_name, ...)
    for s in sources
]
results_per_source = await asyncio.gather(*tasks)
# flatten and merge via RRF
```

### 5.3 RRF Implementation (to be written in RAGService)

```python
def rrf_merge(
    fts_results: list[FTSResult],
    vector_results: list[tuple[str, float]],  # (vector_id, distance)
    chunk_id_from_vector_id: dict[str, int],
    k: int = 60,
) -> list[int]:  # ordered chunk_ids
    scores: dict[int, float] = {}
    for rank, r in enumerate(fts_results):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1 / (k + rank + 1)
    for rank, (vid, _) in enumerate(vector_results):
        cid = chunk_id_from_vector_id.get(vid)
        if cid:
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=lambda cid: scores[cid], reverse=True)
```

---

## 6. Text Splitter Architecture

### Classes

| Class | Role |
|-------|------|
| `TokenAwareTextSplitter` | Base: splits on token budget with overlap |
| `ASTAwareTextSplitter` | Wraps AST/Markdown breakpoint detection |
| `_ASTAwareSplittingEngine` | Async engine: loads grammar, runs `to_thread(_sync_split)` |
| `_BreakpointAwareSplittingEngine` | Splits text at detected breakpoints |

### Async Split Contract

```python
# In _ASTAwareSplittingEngine:
async def split(self, text, file_path, ...):
    await self._load_grammar(language)        # event loop: I/O / cache check
    return await asyncio.to_thread(           # thread pool: CPU work
        self._sync_split, text, ...
    )

def _sync_split(self, text, ...):
    # all CPU work, including ast_scanner.sync_scan()
    ...
```

### Known Bug: ASTBreakpointScanner

```python
# WRONG — raises AttributeError on first use:
class ASTBreakpointScanner:
    def __init__(self):
        self._grammar_cache: dict[...]   # declaration only, no assignment!

# FIX:
    def __init__(self):
        self._grammar_task_cache: dict[SupportedLanguages, asyncio.Task] = {}
        self._grammar_result_cache: dict[SupportedLanguages, Language] = {}
```

`sync_scan()` reads from `_grammar_result_cache` (populated after `await _load_grammar()`). Called only from within `to_thread`.

---

## 7. FTS Index

### Virtual Table DDL

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
USING fts5(
    chunk_tokens,
    content='document_chunks',
    content_rowid='id',
    tokenize='unicode61'
);
```

### Triggers

Auto-maintained by `AFTER INSERT / UPDATE / DELETE` triggers on `document_chunks`. See `backend/app/db/fts.py`.

### FTSProvider Interface

```python
fts_provider.tokenize_for_index(text)  → space-separated tokens (for chunk_tokens column)
fts_provider.tokenize_for_query(text)  → FTS5 MATCH expression
fts_provider.semantic_search(session, user_query)   → list[FTSResult]
fts_provider.keywords_search(session, keywords)     → list[FTSResult]
```

BM25 scoring: `bm25(documents_fts, 3.0, 1.0)` — ORDER BY ascending (SQLite BM25 is negated).

---

## 8. DocumentContent Role

`DocumentContent.document_content` stores the **parser output** (normalized markdown text), not raw file bytes.

Purpose: skip the expensive parse step during re-indexing.

Re-index path:
```
DocumentContent.document_content  → split_text() → embed() → update DocumentChunk rows
```

Full re-ingest path (if parse output is stale/corrupt):
```
SourceItem.storage_key → FileStorage.load_file() → parse() → split() → embed()
```

---

## 9. Pending Implementation Items

| Item | Location | Priority |
|------|----------|----------|
| `RAGService.process_document_with_progress()` full impl | `services/rag/rag.py` | High |
| `upsert_document` SSE endpoint body | `api/admin/endpoints/source.py` | High |
| `RAGService.hybrid_search()` with RRF | `services/rag/rag.py` | High |
| Wire `QueryExpander` into search path | `services/rag/rag.py` | High |
| `ASTBreakpointScanner` bug fix + `sync_scan()` | `rag/utils/breakpoint_scanner.py` | Medium |
| `_ASTAwareSplittingEngine._sync_split()` extract | `rag/text_splitter.py` | Medium |
| Cross-source chunk copy on hash match | `services/rag/source_item.py` | Low |
| `FileStorage` delete + GC logic | `storage/` | Low |
| `Source.is_public` filter in visitor RAG | `services/rag/rag.py` | Medium |

---

## 10. query_expand.py — ExpandedQuery Schema

```python
class ExpandedQuery(BaseModel):
    keywords: list[str]           # → FTS keywords_search
    alternative_queries: list[str]  # → embed each → vector search
    hypothetical_document: str    # HyDE → embed → vector search
```

All three are used in parallel during hybrid search. The hypothetical document (HyDE) tends to produce higher-quality embedding queries than the raw user question.
