from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.rate_limit import VisitorRateLimiter
from app.core.security import ProviderAPIKeyCipher
from app.db.fts import init_fts_tables
from app.db.models import Base
from app.ingestion.crawler import HTMLPageParser, WebCrawler
from app.ingestion.parser import create_default_file_parser_factory
from app.main import create_app
from app.rag import QueryExpander, SQLiteFTSProvider
from app.rag.utils import JiebaFTSTokenizer
from app.services.chat import (
    ChatOrchestratorService,
    CompactionService,
    ContextBuilder,
    GenerationRegistry,
)
from app.services.indexing import SourceItemIndexingService
from app.services.jobs import RAGJobManager
from app.services.search import HybridSearchService, RAGRetrievalService
from app.services.sources import WebCrawlSyncService
from app.storage.base import LocalFileStorage
from tests.helpers import (
    FakeEmbeddingProvider,
    FakeRerankProvider,
    FakeTextSplitter,
    FakeTokenCounter,
    FakeVectorDatabase,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """默认跳过 live mark 测试"""
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="运行需要网络、凭据或可能产生费用的 live 测试",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--run-live"):
        return

    skip_live = pytest.mark.skip(reason="需要显式传入 --run-live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def configure_test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试使用独立 JWT 配置，不依赖开发者本地 .env 或 CI secrets"""
    monkeypatch.setattr(
        settings,
        "jwt_secret_key",
        "tadaask-test-only-jwt-secret-key",
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")


@pytest.fixture
def fake_embedding() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def fake_rerank() -> FakeRerankProvider:
    return FakeRerankProvider()


@pytest.fixture
def fake_vector_db() -> FakeVectorDatabase:
    return FakeVectorDatabase()


@pytest.fixture
def fake_text_splitter() -> FakeTextSplitter:
    return FakeTextSplitter()


@pytest.fixture
def fake_token_counter() -> FakeTokenCounter:
    return FakeTokenCounter()


@pytest_asyncio.fixture
async def test_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_path = (tmp_path / "test.sqlite3").as_posix()
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await init_fts_tables(connection)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture
def file_storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(base_path=str(tmp_path / "uploads"))


@pytest.fixture
def runtime_overrides(
    session_factory: async_sessionmaker[AsyncSession],
    file_storage: LocalFileStorage,
    fake_embedding: FakeEmbeddingProvider,
    fake_rerank: FakeRerankProvider,
    fake_vector_db: FakeVectorDatabase,
    fake_text_splitter: FakeTextSplitter,
    fake_token_counter: FakeTokenCounter,
) -> dict[str, object]:
    """构建无网络、无模型下载的完整测试运行时。"""
    fts_provider = SQLiteFTSProvider(
        tokenizer=JiebaFTSTokenizer(
            cut_all=False,
            use_hmm=True,
            stop_words_file=None,
            jieba_stop_words_path=None,
            jieba_idf_path=None,
        )
    )
    query_expander = QueryExpander(cache_enabled=False)
    generation_registry = GenerationRegistry()
    context_builder = ContextBuilder(token_counter=fake_token_counter)
    compaction_service = CompactionService(
        session_factory=session_factory,
        token_counter=fake_token_counter,
    )
    hybrid_search_service = HybridSearchService(
        session_factory=session_factory,
        vector_db=fake_vector_db,
        query_expander=query_expander,
        embedding=fake_embedding,
        fts_provider=fts_provider,
        rerank_provider=fake_rerank,
    )
    rag_retrieval_service = RAGRetrievalService(
        hybrid_search_service=hybrid_search_service,
        token_counter=fake_token_counter,
    )
    file_parser_factory = create_default_file_parser_factory()
    crawler = WebCrawler(timeout=2.0, user_agent="TadaAsk-Test/1.0")
    html_parser = HTMLPageParser()

    return {
        "visitor_rate_limiter": VisitorRateLimiter(
            enabled=False,
            ip_project_per_minute=1,
            ip_project_per_hour=1,
            ip_per_minute=1,
            project_per_minute=1,
            stream_per_ip=1,
            stream_per_project=1,
        ),
        "api_key_cipher": ProviderAPIKeyCipher(
            encryption_key=Fernet.generate_key().decode("ascii")
        ),
        "file_storage": file_storage,
        "file_parser_factory": file_parser_factory,
        "web_crawler": crawler,
        "html_page_parser": html_parser,
        "vector_db": fake_vector_db,
        "generation_registry": generation_registry,
        "text_splitter": fake_text_splitter,
        "fts_search_provider": fts_provider,
        "embedding": fake_embedding,
        "query_expander": query_expander,
        "rerank": fake_rerank,
        "token_counter": fake_token_counter,
        "chat_context_builder": context_builder,
        "compaction_service": compaction_service,
        "hybrid_search_service": hybrid_search_service,
        "rag_retrieval_service": rag_retrieval_service,
        "chat_orchestrator_service": ChatOrchestratorService(
            session_factory=session_factory,
            context_builder=context_builder,
            generation_registry=generation_registry,
            compaction_service=compaction_service,
        ),
        "source_item_indexing_service": SourceItemIndexingService(
            session_factory=session_factory,
            file_storage=file_storage,
            file_parser_factory=file_parser_factory,
            vector_db=fake_vector_db,
            text_splitter=fake_text_splitter,
            embedding=fake_embedding,
            fts_provider=fts_provider,
        ),
        "web_crawl_sync_service": WebCrawlSyncService(
            session_factory=session_factory,
            crawler=crawler,
            html_parser=html_parser,
            vector_db=fake_vector_db,
        ),
        "rag_job_manager": RAGJobManager(),
    }


@pytest_asyncio.fixture
async def app(
    session_factory: async_sessionmaker[AsyncSession],
    runtime_overrides: dict[str, object],
) -> AsyncIterator[FastAPI]:
    test_app = create_app(
        session_factory=session_factory,
        initialize_runtime=False,
        state_overrides=runtime_overrides,
    )
    async with test_app.router.lifespan_context(test_app):
        yield test_app
    test_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
