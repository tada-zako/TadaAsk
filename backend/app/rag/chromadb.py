from typing import Protocol, runtime_checkable, Any
from pathlib import Path
from dataclasses import dataclass

from chromadb import PersistentClient, Collection as ChromaCollection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from numpy.typing import NDArray
import numpy as np
from loguru import logger

from app.core.config import settings


@dataclass
class VectorQueryResult:
    vector_id: str  # 向量 ID
    metadata: dict[str, Any]
    distance: float


@runtime_checkable
class VectorDatabase(Protocol):
    def create_collection(self, collection_name: str):
        """创建新的集合"""
        ...

    def get_collection(self, collection_name: str) -> Any:
        """获取集合"""
        ...

    def add_data_to_collection(
        self,
        collection: Any,
        ids: list[str],
        embeddings: list[NDArray[np.float32]],
        metadatas: list[dict[str, Any]],
    ):
        """将数据添加到集合中"""
        ...

    def update_data_in_collection(
        self,
        collection: Any,
        ids: list[str],
        embeddings: list[NDArray[np.float32]],
        metadatas: list[dict[str, Any]],
    ):
        """更新集合中的数据"""
        ...

    def delete_data_from_collection(self, collection: Any, ids: list[str]):
        """从集合中删除数据"""
        ...

    def query_collection(
        self,
        query_embedding: NDArray[np.float32],
        collection: Any,
        top_k: int = 5,
    ) -> list[VectorQueryResult]:
        """查询集合，返回匹配度最高的 top_k 条结果"""
        ...

    def delete_collection(self, collection_name: str):
        """删除集合及其所有文档"""
        ...


class ChromaDB:
    def __init__(self):
        # 确保向量数据库路径存在
        Path(settings.chromadb_path).mkdir(parents=True, exist_ok=True)

        self._client = PersistentClient(path=settings.chromadb_path)
        self.embedding_function = DefaultEmbeddingFunction()  # 保留默认使用的嵌入函数

    def create_collection(self, collection_name: str):
        """创建新的集合"""
        self._client.create_collection(name=collection_name)

    def get_collection(self, collection_name: str) -> ChromaCollection:
        """获取集合"""
        return self._client.get_collection(name=collection_name)

    def add_data_to_collection(
        self,
        collection: ChromaCollection,
        ids: list[str],
        embeddings: list[NDArray[np.float32]],
        metadatas: list[dict[str, Any]],
    ):
        """将数据添加到集合中"""
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def update_data_in_collection(
        self,
        collection: ChromaCollection,
        ids: list[str],
        embeddings: list[NDArray[np.float32]],
        metadatas: list[dict[str, Any]],
    ):
        """更新集合中的数据"""
        collection.update(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def delete_data_from_collection(self, collection: ChromaCollection, ids: list[str]):
        """从集合中删除数据"""
        collection.delete(ids=ids)

    def query_collection(
        self,
        query_embedding: NDArray[np.float32],
        collection: ChromaCollection,
        top_k: int = 5,
    ) -> list[VectorQueryResult]:
        """查询集合，返回匹配度最高的 top_k 条结果"""
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        ids = (results["ids"] or [[]])[0]
        metas = (results["metadatas"] or [[]])[0]
        distances = (results["distances"] or [[]])[0]

        return [
            VectorQueryResult(
                vector_id=id,
                metadata=dict(meta),
                distance=dis,
            )
            for id, meta, dis in zip(ids, metas, distances)
        ]

    def delete_collection(self, collection_name: str):
        """删除指定名称的集合"""
        self._client.delete_collection(name=collection_name)
        logger.debug(f"集合 '{collection_name}' 已删除")
