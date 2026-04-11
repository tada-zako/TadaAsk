from typing import Protocol, runtime_checkable, Any, Iterable

from pydantic import BaseModel, Field
from langchain_core.documents import Document


class VectorQueryItem(BaseModel):
    id: str
    document: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    distance: float


@runtime_checkable
class VectorDatabase(Protocol):
    def create_collection(self, collection_name: str):
        """创建新的集合"""
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
