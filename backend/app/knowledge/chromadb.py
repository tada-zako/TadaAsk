from pathlib import Path
from typing import Any, Iterable
import uuid

from chromadb import PersistentClient
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from loguru import logger

from app.core.config import settings


class ChromaQueryItem(BaseModel):
    id: str
    document: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    distance: float


class ChromaDB:
    def __init__(self):
        # 确保向量数据库路径存在
        Path(settings.chromadb_path).mkdir(parents=True, exist_ok=True)

        self.client = PersistentClient(path=settings.chromadb_path)
        self.embedding_function = DefaultEmbeddingFunction()

        # 基于句柄切割文本
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", "", ".", "。", "!", "！", "?", "？"],
            chunk_size=1000,
        )

    def create_collection(self, collection_name: str):
        """创建新的集合"""
        self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,  # type: ignore
            get_or_create=False,  # 明确创建新集合
        )

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
        collection = self.client.get_or_create_collection(
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
    ) -> list[ChromaQueryItem]:
        """
        查询向量库，返回匹配度最高的 top_k 条结果

        Args:
            collection_name: 向量库集合名称
            query_text: 查询文本
            top_k: 返回的结果数量，默认为 5
        """

        collection = self.client.get_collection(name=collection_name)

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
            ChromaQueryItem(
                id=id,
                document=doc,
                metadata=dict(meta),
                distance=dis,
            )
            for id, doc, meta, dis in zip(ids, docs, metas, distances)
        ]

    def delete_collection(self, collection_name: str):
        """删除指定名称的集合"""
        self.client.delete_collection(name=collection_name)
        logger.debug(f"集合 '{collection_name}' 已删除")


chromadb = ChromaDB()
