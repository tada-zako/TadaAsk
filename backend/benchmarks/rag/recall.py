import json
import os
import sys
import shutil
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from loguru import logger

from .bundle import load_jsonl
from .models import BenchmarkCase, BenchmarkDocument, QuestionType

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.core.constants import SearchMode
    from app.db.schemas import HybridSearchResult
    from app.providers.base import StructuredCompleter
    from app.rag import VectorDatabase
    from app.services.indexing import SourceItemIndexingService
    from app.services.search import HybridSearchService, SearchSourceRef
    from app.storage import FileStorage


PACKAGE_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PACKAGE_ROOT.parents[1]
DATA_ROOT = BACKEND_ROOT / "data" / "benchmarks" / "rag"
RECALL_K = (1, 3, 5)


@dataclass(frozen=True)
class RecallConfig:
    """Resolved configuration for one retrieval recall run."""

    bundle_dir: Path
    workspace_dir: Path
    run_dir: Path
    modes: tuple[str, ...]
    rebuild_workspace: bool
    resume: bool
    app_settings: dict[str, Any]
    search_options: dict[str, Any]
    query_expansion: dict[str, str]


def load_recall_config(path: Path) -> RecallConfig:
    """Load a benchmark TOML file and resolve its runtime paths.

    Args:
        path: TOML file edited by the benchmark operator.

    Returns:
        Configuration with paths resolved from the backend directory.
    """
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    benchmark = raw["benchmark"]

    def resolve(value: str) -> Path:
        candidate = Path(value)
        return (
            candidate.resolve()
            if candidate.is_absolute()
            else (BACKEND_ROOT / candidate).resolve()
        )

    return RecallConfig(
        bundle_dir=resolve(benchmark["bundle_dir"]),
        workspace_dir=resolve(benchmark["workspace_dir"]),
        run_dir=resolve(benchmark["run_dir"]),
        modes=tuple(benchmark.get("modes", ["fast"])),
        rebuild_workspace=benchmark.get("rebuild_workspace", False),
        resume=benchmark.get("resume", True),
        app_settings=raw.get("app", {}),
        search_options=raw.get("search", {}),
        query_expansion=raw.get("query_expansion", {}),
    )


def _prepare_app_environment(config: RecallConfig) -> None:
    """Bind app globals to benchmark-owned storage before importing app modules."""
    for name, value in config.app_settings.items():
        if isinstance(value, bool):
            environment_value = str(value).lower()
        elif isinstance(value, (dict, list)):
            environment_value = json.dumps(value)
        else:
            environment_value = str(value)
        os.environ[name.upper()] = environment_value

    # app settings, SQLAlchemy and ChromaDB are initialized at import time.
    os.environ["SQLITE_DATABASE_PATH"] = str(
        config.workspace_dir / "database" / "sqlite.db"
    )
    os.environ["UPLOAD_FOLDER_PATH"] = str(config.workspace_dir / "storage")
    os.environ["CHROMADB_PATH"] = str(config.workspace_dir / "vector")


