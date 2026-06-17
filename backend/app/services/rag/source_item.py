import os
from pathlib import Path

from fastapi import UploadFile
from loguru import logger

from app.storage import FileStorage
from app.db.models import Source
from app.db.schemas import (
    SourceItemInternal,
    SourceItemRead,
)
from app.crud import SourceCRUD
from app.utils.calcu_file_hash import calculate_file_hash


class SourceItemService:
    def __init__(
        self,
        *,
        source_crud: SourceCRUD,
        file_storage: FileStorage,
    ):
        """具体的参数由依赖注入"""
        self.source_crud = source_crud
        self.file_storage = file_storage

    def _resolve_unique_filename(self, filename: str, used_filename: set[str]) -> str:
        """
        基于已使用文件名集合，生成唯一的文件名；
        例如："document.pdf" -> "document(1).pdf" -> "document(2).pdf"
        """
        if filename not in used_filename:
            return filename

        name_part, ext_part = os.path.splitext(filename)
        counter = 1
        while True:
            new_filename = f"{name_part}({counter}){ext_part}"
            if new_filename not in used_filename:
                return new_filename
            counter += 1

    async def upload_file(
        self,
        *,
        validated_files: list[UploadFile],
        source: Source,
    ) -> list[SourceItemRead]:
        # 0. 查询 Source 已有文件名
        result = await self.source_crud.list_source_item_filenames_by_source_id(
            source_id=source.id
        )
        used_filenames = set(result)

        source_items = []
        for file in validated_files:
            # 1. 计算文件哈希值
            file_content = await file.read()
            file_hash = calculate_file_hash(
                file_content
            )  # NOTE: 假设 calculate_file_hash 处理速度较快

            # 2. 生成唯一文件名，避免同一 Source 下文件名冲突
            unique_filename = self._resolve_unique_filename(
                filename=file.filename,  # type: ignore
                used_filename=used_filenames,
            )
            used_filenames.add(unique_filename)  # 更新已使用文件名集合

            # 2. 文件查重；基于文件内容判断文件是否存在，相同文件名而内容不同，仍会重复存储
            ext = Path(unique_filename).suffix.lower()
            # 使用 hash 前两位作为子目录
            storage_key = f"{file_hash[:2]}/{file_hash}{ext}"
            file_exists = await self.file_storage.exists(key=storage_key)

            # 3. 文件存储
            if not file_exists:
                await self.file_storage.save_file(key=storage_key, content=file_content)
                logger.info(
                    f"文件 '{unique_filename}' 已保存到存储系统，存储键：{storage_key}"
                )
            else:
                logger.info(
                    f"文件 '{unique_filename}' 已存在于存储系统，存储键：{storage_key}，跳过保存"
                )

            # 4. 创建 SourceItemInternal 实例
            source_items.append(
                SourceItemInternal(
                    item_key=storage_key,
                    title=unique_filename,
                    filename=unique_filename,
                    storage_key=storage_key,
                    origin_url=None,
                    item_hash=file_hash,
                )
            )

        # 5. 执行写库操作
        created_items = await self.source_crud.add_source_items(
            source=source, items_data=source_items
        )

        return [SourceItemRead.model_validate(item) for item in created_items]
