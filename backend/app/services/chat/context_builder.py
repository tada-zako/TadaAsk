from ..utils import TokenBudget
from app.providers import Message
from app.db.models import ChatMessage
from app.core.constants import ChatMessageRole
from app.utils import TokenCounter


class ContextBuilder:
    """
    LLM 对话上下文构建器
    """

    def __init__(self, *, token_counter: TokenCounter):
        self.token_counter = token_counter

    def _select_recent_messages(
        self,
        *,
        recent_messages: list[ChatMessage],
        max_tokens: int,
    ) -> tuple[list[ChatMessage], int]:
        """
        从 recent_messages 中选择靠近 current_message 的消息，直到达到 max_tokens 限制

        返回值：
            - 选中的 recent_messages 列表（顺序为靠近 current_message 的消息在前）
            - 选中消息的总 token 数量
        """
        selected_messages: list[ChatMessage] = []
        used_tokens = 0

        for message in reversed(recent_messages):
            if message.role not in (
                ChatMessageRole.USER,
                ChatMessageRole.ASSISTANT,
            ):
                continue

            message_tokens = self.token_counter.count_message(message.message)

            if used_tokens + message_tokens > max_tokens:
                break

            selected_messages.append(message)
            used_tokens += message_tokens

        selected_messages.reverse()  # 将选中的消息列表反转为正序
        return selected_messages, used_tokens

    def build_chat_context(
        self,
        *,
        system_prompt: str,
        compaction_message: ChatMessage | None,
        recent_messages: list[ChatMessage],
        current_message: ChatMessage,
        rag_context: str | None,
        token_budget: TokenBudget,
    ) -> list[Message]:
        """
        构建 LLM 对话上下文消息列表

        Context 结构：
        - system prompt
        - compaction_message（如果存在）
        - recent_messages
        - rag_context（如果存在）
        - current_message

        约束条件：
            - 确保构建的上下文在 token_budget.max_input_tokens 限制内
            - 确保 system_prompt, current_message 位于 context 中
            - recent_messages, rag_context, compaction_message 软优先级处理
            - rag_context 可截断，并且总比率不超过 token_budget.rag_context_ratio
            - recent_messages 优先保留靠近 current_message 的消息
            - recent_messages 占比基于 RAG context 是否存在调整：
                - RAG 内容不存在： recent_messages 最多占用 recent_max_ratio 比例的剩余空间，此时 compaction 被截断
                - RAG 内容存在： recent_messages 最多占用 rag_context_ratio 比例的剩余空间，此时 compaction 可以抛弃
            - compaction 可截断或丢弃
        """
        context_messages: list[Message] = []
        max_input_tokens = token_budget.max_input_tokens

        # 1. 计算 hard context, soft context
        system_tokens = self.token_counter.count_message(system_prompt)
        current_tokens = self.token_counter.count_message(current_message.message)

        hard_tokens = system_tokens + current_tokens
        soft_tokens = max(0, max_input_tokens - hard_tokens)

        # 2. 构建 RAG 内容
        rag_tokens = 0

        if rag_context:
            rag_context = self.token_counter.truncate_text(
                rag_context,
                int(max_input_tokens * token_budget.rag_context_ratio),
            )
            rag_tokens = self.token_counter.count_message(rag_context)

        # 3. 构建 recent_messages 内容
        remaining_after_rag = max(0, soft_tokens - rag_tokens)

        if rag_context:
            recent_max_tokens = min(
                remaining_after_rag,
                int(max_input_tokens * token_budget.rag_context_ratio),
            )
        else:
            recent_max_tokens = int(remaining_after_rag * token_budget.recent_max_ratio)

        selected_recent, recent_tokens = self._select_recent_messages(
            recent_messages=recent_messages,
            max_tokens=recent_max_tokens,
        )

        # 4. compaction 使用剩余空间
        remaining_after_recent = max(0, remaining_after_rag - recent_tokens)

        compaction_content: str | None = None
        if compaction_message and remaining_after_recent > 0:
            compaction_content = self.token_counter.truncate_text(
                compaction_message.message,
                max_tokens=remaining_after_recent,
            )

        # 5. 构建最终 context 消息列表
        context_messages.append(
            Message(
                role=ChatMessageRole.SYSTEM,
                content=system_prompt,
            )
        )

        if compaction_content:
            context_messages.append(
                Message(
                    role=ChatMessageRole.SYSTEM,
                    content=compaction_content,
                )
            )

        for msg in selected_recent:
            context_messages.append(
                Message(
                    role=msg.role,
                    content=msg.message,
                )
            )

        if rag_context:
            context_messages.append(
                Message(
                    role=ChatMessageRole.SYSTEM,
                    content=rag_context,
                )
            )

        context_messages.append(
            Message(
                role=current_message.role,
                content=current_message.message,
            )
        )

        return context_messages