async def _materialize_index(
    *,
    config: RecallConfig,
    documents: list[BenchmarkDocument],
    session_factory: async_sessionmaker[AsyncSession],
    vector_db: "VectorDatabase",
    file_storage: "FileStorage",
    indexing_service: "SourceItemIndexingService",
) -> dict[str, Any]:
    """Create Source/SourceItems through app services and index every document.

    Args:
        config: Current benchmark configuration.
        documents: Controlled corpus manifest records.
        session_factory: App SQLAlchemy session factory.
        vector_db: App vector database implementation.
        file_storage: App file storage implementation.
        indexing_service: App source item indexing service.

    Returns:
        Stable benchmark document to SourceItem mapping used during scoring.

    Raises:
        RuntimeError: One or more documents fail during app indexing.
    """
    from fastapi import UploadFile

    from app.core.constants import SourceType
    from app.crud import SourceCRUD
    from app.db.schemas import SourceBase
    from app.services.sources import SourceItemUploadService, SourceService

    async with session_factory() as session:
        async with session.begin():
            source_crud = SourceCRUD(session)
            source = await SourceService(
                source_crud=source_crud,
                vector_db=vector_db,
                file_storage=file_storage,
            ).create_source(
                SourceBase(
                    source_name="TadaAsk RAG benchmark",
                    source_type=SourceType.LOCAL_FILE,
                )
            )
            upload_service = SourceItemUploadService(
                source_crud=source_crud,
                file_storage=file_storage,
            )

            item_by_document: dict[str, dict[str, int | str]] = {}
            for document in documents:
                document_path = config.bundle_dir / document.relative_path
                filename = f"{document.id}{document_path.suffix.lower()}"
                with document_path.open("rb") as handle:
                    uploaded = await upload_service.upload_file(
                        validated_files=[UploadFile(handle, filename=filename)],
                        source=source,
                    )
                source_item = await source_crud.get_source_item_by_uid(uploaded[0].uid)
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

    source_item_uids = [str(item["uid"]) for item in item_by_document.values()]
    final_counters = None
    async for event in indexing_service.ingest_source_items(
        source_uid=str(source_ref["uid"]),
        source_item_uids=source_item_uids,
    ):
        if event.counters is not None:
            final_counters = event.counters

    if final_counters is None or final_counters.failed:
        failed = final_counters.failed if final_counters is not None else len(documents)
        raise RuntimeError(
            f"benchmark document indexing failed: {failed} document(s); "
            "rebuild the workspace before retrying"
        )

    manifest = {"source": source_ref, "documents": item_by_document}
    manifest_path = config.workspace_dir / "index.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _create_query_expansion_completer(
    config: dict[str, str],
) -> "StructuredCompleter":
    """Create the configured app FullCompleter without persisting provider records."""
    from pydantic import SecretStr

    from app.db.schemas import ModelProfileRead, ProviderWithModelInternalRead
    from app.providers.factory import completer_factory

    api_key_env = config.get("api_key_env")
    api_key = os.environ.get(api_key_env) if api_key_env else None
    now = datetime.now(UTC)
    provider_with_model = ProviderWithModelInternalRead(
        uid="rag-benchmark-provider",
        name=config["provider"],
        base_url=config.get("base_url") or None,
        api_key=SecretStr(api_key) if api_key else None,
        created_at=now,
        updated_at=now,
        model_profile=ModelProfileRead(
            uid="rag-benchmark-query-expansion-model",
            model=config["model"],
            created_at=now,
            updated_at=now,
        ),
    )
    return completer_factory(provider_with_model)


def _score_results(
    *,
    case: BenchmarkCase,
    results: list["HybridSearchResult"],
    document_id_by_source_item_uid: dict[str, str],
) -> tuple[dict[str, float], dict[str, float]]:
    """Calculate document and exact-evidence recall over ranked chunks.

    Args:
        case: Answerable benchmark case with gold evidence.
        results: Ranked HybridSearchResult objects.
        document_id_by_source_item_uid: Index mapping back to benchmark documents.

    Returns:
        Document Recall@1/@3/@5 and Evidence Recall@1/@3/@5.
    """
    gold_document_ids = {evidence.document_id for evidence in case.gold_evidence}
    normalized_evidence = [
        (evidence.document_id, " ".join(evidence.text.split()).casefold())
        for evidence in case.gold_evidence
    ]
    document_recall: dict[str, float] = {}
    evidence_recall: dict[str, float] = {}

    for k in RECALL_K:
        hits = results[:k]
        retrieved_document_ids = {
            document_id_by_source_item_uid.get(hit.source_item_uid) for hit in hits
        }
        document_recall[str(k)] = len(
            gold_document_ids.intersection(retrieved_document_ids)
        ) / len(gold_document_ids)

        matched_evidence = 0
        for document_id, evidence_text in normalized_evidence:
            if any(
                document_id_by_source_item_uid.get(hit.source_item_uid) == document_id
                and evidence_text in " ".join(hit.content.split()).casefold()
                for hit in hits
            ):
                matched_evidence += 1
        evidence_recall[str(k)] = matched_evidence / len(normalized_evidence)

    return document_recall, evidence_recall


