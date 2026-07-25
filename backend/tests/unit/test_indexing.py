from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SourceItemProcessStatus, SourceType
from app.core.exceptions import DocumentPausedException
from app.crud import SourceCRUD
from app.db.models import DocumentChunk, DocumentContent, Source, SourceItem
from app.ingestion import ParsedDocument, ParsedSection
from app.services.indexing.chunk_index_writer import DocumentChunkIndexWriter, generate_vector_id
from app.services.indexing.source_item_indexing import SourceItemIndexingService
from tests.helpers import FakeEmbeddingProvider, FakeTextSplitter, FakeVectorDatabase


class FakeFTSProvider:
    def tokenize_for_index(self, text: str) -> str:
        return f"tokens:{text}"


async def create_source_item(
    session: AsyncSession,
    *,
    status: SourceItemProcessStatus = SourceItemProcessStatus.PENDING,
) -> tuple[Source, SourceItem]:
    source = Source(
        source_name=f"index-source-{id(session)}-{status.value}",
        collection_name=f"index-collection-{id(session)}-{status.value}",
        source_type=SourceType.LOCAL_FILE,
    )
    session.add(source)
    await session.flush()
    item = SourceItem(
        source_id=source.id,
        item_key=f"item-{status.value}",
        title="document.txt",
        filename="document.txt",
        storage_key="documents/document.txt",
        item_hash="hash",
        status=status,
    )
    session.add(item)
    await session.flush()
    return source, item


async def collect_events(events: AsyncIterator[object]) -> list[object]:
    return [event async for event in events]


@pytest.mark.asyncio
async def test_claim_source_item_is_exclusive(db_session: AsyncSession) -> None:
    source, item = await create_source_item(db_session)
    crud = SourceCRUD(db_session)

    assert await crud.claim_source_item_for_ingest(source_uid=source.uid, source_item_uid=item.uid)
    assert not await crud.claim_source_item_for_ingest(source_uid=source.uid, source_item_uid=item.uid)


@pytest.mark.asyncio
async def test_chunk_writer_persists_sections_pages_vectors_and_replaces_old_index(
    db_session: AsyncSession,
) -> None:
    source, item = await create_source_item(db_session)
    vector_db = FakeVectorDatabase()
    vector_db.create_collection(source.collection_name)
    writer = DocumentChunkIndexWriter(
        source_crud=SourceCRUD(db_session),
        vector_db=vector_db,
        text_splitter=FakeTextSplitter(chunk_size=6),
        embedding=FakeEmbeddingProvider(),
        fts_provider=FakeFTSProvider(),
    )
    document = ParsedDocument(
        text="abcdefghi", title="doc", source_type=SourceType.LOCAL_FILE,
        page_boundaries=[(0, 6), (6, 20)],
        sections=[
            ParsedSection(start=0, header="First", anchor="#first", level=1),
            ParsedSection(start=6, header="Second", level=2),
        ],
    )

    events = await collect_events(
        writer.index_parsed_document(
            source=source,
            source_item=item,
            parsed_doc=document,
        )
    )
    await db_session.commit()
    rows = (await db_session.execute(select(DocumentChunk).order_by(DocumentChunk.chunk_index))).scalars().all()

    assert len(events) == 3
    assert [row.vector_id for row in rows] == [
        generate_vector_id(item.id, 0),
        generate_vector_id(item.id, 1),
    ]
    assert [(row.section_header, row.page_number) for row in rows] == [
        ("First", 1),
        ("Second", 2),
    ]
    assert rows[0].metadata_json == {
        "anchor": "#first",
        "section_level": 1,
        "origin_url": None,
    }
    assert set(vector_db.collections[source.collection_name]) == {row.vector_id for row in rows}

    await collect_events(
        writer.index_parsed_document(
            source=source,
            source_item=item,
            parsed_doc=ParsedDocument(
                text="new",
                title="doc",
                source_type=SourceType.LOCAL_FILE,
            ),
        )
    )
    await db_session.commit()
    rows = (await db_session.execute(select(DocumentChunk))).scalars().all()
    assert [row.chunk_content for row in rows] == ["new"]
    assert set(vector_db.collections[source.collection_name]) == {generate_vector_id(item.id, 0)}


@pytest.mark.asyncio
async def test_pause_checkpoint_and_resume_restore_terminal_status(
    session_factory, file_storage, fake_vector_db, fake_text_splitter, fake_embedding
) -> None:
    async with session_factory() as session:
        source, item = await create_source_item(session, status=SourceItemProcessStatus.PAUSE_REQUESTED)
        await session.commit()
    service = SourceItemIndexingService(
        session_factory=session_factory,
        file_storage=file_storage,
        file_parser_factory=object(),
        vector_db=fake_vector_db,
        text_splitter=fake_text_splitter,
        embedding=fake_embedding,
        fts_provider=FakeFTSProvider(),
    )

    with pytest.raises(DocumentPausedException, match="paused by user request"):
        await service._pause_checkpoint(source_item_id=item.id)

    async with session_factory() as session:
        paused = await SourceCRUD(session).get_source_item_by_id(item.id)
        assert paused.status == SourceItemProcessStatus.PAUSED

        session.add(DocumentContent(source_item_id=item.id, content="resumable text"))
        await session.commit()

    events = await collect_events(
        service.resume_source_items(source_uid=source.uid, source_item_uids=[item.uid])
    )

    assert events[-1].counters.completed == 1  # type: ignore[attr-defined]
    async with session_factory() as session:
        completed = await SourceCRUD(session).get_source_item_by_id(item.id)
        assert completed.status == SourceItemProcessStatus.COMPLETED


@pytest.mark.asyncio
async def test_ingest_failure_marks_item_failed(
    session_factory,
    file_storage,
    fake_vector_db,
    fake_text_splitter,
    fake_embedding,
) -> None:
    async with session_factory() as session:
        source, item = await create_source_item(session)
        await session.commit()
    service = SourceItemIndexingService(
        session_factory=session_factory,
        file_storage=file_storage,
        file_parser_factory=object(),
        vector_db=fake_vector_db,
        text_splitter=fake_text_splitter,
        embedding=fake_embedding,
        fts_provider=FakeFTSProvider(),
    )

    events = await collect_events(service._process_single_document(source_uid=source.uid, source_item_uid=item.uid))

    assert events[-1].source_item_status == SourceItemProcessStatus.FAILED  # type: ignore[attr-defined]
    async with session_factory() as session:
        failed = await SourceCRUD(session).get_source_item_by_id(item.id)
        assert failed.status == SourceItemProcessStatus.FAILED
