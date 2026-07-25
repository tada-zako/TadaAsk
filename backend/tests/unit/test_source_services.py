from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CrawlEntryType, SourceType
from app.core.exceptions import SourceCreateConflictError
from app.crud import SourceCRUD
from app.db.models import Source, SourceItem
from app.db.schemas import DocumentChunkInternal, SourceCreate, WebCrawlConfig
from app.services.sources.file_upload import SourceItemUploadService
from app.services.sources.source import SourceService
from app.services.sources.source_item import SourceItemService
from tests.helpers import FakeVectorDatabase


async def create_source(
    session: AsyncSession,
    *,
    source_type: SourceType = SourceType.LOCAL_FILE,
) -> Source:
    source = Source(
        source_name=f"source-{source_type.value}-{id(session)}",
        collection_name=f"collection-{id(session)}-{source_type.value}",
        source_type=source_type,
    )
    session.add(source)
    await session.flush()
    return source


async def create_item(
    session: AsyncSession,
    source: Source,
    *,
    storage_key: str | None = "files/a.txt",
) -> SourceItem:
    item = SourceItem(
        source_id=source.id,
        item_key=storage_key or "https://example.test/page",
        title="original.txt",
        filename="original.txt" if storage_key else None,
        storage_key=storage_key,
        origin_url=None if storage_key else "https://example.test/page",
        item_hash="hash",
    )
    session.add(item)
    await session.flush()
    return item


@pytest.mark.asyncio
async def test_source_creation_normalizes_crawl_scope_and_detects_name_conflict(
    db_session: AsyncSession, fake_vector_db: FakeVectorDatabase, file_storage: object
) -> None:
    service = SourceService(
        source_crud=SourceCRUD(db_session), vector_db=fake_vector_db, file_storage=file_storage  # type: ignore[arg-type]
    )
    data = SourceCreate(
        sourceName="docs",
        sourceType=SourceType.WEB_CRAWL,
        webCrawlConfig=WebCrawlConfig(
            entry_type=CrawlEntryType.URL_LIST,
            urls=["https://docs.example.test/guide/start"],
        ),
    )

    source = await service.create_source(data)
    await db_session.commit()

    assert source.web_crawl_config["allowed_domains"] == ["docs.example.test"]
    assert source.collection_name in fake_vector_db.collections
    with pytest.raises(SourceCreateConflictError):
        await service.create_source(data)


@pytest.mark.asyncio
async def test_file_upload_persists_each_item_and_storage_failure_prevents_database_write(
    db_session: AsyncSession, file_storage: object
) -> None:
    source = await create_source(db_session)
    upload_service = SourceItemUploadService(
        source_crud=SourceCRUD(db_session), file_storage=file_storage  # type: ignore[arg-type]
    )
    uploads = [
        UploadFile(filename="notes.txt", file=BytesIO(b"same file")),
        UploadFile(filename="notes.txt", file=BytesIO(b"same file")),
    ]

    uploaded = await upload_service.upload_file(validated_files=uploads, source=source)
    await db_session.commit()

    assert len(uploaded) == 2
    assert uploaded[0].storage_key != uploaded[1].storage_key
    assert await file_storage.exists(uploaded[0].storage_key)  # type: ignore[union-attr]

    class FailingStorage:
        async def save_file(self, key: str, content: bytes) -> str:
            raise OSError("disk unavailable")

    failing_service = SourceItemUploadService(
        source_crud=SourceCRUD(db_session), file_storage=FailingStorage()
    )
    with pytest.raises(OSError):
        await failing_service.upload_file(
            validated_files=[UploadFile(filename="broken.txt", file=BytesIO(b"x"))],
            source=source,
        )

    items = (await db_session.execute(select(SourceItem))).scalars().all()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_source_item_rename_download_delete_and_source_cleanup(
    db_session: AsyncSession, fake_vector_db: FakeVectorDatabase, file_storage: object
) -> None:
    source = await create_source(db_session)
    item = await create_item(db_session, source=source)
    await file_storage.save_file(item.storage_key, b"contents")  # type: ignore[union-attr]
    fake_vector_db.create_collection(source.collection_name)
    fake_vector_db.add_data_to_collection(source.collection_name, ["vector-1"], [], [])
    # 让删除服务查询到关联向量 ID。
    await SourceCRUD(db_session).bulk_insert_document_chunks(
        [
            DocumentChunkInternal(
                source_item_id=item.id,
                vector_id="vector-1",
                chunk_index=0,
                chunk_hash="hash",
                chunk_content="contents",
                chunk_tokens="contents",
                chunk_pos=0,
            )
        ]
    )
    await db_session.commit()

    item_service = SourceItemService(
        source_crud=SourceCRUD(db_session), vector_db=fake_vector_db, file_storage=file_storage  # type: ignore[arg-type]
    )
    renamed = await item_service.rename_source_item(source=source, source_item=item, title="renamed.txt")
    download = await item_service.get_download_info(source=source, source_item=item)
    deleted = await item_service.delete_source_item(source=source, source_item=item)

    assert (renamed.title, renamed.filename) == ("renamed.txt", "renamed.txt")
    assert download.filename == "renamed.txt"
    assert deleted.deleted_vector_count == 1
    assert deleted.file_deleted

    remaining = await create_item(db_session, source=source, storage_key="files/remaining.txt")
    await file_storage.save_file(remaining.storage_key, b"remaining")  # type: ignore[union-attr]
    cleanup = await SourceService(
        source_crud=SourceCRUD(db_session), vector_db=fake_vector_db, file_storage=file_storage  # type: ignore[arg-type]
    ).delete_source(source=source)

    assert cleanup.deleted_source_item_count == 1
    assert cleanup.file_deleted_count == 1
    assert source.collection_name not in fake_vector_db.collections