def _summarize_results(path: Path, modes: tuple[str, ...]) -> dict[str, Any]:
    """Aggregate checkpoint records without loading document content into stdout."""
    records_by_mode: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["mode"] in records_by_mode:
                records_by_mode[record["mode"]].append(record)

    summary: dict[str, Any] = {"modes": {}}
    for mode, records in records_by_mode.items():
        mode_summary: dict[str, Any] = {"case_count": len(records)}
        for metric in ("document_recall", "evidence_recall"):
            mode_summary[metric] = {
                f"@{k}": (
                    sum(record[metric][str(k)] for record in records) / len(records)
                    if records
                    else 0.0
                )
                for k in RECALL_K
            }
        summary["modes"][mode] = mode_summary
    return summary


def _create_app_services(
    settings: "Settings",
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[
    "VectorDatabase",
    "FileStorage",
    "SourceItemIndexingService",
    "HybridSearchService",
]:
    """Assemble the app indexing and retrieval components used by the runner."""
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
        session_factory=session_factory,
        file_storage=file_storage,
        file_parser_factory=create_default_file_parser_factory(),
        vector_db=vector_db,
        text_splitter=text_splitter,
        embedding=embedding,
        fts_provider=fts_provider,
    )
    search_service = HybridSearchService(
        session_factory=session_factory,
        vector_db=vector_db,
        query_expander=QueryExpander(),
        embedding=embedding,
        fts_provider=fts_provider,
        rerank_provider=rerank,
    )
    return vector_db, file_storage, indexing_service, search_service


