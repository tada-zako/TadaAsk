from typing import Protocol, runtime_checkable
from pathlib import Path
import asyncio


@runtime_checkable
class FileStorage(Protocol):
    """文件存储接口"""

    async def save_file(self, key: str, content: bytes) -> str:
        """
        保存文件

        Args:
            key: 文件存储键；可以是文件名或路径
            content: 文件内容的字节数据

        Returns:
            存储后的文件 key
        """
        ...

    async def load_file(self, key: str) -> bytes:
        """加载文件内容"""
        ...

    async def delete_file(self, key: str) -> bool:
        """删除文件"""
        ...

    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        ...


class LocalFileStorage:
    """本地文件存储实现"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)

        # 确保 base_path 存在
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_file(self, key: str, content: bytes) -> str:
        """保存文件到本地"""
        file_path = self.base_path / key

        def _write():
            file_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            with open(file_path, "wb") as f:
                f.write(content)

        await asyncio.to_thread(_write)
        return key

    async def load_file(self, key: str) -> bytes:
        """加载文件内容"""
        file_path = self.base_path / key
        if not file_path.exists():
            raise FileNotFoundError(f"File {key} not found")

        return await asyncio.to_thread(file_path.read_bytes)

    async def delete_file(self, key: str) -> bool:
        """删除文件"""
        file_path = self.base_path / key

        def _delete():
            if file_path.exists():
                file_path.unlink()
                return True
            return False

        return await asyncio.to_thread(_delete)

    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        file_path = self.base_path / key
        return await asyncio.to_thread(file_path.exists)
