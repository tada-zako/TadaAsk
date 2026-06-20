from .hybrid_search import HybridSearchService
from ..schemas import RAGRetrievalResult
from ..utils import TokenBudget
from app.rag import StandaloneQueryRewriter
from app.crud import RAGSearchCRUD
from app.providers import Message, StructuredCompleter
from app.db.models import Source, ChatMessage
from app.db.schemas import HybridSearchOptions, RAGSnapshotItem, RAGSnapshot
from app.core.constants import ChatMessageRole
from app.utils import TokenCounter


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
        token_counter: TokenCounter,
    ):
        self.rag_search_crud = rag_search_crud
        self.hybrid_search_service = hybrid_search_service
        self.token_counter = token_counter

    def _build_standalone_context(
        self,
        *,
        user_query: str,
        recent_messages: list[ChatMessage],
        compaction_message: ChatMessage | None,
        token_budget: TokenBudget,
    ) -> list[Message]:
        """构建 standalone 查询改写的上下文"""
        max_tokens = int(
            token_budget.max_input_tokens * token_budget.standalone_context_ratio
        )

        messages: list[Message] = []
        used = self.token_counter.count_message(user_query)

        # 上下文装入 compaction message
        if compaction_message:
            tokens = self.token_counter.count_message(compaction_message.message)
            if used + tokens <= max_tokens:
                messages.append(
                    Message(
                        role=ChatMessageRole.SYSTEM,
                        content=compaction_message.message,
                    )
                )
                used += tokens

        # 上下文装入 recent messages
        selected_recent: list[ChatMessage] = []
        for message in reversed(recent_messages):
            if message.role not in (
                ChatMessageRole.USER,
                ChatMessageRole.ASSISTANT,
            ):
                continue

            tokens = self.token_counter.count_message(message.message)
            if used + tokens > max_tokens:
                break

            selected_recent.append(message)
            used += tokens

        # 反转选中的 recent message
        for message in reversed(selected_recent):
            messages.append(Message(role=message.role, content=message.message))

        messages.append(
            Message(
                role=ChatMessageRole.USER,
                content=user_query,
            )
        )
        return messages

    async def retrieve_for_chat(
        self,
        *,
        sources: list[Source],
        user_query: str,
        recent_messages: list[ChatMessage],
        compaction_message: ChatMessage | None,
        rag_options: HybridSearchOptions,
        completer: StructuredCompleter,
        token_budget: TokenBudget,
    ) -> RAGRetrievalResult:
        """
        处理 Chat 场景的 RAG 检索请求
        """
        retrieval_query = user_query
        standalone_query = None

        # 判断是否需要进行独立查询改写
        if rag_options.standalone_enabled:
            # 构建改写上下文
            standalone_context = self._build_standalone_context(
                user_query=user_query,
                recent_messages=recent_messages,
                compaction_message=compaction_message,
                token_budget=token_budget,
            )

            standalone_query = await StandaloneQueryRewriter.rewrite(
                query=user_query,
                standalone_context=standalone_context,
                completer=completer,
            )
            retrieval_query = standalone_query

        # 调用混合搜索服务进行检索
        search_results = await self.hybrid_search_service.search(
            query=retrieval_query,
            sources=sources,
            completer=completer,
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
            items=snapshot_items,
        )

        context_content = None
        if blocks:
            context_content = "\n\n".join(blocks)

        return RAGRetrievalResult(
            snapshot=snapshot,
            context_content=context_content,
        )