async def _run_retrieval_cases(
    *,
    config: RecallConfig,
    cases: list[BenchmarkCase],
    modes: tuple["SearchMode", ...],
    source_ref: "SearchSourceRef",
    search_service: "HybridSearchService",
    completer: "StructuredCompleter",
    document_id_by_source_item_uid: dict[str, str],
) -> Path:
    """Search answerable cases sequentially and checkpoint each mode result."""
    from app.db.schemas import HybridSearchOptions

    results_path = config.run_dir / "recall.jsonl"
    completed: set[tuple[str, str]] = set()
    if config.resume and results_path.is_file():
        with results_path.open("r", encoding="utf-8") as handle:
            completed = {
                (record["case_id"], record["mode"])
                for line in handle
                if (record := json.loads(line))
            }
    elif results_path.exists():
        results_path.write_text("", encoding="utf-8")

    with results_path.open("a", encoding="utf-8", newline="\n") as output:
        for case in cases:
            if case.question_type == QuestionType.UNANSWERABLE:
                continue
            # Retrieval is evaluated after standalone rewriting, not as a test
            # of the conversation rewriter itself.
            query = case.expected_standalone_query or case.question
            for mode in modes:
                key = (case.id, mode.value)
                if key in completed:
                    continue
                results = await search_service.search(
                    query=query,
                    sources=[source_ref],
                    options=HybridSearchOptions(
                        **config.search_options,
                        mode=mode,
                    ),
                    completer=completer,
                )
                document_recall, evidence_recall = _score_results(
                    case=case,
                    results=results,
                    document_id_by_source_item_uid=document_id_by_source_item_uid,
                )
                record = {
                    "case_id": case.id,
                    "dataset": case.dataset,
                    "question_type": case.question_type.value,
                    "mode": mode.value,
                    "query": query,
                    "gold_document_ids": sorted(
                        {evidence.document_id for evidence in case.gold_evidence}
                    ),
                    "document_recall": document_recall,
                    "evidence_recall": evidence_recall,
                    "retrieved": [
                        {
                            "rank": rank,
                            "document_id": document_id_by_source_item_uid.get(
                                result.source_item_uid
                            ),
                            "source_item_uid": result.source_item_uid,
                            "chunk_id": result.chunk_id,
                            "content": result.content,
                            "rrf_score": result.rrf_score,
                            "rerank_score": result.rerank_score,
                        }
                        for rank, result in enumerate(results, start=1)
                    ],
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()
    return results_path


async def run_recall(config_path: Path) -> dict[str, Any]:
    """Run the in-process TadaAsk retrieval recall benchmark.

    The function deliberately avoids importing app modules until benchmark paths
    are bound, then assembles the same indexing and search components as the app.

    Args:
        config_path: Operator-managed recall TOML configuration.

    Returns:
        Aggregate recall metrics and artifact paths.
    """
    # Bind all import-time app globals before loading any app package.
    logger.add(sys.stderr, level="WARNING")
    config = load_recall_config(config_path)
    if config.rebuild_workspace and config.workspace_dir.exists():
        config.workspace_dir.relative_to(DATA_ROOT)
        if config.workspace_dir == DATA_ROOT:
            raise ValueError("benchmark workspace must be below the RAG data root")
        shutil.rmtree(config.workspace_dir)
    _prepare_app_environment(config)

    # All app imports must remain below the environment bootstrap above.
    from app.core.config import settings
    from app.core.constants import SearchMode
    from app.db import async_session, init_db, run_migrations
    from app.db.config import engine
    from app.providers.base import StructuredCompleter
    from app.services.search import SearchSourceRef

    modes = tuple(SearchMode(mode) for mode in config.modes)
    if max(RECALL_K) > config.search_options.get("top_k", 8):
        raise ValueError("search.top_k must be at least 5 for Recall@5")
    if any(mode != SearchMode.FAST for mode in modes):
        missing = {"provider", "model"}.difference(config.query_expansion)
        if missing:
            raise ValueError(
                "query_expansion.provider and query_expansion.model are required "
                "for adaptive/full recall"
            )

    # Initialize only the database and the RAG components needed by this run.
    config.workspace_dir.mkdir(parents=True, exist_ok=True)
    config.run_dir.mkdir(parents=True, exist_ok=True)
    await run_migrations()
    await init_db()

    vector_db, file_storage, indexing_service, search_service = _create_app_services(
        settings, async_session
    )

    # Reuse an existing isolated index or materialize it through app services.
    cases = load_jsonl(config.bundle_dir / "cases.jsonl", BenchmarkCase)
    documents = load_jsonl(config.bundle_dir / "documents.jsonl", BenchmarkDocument)
    index_path = config.workspace_dir / "index.json"
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = await _materialize_index(
            config=config,
            documents=documents,
            session_factory=async_session,
            vector_db=vector_db,
            file_storage=file_storage,
            indexing_service=indexing_service,
        )

    document_id_by_source_item_uid = {
        str(item["uid"]): document_id
        for document_id, item in index["documents"].items()
    }
    source_ref = SearchSourceRef(
        id=index["source"]["id"],
        uid=index["source"]["uid"],
        collection_name=index["source"]["collection_name"],
        source_item_ids=[item["id"] for item in index["documents"].values()],
    )

    # Search each answerable case and persist one checkpoint per mode.
    expansion_completer = (
        _create_query_expansion_completer(config.query_expansion)
        if any(mode != SearchMode.FAST for mode in modes)
        else None
    )
    # HybridSearchService never dereferences completer in its Fast branch.
    completer = cast(StructuredCompleter, expansion_completer)
    results_path = await _run_retrieval_cases(
        config=config,
        cases=cases,
        modes=modes,
        source_ref=source_ref,
        search_service=search_service,
        completer=completer,
        document_id_by_source_item_uid=document_id_by_source_item_uid,
    )

    # The CLI prints only this aggregate summary; chunk content stays in JSONL.
    summary = _summarize_results(results_path, tuple(mode.value for mode in modes))
    summary.update(
        {
            "answerable_case_count": sum(
                case.question_type != QuestionType.UNANSWERABLE for case in cases
            ),
            "skipped_unanswerable_count": sum(
                case.question_type == QuestionType.UNANSWERABLE for case in cases
            ),
            "results_path": str(results_path),
            "workspace_dir": str(config.workspace_dir),
        }
    )
    summary_path = config.run_dir / "recall-summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    await engine.dispose()
    return {**summary, "summary_path": str(summary_path)}
