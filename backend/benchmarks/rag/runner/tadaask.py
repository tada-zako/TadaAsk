from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence, TypeVar, cast

from pydantic import BaseModel, JsonValue

from ..models import BenchmarkDocument
from .control import ModelCallController, ModelCallLimitReached
from .schemas import (
    BenchmarkSearchMode,
    QueryExpansionConfig,
    RecallRunConfig,
    RetrievalOutcome,
    RetrievedChunk,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from app.providers.base import Message, ModelSettings
    from app.providers.factory import FullCompleter
    from app.rag import VectorDatabase
    from app.services.indexing import SourceItemIndexingService
    from app.services.search import HybridSearchService, SearchSourceRef
    from app.storage import FileStorage


BACKEND_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = BACKEND_ROOT / "data" / "benchmarks" / "rag"
ResultModel = TypeVar("ResultModel", bound=BaseModel)


class RetrievalLimitReached(RuntimeError):
    """Signal that the adapter exhausted its configured model-call budget."""


class _ControlledCompleter:
    """Route App structured completions through benchmark call controls."""

    def __init__(
        self,
        delegate: FullCompleter,
        controller: ModelCallController,
        *,
        case_id: str,
        mode: BenchmarkSearchMode,
    ) -> None:
        self._delegate = delegate
        self._controller = controller
        self._case_id = case_id
        self._mode = mode

    @property
    def model_name(self) -> str:
        return self._delegate.model_name

    @property
    def provider_name(self) -> str:
        return self._delegate.provider_name

    async def complete_structured(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        schema: type[ResultModel],
    ) -> ResultModel:
        async def invoke() -> ResultModel:
            return await self._delegate.complete_structured(
                messages=messages,
                model_settings=model_settings,
                schema=schema,
            )

        return await self._controller.execute(
            case_id=self._case_id,
            mode=self._mode,
            invoke=invoke,
        )


class TadaAskRuntime:
    """TadaAsk adapter consumed by the recall execution layer."""

    def __init__(
        self,
        *,
        workspace_dir: Path,
        mode: BenchmarkSearchMode,
        search_options: dict[str, JsonValue],
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        vector_db: VectorDatabase,
        file_storage: FileStorage,
        indexing_service: SourceItemIndexingService,
        search_service: HybridSearchService,
        completer: FullCompleter | None,
        model_calls: ModelCallController | None,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._mode = mode
        self._search_options = search_options
        self._session_factory = session_factory
        self._engine = engine
        self._vector_db = vector_db
        self._file_storage = file_storage
        self._indexing_service = indexing_service
        self._search_service = search_service
        self._completer = completer
        self._model_calls = model_calls
        self._source_ref: SearchSourceRef | None = None
        self._document_id_by_source_item_uid: dict[str, str] = {}

    @classmethod
    async def create(
        cls,
        config: RecallRunConfig,
    ) -> "TadaAskRuntime":
        """Bootstrap isolated App storage and assemble the TadaAsk RAG runtime.

        Args:
            config: Resolved benchmark configuration.

        Returns:
            Initialized runtime without a prepared corpus.
        """
        if config.rebuild_workspace and config.workspace_dir.exists():
            config.workspace_dir.relative_to(DATA_ROOT)
            if config.workspace_dir == DATA_ROOT:
                raise ValueError("benchmark workspace must be below the RAG data root")
            shutil.rmtree(config.workspace_dir)
        cls._prepare_environment(config.app_settings, config.workspace_dir)

        # App settings, SQLAlchemy and ChromaDB bind global state at import time.
        from app.core.config import settings
        from app.db import async_session, init_db, run_migrations
        from app.db.config import engine
        from app.ingestion.parser import create_default_file_parser_factory
        from app.rag import (
            QueryExpander,
            SQLiteFTSProvider,
            TokenAwareTextSplitter,
            embedding_provider_factory,
            rerank_provider_factory,
            vector_db_factory,
        )
        from app.rag.utils.fts_tokenizer import JiebaFTSTokenizer
        from app.services.indexing import SourceItemIndexingService
        from app.services.search import HybridSearchService
        from app.storage import file_storage_factory
        from app.utils import embedding_tokenizer_factory

        config.workspace_dir.mkdir(parents=True, exist_ok=True)
        config.run_dir.mkdir(parents=True, exist_ok=True)
        await run_migrations()
        await init_db()

        vector_db = vector_db_factory(settings.vector_store_perf)
        file_storage = file_storage_factory(
            settings.file_storage_backend,
            base_path=settings.upload_folder_path,
        )
        embedding_tokenizer = embedding_tokenizer_factory(
            embedding_mode=settings.embedding_backend,
            model_name=settings.embedding_model_name,
            cache_dir=settings.hf_hub_cache_dir,
        )
        text_splitter = TokenAwareTextSplitter(
            tokenizer=embedding_tokenizer,
            chunk_tokens=settings.chunk_size_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            window_tokens=settings.chunk_window_tokens,
            splitter_strategy="ast",
        )
        fts_provider = SQLiteFTSProvider(
            tokenizer=JiebaFTSTokenizer(
                cut_all=False,
                use_hmm=True,
                stop_words_file=None,
                jieba_stop_words_path=None,
                jieba_idf_path=None,
            )
        )
        embedding = embedding_provider_factory(settings)
        rerank = rerank_provider_factory(settings)
        indexing_service = SourceItemIndexingService(
            session_factory=async_session,
            file_storage=file_storage,
            file_parser_factory=create_default_file_parser_factory(),
            vector_db=vector_db,
            text_splitter=text_splitter,
            embedding=embedding,
            fts_provider=fts_provider,
        )
        search_service = HybridSearchService(
            session_factory=async_session,
            vector_db=vector_db,
            query_expander=QueryExpander(),
            embedding=embedding,
            fts_provider=fts_provider,
            rerank_provider=rerank,
        )
        if config.mode == BenchmarkSearchMode.FAST:
            model_calls = None
            completer = None
        else:
            model_calls = ModelCallController(
                ledger_path=config.run_dir / "model-calls.jsonl",
                requests_per_minute=config.requests_per_minute,
                max_calls_total=config.max_model_calls_total,
                max_attempts=config.max_attempts,
                retry_base_seconds=config.retry_base_seconds,
            )
            completer = cls._create_completer(
                cast(QueryExpansionConfig, config.query_expansion)
            )
        return cls(
            workspace_dir=config.workspace_dir,
            mode=config.mode,
            search_options=config.search_options,
            session_factory=async_session,
            engine=engine,
            vector_db=vector_db,
            file_storage=file_storage,
            indexing_service=indexing_service,
            search_service=search_service,
            completer=completer,
            model_calls=model_calls,
        )

    @property
    def model_call_attempts(self) -> int:
        """Return persisted model attempts for the current run directory."""
        return self._model_calls.total_attempts if self._model_calls is not None else 0

    @staticmethod
    def _prepare_environment(
        app_settings: dict[str, JsonValue], workspace_dir: Path
    ) -> None:
        """Bind import-time App settings to benchmark-owned storage."""
        for name, value in app_settings.items():
            if isinstance(value, bool):
                environment_value = str(value).lower()
            elif isinstance(value, (dict, list)):
                environment_value = json.dumps(value)
            else:
                environment_value = str(value)
            os.environ[name.upper()] = environment_value

        os.environ["SQLITE_DATABASE_PATH"] = str(
            workspace_dir / "database" / "sqlite.db"
        )
        os.environ["UPLOAD_FOLDER_PATH"] = str(workspace_dir / "storage")
        os.environ["CHROMADB_PATH"] = str(workspace_dir / "vector")

    @staticmethod
    def _create_completer(config: QueryExpansionConfig) -> FullCompleter:
        """Create an App FullCompleter from operator-managed model settings."""
        from app.db.schemas import ModelProfileRead, ProviderWithModelInternalRead
        from app.providers.factory import completer_factory

        now = datetime.now(UTC)
        provider_with_model = ProviderWithModelInternalRead(
            uid="rag-benchmark-provider",
            name=config.provider,
            base_url=config.base_url,
            api_key=config.api_key,
            created_at=now,
            updated_at=now,
            model_profile=ModelProfileRead(
                uid="rag-benchmark-query-expansion-model",
                model=config.model,
                created_at=now,
                updated_at=now,
            ),
        )
        return completer_factory(provider_with_model)

    async def prepare_corpus(
        self,
        *,
        bundle_dir: Path,
        documents: Sequence[BenchmarkDocument],
    ) -> None:
        """Reuse a prepared App index or materialize the controlled corpus."""
        from app.services.search import SearchSourceRef

        index_path = self._workspace_dir / "index.json"
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
        else:
            index = await self._materialize_index(
                bundle_dir=bundle_dir,
                documents=documents,
            )

        self._document_id_by_source_item_uid = {
            str(item["uid"]): document_id
            for document_id, item in index["documents"].items()
        }
        self._source_ref = SearchSourceRef(
            id=index["source"]["id"],
            uid=index["source"]["uid"],
            collection_name=index["source"]["collection_name"],
            source_item_ids=[item["id"] for item in index["documents"].values()],
        )

    async def _materialize_index(
        self,
        *,
        bundle_dir: Path,
        documents: Sequence[BenchmarkDocument],
    ) -> dict[str, Any]:
        """Create Source/SourceItems through App services and index the corpus."""
        from fastapi import UploadFile

        from app.core.constants import SourceType
        from app.crud import SourceCRUD
        from app.db.schemas import SourceBase
        from app.services.sources import SourceItemUploadService, SourceService

        async with self._session_factory() as session:
            async with session.begin():
                source_crud = SourceCRUD(session)
                source = await SourceService(
                    source_crud=source_crud,
                    vector_db=self._vector_db,
                    file_storage=self._file_storage,
                ).create_source(
                    SourceBase(
                        source_name="TadaAsk RAG benchmark",
                        source_type=SourceType.LOCAL_FILE,
                    )
                )
                upload_service = SourceItemUploadService(
                    source_crud=source_crud,
                    file_storage=self._file_storage,
                )

                item_by_document: dict[str, dict[str, int | str]] = {}
                for document in documents:
                    document_path = bundle_dir / document.relative_path
                    filename = f"{document.id}{document_path.suffix.lower()}"
                    with document_path.open("rb") as handle:
                        uploaded = await upload_service.upload_file(
                            validated_files=[UploadFile(handle, filename=filename)],
                            source=source,
                        )
                    source_item = await source_crud.get_source_item_by_uid(
                        uploaded[0].uid
                    )
                    if source_item is None:
                        raise RuntimeError(
                            f"uploaded source item is missing: {document.id}"
                        )
                    item_by_document[document.id] = {
                        "id": source_item.id,
                        "uid": source_item.uid,
                    }

                source_ref = {
                    "id": source.id,
                    "uid": source.uid,
                    "collection_name": source.collection_name,
                }

        final_counters = None
        async for event in self._indexing_service.ingest_source_items(
            source_uid=str(source_ref["uid"]),
            source_item_uids=[str(item["uid"]) for item in item_by_document.values()],
        ):
            if event.counters is not None:
                final_counters = event.counters
        if final_counters is None or final_counters.failed:
            failed = (
                final_counters.failed if final_counters is not None else len(documents)
            )
            raise RuntimeError(
                f"benchmark document indexing failed: {failed} document(s); "
                "rebuild the workspace before retrying"
            )

        index = {"source": source_ref, "documents": item_by_document}
        (self._workspace_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return index

    async def retrieve(
        self,
        *,
        case_id: str,
        query: str,
    ) -> RetrievalOutcome:
        """Run App Hybrid Search and map results to the benchmark protocol."""
        if self._source_ref is None:
            raise RuntimeError("benchmark corpus has not been prepared")

        from app.core.constants import SearchMode
        from app.db.schemas import HybridSearchOptions

        attempts_before = self.model_call_attempts
        completer = (
            _ControlledCompleter(
                self._completer,
                self._model_calls,
                case_id=case_id,
                mode=self._mode,
            )
            if self._completer is not None and self._model_calls is not None
            else None
        )
        try:
            results = await self._search_service.search(
                query=query,
                sources=[self._source_ref],
                options=HybridSearchOptions(
                    **self._search_options,
                    mode=SearchMode(self._mode.value),
                ),
                # The App Fast branch never dereferences its completer argument.
                completer=completer,
            )
        except ModelCallLimitReached as exc:
            raise RetrievalLimitReached from exc

        chunks = [
            RetrievedChunk(
                rank=rank,
                document_id=self._document_id_by_source_item_uid.get(
                    result.source_item_uid
                ),
                chunk_id=result.chunk_id,
                content=result.content,
                rrf_score=result.rrf_score,
                rerank_score=result.rerank_score,
            )
            for rank, result in enumerate(results, start=1)
        ]
        return RetrievalOutcome(
            chunks=chunks,
            model_call_attempts=self.model_call_attempts - attempts_before,
        )

    async def close(self) -> None:
        """Dispose the isolated App database engine."""
        await self._engine.dispose()
