import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.constants import ChatMessageRole, ChatSessionType, SourceType
from app.crud import ChatMessageCRUD, SourceCRUD
from app.db import config as db_config
from app.db.fts import init_fts_tables
from app.db.models import ChatSession, DocumentChunk, Source, SourceItem


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_alembic_upgrade_from_empty_sqlite_and_fts_initialization(
    tmp_path, monkeypatch
) -> None:
    database_path = tmp_path / "migrated.sqlite3"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(db_config, "DATABASE_URL", database_url)
    alembic_config = Config(str(db_config.ALEMBIC_INI_PATH))

    await asyncio.to_thread(command.upgrade, alembic_config, "head")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            tables = {
                row[0]
                for row in (
                    await connection.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    )
                ).all()
            }
            assert {
                "sources",
                "source_items",
                "document_chunks",
                "chat_messages",
            } <= tables

            await init_fts_tables(connection)
            await connection.execute(
                text(
                    "SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'missing'"
                )
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_constraints_cascades_claims_and_chat_message_order(
    db_session: AsyncSession,
    session_factory,
) -> None:
    # ----- 测试 DB claim 是否真实排他 -----
    source = Source(
        source_name="database-source",
        collection_name="database-source-collection",
        source_type=SourceType.LOCAL_FILE,
    )
    db_session.add(source)
    await db_session.flush()
    item = SourceItem(
        source_id=source.id,
        item_key="item-key",
        title="item",
        filename="item.txt",
        storage_key="files/item.txt",
        item_hash="hash",
    )
    db_session.add(item)
    await db_session.flush()
    db_session.add(
        DocumentChunk(
            source_item_id=item.id,
            vector_id="vector-id",
            chunk_index=0,
            chunk_hash="chunk-hash",
            chunk_content="database integration",
            chunk_tokens="database integration",
            chunk_pos=0,
        )
    )
    await db_session.commit()

    async with session_factory() as session:
        crud = SourceCRUD(session)
        assert await crud.claim_source_item_for_ingest(
            source_uid=source.uid,
            source_item_uid=item.uid,
        )
        await session.commit()
    async with session_factory() as session:
        assert not await SourceCRUD(session).claim_source_item_for_ingest(
            source_uid=source.uid,
            source_item_uid=item.uid,
        )

    # ----- 测试 ChatMessage 添加顺序 -----
    async with session_factory() as session:
        session.add(
            ChatSession(
                title="chat",
                owner_type=ChatSessionType.ADMIN,
                provider="fake",
                model="fake-model",
            )
        )
        await session.flush()
        chat_session = (await session.execute(select(ChatSession))).scalar_one()
        messages = ChatMessageCRUD(session)
        first = await messages.append_message(
            chat_session_id=chat_session.id,
            role=ChatMessageRole.USER,
            message="one",
            provider="fake",
            model="fake-model",
        )
        second = await messages.append_message(
            chat_session_id=chat_session.id,
            role=ChatMessageRole.ASSISTANT,
            message="two",
            provider="fake",
            model="fake-model",
        )
        await session.commit()
        assert (first.sequence, second.sequence) == (1, 2)

    async with session_factory() as session:
        source_to_delete = await SourceCRUD(session).get_source_by_uid(source.uid)
        await session.delete(source_to_delete)
        await session.commit()
        assert (
            await session.execute(select(func.count(SourceItem.id)))
        ).scalar_one() == 0
        assert (
            await session.execute(select(func.count(DocumentChunk.id)))
        ).scalar_one() == 0
