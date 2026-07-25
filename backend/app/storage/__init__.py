from .base import FileDownloadTarget, FileStorage
from app.core.config import settings

__all__ = [
    "FileDownloadTarget",
    "FileStorage",
]


def file_storage_factory(
    storage_backend: str,
    *,
    base_path: str | None = None,
) -> FileStorage:
    """文件存储工厂函数；根据配置返回对应的文件存储实例"""
    # 目前仅实现了本地文件存储，未来可以根据 settings.file_storage_backend 扩展 S3 或其他云存储实现
    if storage_backend == "local":
        from .base import LocalFileStorage

        return LocalFileStorage(base_path=base_path or settings.upload_folder_path)
    raise ValueError(f"Unsupported file storage provider: {storage_backend}")
