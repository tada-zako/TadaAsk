from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SearchMode, SourceType
from app.crud import SourceCRUD
from app.db.models import DocumentChunk, DocumentContent
from app.db.schemas import HybridSearchOptions, SourceCreate
from app.services.search import SearchSourceRef
from app.services.sources import (
    SourceItemService,
    SourceItemUploadService,
    SourceService,
)
from tests.helpers import FakeCompleter, FakeVectorDatabase


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_local_file_source_pipeline_indexes_searches_and_cleans_up(
    db_session: AsyncSession,
    session_factory,
    file_storage,
    runtime_overrides,
    fake_vector_db: FakeVectorDatabase,
) -> None:
    # ----- 测试本地文件 SourceItem 上传业务 -----
    source_service = SourceService(
        source_crud=SourceCRUD(db_session),
        vector_db=fake_vector_db,
        file_storage=file_storage,
    )
    source = await source_service.create_source(
        SourceCreate(sourceName="pipeline-source", sourceType=SourceType.LOCAL_FILE)
    )
    await db_session.commit()

    uploaded = await SourceItemUploadService(
        source_crud=SourceCRUD(db_session),
        file_storage=file_storage,
    ).upload_file(
        validated_files=[
            UploadFile(
                filename="guide.txt",
                file=BytesIO(b"Python deployment guide. Run deployment safely."),
            )
        ],
        source=source,
    )
    await db_session.commit()
    item_uid = uploaded[0].uid
    storage_key = uploaded[0].storage_key
    assert await file_storage.exists(storage_key)

    # ----- 测试 SourceItem indexing 业务 -----
    indexing_service = runtime_overrides["source_item_indexing_service"]
    events = [
        event
        async for event in indexing_service.ingest_source_items(
            source_uid=source.uid,
            source_item_uids=[item_uid],
        )
    ]
    assert events[-1].counters.completed == 1

    async with session_factory() as session:
        source_crud = SourceCRUD(session)
        indexed_source, indexed_item = await source_crud.get_source_and_item_by_uid(
            source_uid=source.uid,
            source_item_uid=item_uid,
        )
        content = (
            await session.execute(
                select(DocumentContent).where(
                    DocumentContent.source_item_id == indexed_item.id
                )
            )
        ).scalar_one()
        chunks = list(
            (
                await session.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.source_item_id == indexed_item.id
                    )
                )
            ).scalars()
        )

    assert "deployment" in content.content.lower()
    assert chunks
    assert (
        chunks[0].vector_id
        in fake_vector_db.collections[indexed_source.collection_name]
    )

    # ----- 测试 hybrid search 业务功能 -----
    search_service = runtime_overrides["hybrid_search_service"]
    results = await search_service.search(
        query="deployment",
        sources=[
            SearchSourceRef(
                id=indexed_source.id,
                uid=indexed_source.uid,
                collection_name=indexed_source.collection_name,
                source_item_ids=[indexed_item.id],
            )
        ],
        options=HybridSearchOptions(mode=SearchMode.FAST, top_k=1),
        completer=FakeCompleter(),
    )
    assert [result.source_item_id for result in results] == [indexed_item.id]

    # ----- 测试 SourceItem 清理逻辑 -----
    async with session_factory() as session:
        source_to_delete, item_to_delete = await SourceCRUD(
            session
        ).get_source_and_item_by_uid(
            source_uid=source.uid,
            source_item_uid=item_uid,
        )
        deletion = await SourceItemService(
            source_crud=SourceCRUD(session),
            vector_db=fake_vector_db,
            file_storage=file_storage,
        ).delete_source_item(source=source_to_delete, source_item=item_to_delete)
        await session.commit()

    assert deletion.deleted_vector_count == len(chunks)
    assert deletion.file_deleted
    assert not await file_storage.exists(storage_key)
    assert not fake_vector_db.collections[source.collection_name]
    async with session_factory() as session:
        assert await SourceCRUD(session).get_source_item_by_uid(item_uid) is None
