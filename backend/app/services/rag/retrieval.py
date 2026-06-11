from pydantic import BaseModel, Field

from .hybrid_search import HybridSearchService
from app.rag import StandaloneQueryRewriter
from app.crud import RAGSearchCRUD
from app.providers import Message
from app.db.models import Source, ChatMessage
from app.db.schemas import HybridSearchOptions


class RAGSnapshotItem(BaseModel):
    """RAG 检索结果快照项"""

    citation_id: int
    source_id: int
    source_item_id: int
    chunk_id: int
    vector_id: str | None = None

    rrf_score: float | None = None
    rerank_score: float | None = None
    used_in_context: bool = True


class RAGSnapshot(BaseModel):
    """RAG 检索结果快照"""

    version: int = 1
    query: str
    standalone_query: str | None = None
    search_options: HybridSearchOptions
    items: list[RAGSnapshotItem] = Field(default_factory=list)


class RAGRetrievalResult(BaseModel):
    """RAG 检索结果"""

    snapshot: RAGSnapshot
    context_block: str | None  # 基于检索结果构建的 RAG block，用于构建 context


class RAGRetrievalService:
    """
    RAG 检索服务
     - 负责处理与检索相关的业务逻辑
    """

    def __init__(
        self,
        *,
        rag_search_crud: RAGSearchCRUD,
        hybrid_search_service: HybridSearchService,
        standalone_rewriter: StandaloneQueryRewriter,
    ):
        self.rag_search_crud = rag_search_crud
        self.hybrid_search_service = hybrid_search_service
        self.standalone_rewriter = standalone_rewriter

    async def retrieve_for_chat(
        self,
        *,
        sources: list[Source],
        user_query: str,
        recent_messages: list[ChatMessage],
        rag_options: HybridSearchOptions,
    ) -> RAGRetrievalResult:
        """
        处理 Chat 场景的 RAG 检索请求
        """
        retrieval_query = user_query
        standalone_query = None

        # 判断是否需要进行独立查询改写
        if rag_options.standalone_enabled:
            standalone_query = await self.standalone_rewriter.rewrite(
                query=user_query,
                # TODO: recent_messages 需要内部处理；包括限制数量等
                recent_messages=recent_messages,
            )
            retrieval_query = standalone_query

        # 调用混合搜索服务进行检索
        search_results = await self.hybrid_search_service.search(
            query=retrieval_query,
            sources=sources,
            options=rag_options,
        )

        # 构建 RAG 检索结果快照以及 RAG 上下文
        blocks: list[str] = []
        snapshot_items: list[RAGSnapshotItem] = []

        for index, result in enumerate(search_results):
            title = result.title or result.filename
            header = f"[{index}] {title}"
            if result.section_header:
                header += f" / {result.section_header}"

            content = result.content.strip()
            blocks.append(f"{header}\n{content}")

            snapshot_item = RAGSnapshotItem(
                citation_id=index + 1,
                source_id=result.source_id,
                source_item_id=result.source_item_id,
                chunk_id=result.chunk_id,
                vector_id=result.vector_id,
                rrf_score=result.rrf_score,
                rerank_score=result.rerank_score,
                used_in_context=True,  # 默认都使用，后续可以根据策略调整
            )
            snapshot_items.append(snapshot_item)

        snapshot = RAGSnapshot(
            query=user_query,
            standalone_query=standalone_query,
            search_options=rag_options,
            items=snapshot_items,
        )

        context_block = (
            "[Knowledge Base Context]\n"
            + "\n\n".join(blocks)
            + "\n[/Knowledge Base Context]"
        )

        return RAGRetrievalResult(
            snapshot=snapshot,
            context_block=context_block,
        )
