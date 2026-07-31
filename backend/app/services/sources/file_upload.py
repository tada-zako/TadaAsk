from pathlib import Path
import uuid

from fastapi import UploadFile
from loguru import logger

from app.storage import FileStorage
from app.db.models import Source
from app.db.schemas import (
    SourceItemInternal,
    SourceItemRead,
)
from app.crud import SourceCRUD
from app.utils import calculate_file_hash


class SourceItemUploadService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        file_storage: FileStorage,
    ):
        """具体的参数由依赖注入"""
        self.source_crud = source_crud
        self.file_storage = file_storage

    def _build_storage_key(self, *, file_hash: str, filename: str) -> str:
        """生成唯一 storage_key
        storage_key = "{file_hash[:2]}/{file_hash}_{uuid4}{ext}"
        """
        ext = Path(filename).suffix.lower()
        return f"{file_hash[:2]}/{file_hash}_{uuid.uuid4().hex}{ext}"

    async def upload_file(
        self,
        *,
        validated_files: list[UploadFile],
        source: Source,
    ) -> list[SourceItemRead]:
        source_items = []
        uploaded_bytes = 0
        for file in validated_files:
            # 1. 计算文件哈希值
            file_content = await file.read()
            file_hash = calculate_file_hash(file_content)

            # 允许上传同名文件
            filename = file.filename or "uploaded_file"
            storage_key = self._build_storage_key(
                file_hash=file_hash,
                filename=filename,
            )

            # 2. 文件存储；每个 source_item 独占一个存储对象，便于删除时直接清理
            await self.file_storage.save_file(key=storage_key, content=file_content)
            uploaded_bytes += len(file_content)

            # 3. 创建 SourceItemInternal 实例
            source_items.append(
                SourceItemInternal(
                    item_key=storage_key,
                    title=filename,
                    filename=filename,
                    storage_key=storage_key,
                    origin_url=None,
                    item_hash=file_hash,
                    metadata_json=None,
                )
            )

        # 4. 执行写库操作
        created_items = await self.source_crud.add_source_items(
            source=source, items_data=source_items
        )
        logger.bind(
            event="source.files.uploaded",
            source_uid=source.uid,
            file_count=len(created_items),
            uploaded_bytes=uploaded_bytes,
        ).info("Source files uploaded")

        return [SourceItemRead.model_validate(item) for item in created_items]
