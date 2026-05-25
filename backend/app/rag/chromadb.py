from typing import Protocol, runtime_checkable, Any, Iterable
from pathlib import Path
import uuid

from chromadb import PersistentClient, Collection as ChromaCollection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from loguru import logger

from app.core.config import settings


class VectorQueryResult(BaseModel):
    id: str
    document: str
    metadata: dict[str, Any] = Field(default_factory=dict)
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
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ):
        """将数据添加到集合中"""
        ...

    def update_data_in_collection(
        self,
        collection: Any,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ):
        """更新集合中的数据"""
        ...

    def delete_data_from_collection(self, collection: Any, ids: list[str]):
        """从集合中删除数据"""
        ...

    def query_collection(
        self,
        query_embedding: list[float],
        collection: Any,
        top_k: int = 5,
    ) -> list[VectorQueryResult]:
        """查询集合，返回匹配度最高的 top_k 条结果"""
        ...

    def upsert_documents(
        self,
        collection_name: str,
        documents: Iterable[Document],
        hash_key: str | None = None,
    ) -> int:
        """
        同步执行的文本存储方法，将文本块存储到向量库中

        Args:
            collection_name: 向量库集合名称
            documents: 待存储的文本块列表
            hash_key: 可选的哈希键，用于生成文档唯一 ID，默认为 None

        Returns:
            存储的文本块数量
        """
        ...

    def query(
        self, collection_name: str, query_text: str, top_k: int = 5
    ) -> list[VectorQueryItem]:
        """
        查询向量库，返回匹配度最高的 top_k 条结果

        Args:
            collection_name: 向量库集合名称
            query_text: 查询文本内容
            top_k: 返回结果数量上限，默认为 5

        Returns:
            匹配度最高的 top_k 条结果列表，每条结果包含文档内容、元数据和距离信息
        """
        ...

    def delete_collection(self, collection_name: str):
        """删除集合及其所有文档"""
        ...


class ChromaDB:
    def __init__(self):
        # 确保向量数据库路径存在
        Path(settings.chromadb_path).mkdir(parents=True, exist_ok=True)

        self._client = PersistentClient(path=settings.chromadb_path)
        self.embedding_function = DefaultEmbeddingFunction()

        # 基于句柄切割文本
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", "", ".", "。", "!", "！", "?", "？"],
            chunk_size=1000,
        )

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
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ):
        """将数据添加到集合中"""
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def update_data_in_collection(
        self,
        collection: ChromaCollection,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ):
        """更新集合中的数据"""
        collection.update(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def delete_data_from_collection(self, collection: ChromaCollection, ids: list[str]):
        """从集合中删除数据"""
        collection.delete(ids=ids)

    def query_collection(
        self,
        query_embedding: list[float],
        collection: ChromaCollection,
        top_k: int = 5,
    ) -> list[VectorQueryResult]:
        """查询集合，返回匹配度最高的 top_k 条结果"""
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        ids = (results["ids"] or [[]])[0]
        docs = (results["documents"] or [[]])[0]
        metas = (results["metadatas"] or [[]])[0]
        distances = (results["distances"] or [[]])[0]

        return [
            VectorQueryResult(
                id=id,
                document=doc,
                metadata=dict(meta),
                distance=dis,
            )
            for id, doc, meta, dis in zip(ids, docs, metas, distances)
        ]

    def upsert_documents(
        self,
        collection_name: str,
        documents: Iterable[Document],
        hash_key: str | None = None,
    ) -> int:
        """
        同步执行的文本存储方法，将文本块存储到 ChromaDB 向量库中

        Args:
            collection_name: 向量库集合名称
            documents: 待存储的文本块列表
            hash_key: 可选的哈希键，用于生成文档唯一 ID，默认为 None

        Returns:
            存储的文本块数量
        """

        # 获取或创建集合，使用默认的嵌入函数
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,  # type: ignore
        )

        # 切割文本
        chunks = self.text_splitter.split_documents(documents)
        logger.debug(f"切割文本为 {len(chunks)} 个块")

        # 生成唯一 ID：当未提供 hash_key 时使用随机前缀避免覆盖已有文档块
        key = hash_key or uuid.uuid4().hex[:16]
        ids = [f"{key}_chunk_{i}" for i in range(len(chunks))]

        # 存入向量库
        collection.upsert(
            ids=ids,
            documents=[doc.page_content for doc in chunks],
            metadatas=[doc.metadata for doc in chunks],
        )
        logger.debug(f"已将 {len(chunks)} 个文本块存储到集合 '{collection_name}' 中")

        return len(chunks)

    def query(
        self, collection_name: str, query_text: str, top_k: int = 5
    ) -> list[VectorQueryItem]:
        """
        查询向量库，返回匹配度最高的 top_k 条结果

        Args:
            collection_name: 向量库集合名称
            query_text: 查询文本
            top_k: 返回的结果数量，默认为 5
        """

        collection = self._client.get_collection(name=collection_name)

        results = collection.query(
            query_texts=[query_text],
            n_results=top_k,
        )

        # 解析查询结果
        ids = (results["ids"] or [[]])[0]
        docs = (results["documents"] or [[]])[0]
        metas = (results["metadatas"] or [[]])[0]
        distances = (results["distances"] or [[]])[0]

        return [
            VectorQueryItem(
                id=id,
                document=doc,
                metadata=dict(meta),
                distance=dis,
            )
            for id, doc, meta, dis in zip(ids, docs, metas, distances)
        ]

    def delete_collection(self, collection_name: str):
        """删除指定名称的集合"""
        self._client.delete_collection(name=collection_name)
        logger.debug(f"集合 '{collection_name}' 已删除")
