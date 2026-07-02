# Backend Source Map

本文件用于快速定位后端业务实现。它不是严格接口规范；接口形状以 `openapi.json` 和 FastAPI `/docs` 为准，业务细节以源代码为准。

## API Router

- Admin router 汇总：[app/api/admin/router.py](../../app/api/admin/router.py)
- Visitor router 汇总：[app/api/visitor/router.py](../../app/api/visitor/router.py)
- Admin auth：[app/api/admin/endpoints/auth.py](../../app/api/admin/endpoints/auth.py)
- Project / Widget / Project Settings / Project-Source 绑定：[app/api/admin/endpoints/project.py](../../app/api/admin/endpoints/project.py)
- Source / SourceItem / upload / RAG job start/query/events / pause / resume：[app/api/admin/endpoints/source.py](../../app/api/admin/endpoints/source.py)
- Provider / Model Profile：[app/api/admin/endpoints/model_profile.py](../../app/api/admin/endpoints/model_profile.py)
- Admin chat stream / revert / cancel / citation reserved endpoint：[app/api/admin/endpoints/chat.py](../../app/api/admin/endpoints/chat.py)
- Admin session / message timeline：[app/api/admin/endpoints/session.py](../../app/api/admin/endpoints/session.py)
- Visitor widget chat / cancel：[app/api/visitor/endpoints/chat.py](../../app/api/visitor/endpoints/chat.py)
- Widget scoped CORS：[app/api/visitor/widget_cors.py](../../app/api/visitor/widget_cors.py)

## Schema And Constants

- API request/response helpers, RAG job schemas, SSE sync event, delete/cancel responses：[app/api/schemas.py](../../app/api/schemas.py)
- DB-facing Pydantic schemas, Project/Source/Chat/RAGSnapshot：[app/db/schemas.py](../../app/db/schemas.py)
- ORM models：[app/db/models.py](../../app/db/models.py)
- enums and file type constants：[app/core/constants.py](../../app/core/constants.py)
- settings：[app/core/config.py](../../app/core/config.py)
- domain exceptions：[app/core/exceptions.py](../../app/core/exceptions.py)

## Source And Ingestion

- Source create/update/delete and config normalization：[app/services/sources/source.py](../../app/services/sources/source.py)
- Local file upload to SourceItem：[app/services/sources/file_upload.py](../../app/services/sources/file_upload.py)
- SourceItem delete and vector/file cleanup：[app/services/sources/source_item.py](../../app/services/sources/source_item.py)
- Web crawl materialization：[app/services/sources/web_crawl.py](../../app/services/sources/web_crawl.py)
- RAG background job manager and event replay cache：[app/services/jobs/rag_job_manager.py](../../app/services/jobs/rag_job_manager.py)
- SourceItem indexing orchestration：[app/services/indexing/source_item_indexing.py](../../app/services/indexing/source_item_indexing.py)
- Chunk SQL/vector index writer：[app/services/indexing/chunk_index_writer.py](../../app/services/indexing/chunk_index_writer.py)
- File parser factory and parser implementations：[app/ingestion/parser/](../../app/ingestion/parser/)
- Web crawler and HTML parser：[app/ingestion/crawler/](../../app/ingestion/crawler/)

## Search, RAG, And Citation

- Hybrid search service：[app/services/search/hybrid_search.py](../../app/services/search/hybrid_search.py)
- Chat retrieval and RAGSnapshot construction：[app/services/search/retrieval.py](../../app/services/search/retrieval.py)
- Vector database adapter：[app/rag/chromadb.py](../../app/rag/chromadb.py)
- FTS provider：[app/rag/fts.py](../../app/rag/fts.py)
- Embedding provider：[app/rag/embedding.py](../../app/rag/embedding.py)
- Query expansion：[app/rag/query_expand.py](../../app/rag/query_expand.py)
- Rerank provider：[app/rag/rerank.py](../../app/rag/rerank.py)
- Text splitter：[app/rag/text_splitter.py](../../app/rag/text_splitter.py)

Citation display data is currently stored in `ChatMessage.rag_snapshot` as `RAGSnapshot.items`. The reserved lazy-loading citation endpoint exists in the Admin chat router but currently returns `501`.

## Chat And Session

- Chat stream event schemas：[app/services/schemas.py](../../app/services/schemas.py)
- Chat orchestration：[app/services/chat/chat_orchestrator.py](../../app/services/chat/chat_orchestrator.py)
- Session operations such as revert/cancel scope：[app/services/chat/session_operations.py](../../app/services/chat/session_operations.py)
- Context builder：[app/services/chat/context_builder.py](../../app/services/chat/context_builder.py)
- Compaction service：[app/services/chat/compaction_service.py](../../app/services/chat/compaction_service.py)
- Active generation registry：[app/services/chat/generation_registry.py](../../app/services/chat/generation_registry.py)

Chat SSE events are defined in `app/services/schemas.py`. Source crawl/index/resume jobs are started from the Source router, tracked by `RAGJobManager`, and observed through `RAGSyncEvent` events defined in `app/api/schemas.py`.

## CRUD Layer

- Project CRUD：[app/crud/project.py](../../app/crud/project.py)
- Source CRUD：[app/crud/source.py](../../app/crud/source.py)
- RAG search CRUD：[app/crud/rag_search.py](../../app/crud/rag_search.py)
- Model profile CRUD：[app/crud/model_profile.py](../../app/crud/model_profile.py)
- Chat session CRUD：[app/crud/chat_session.py](../../app/crud/chat_session.py)
- Chat message CRUD：[app/crud/chat_message.py](../../app/crud/chat_message.py)
- Admin CRUD：[app/crud/admin.py](../../app/crud/admin.py)

## Runtime Wiring

- FastAPI app, lifespan setup, middleware, exception handlers：[app/main.py](../../app/main.py)
- Dependency injection wiring：[app/api/deps.py](../../app/api/deps.py)
- Visitor rate limiter：[app/core/rate_limit.py](../../app/core/rate_limit.py)
- Security and API key encryption：[app/core/security.py](../../app/core/security.py)
- Storage protocol and local implementation：[app/storage/](../../app/storage/)
