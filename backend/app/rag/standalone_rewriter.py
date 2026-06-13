from pydantic import BaseModel, Field

from app.providers import (
    StructuredCompleter,
    Message,
    ModelSettings,
    STANDALONE_QUERY_REWRITE_PROMPT,
)
from app.core.constants import ChatMessageRole


class StandaloneQueryOutput(BaseModel):
    query: str = Field(..., description="Standalone search query")


class StandaloneQueryRewriter:
    """
    独立的查询改写器；附带会话上下文对用户查询进行改写
    """

    def __init__(self, completer: StructuredCompleter):
        self._completer = completer

    async def rewrite(self, query: str, standalone_context: list[Message]) -> str:
        """
        根据用户查询和最近的对话消息，生成改写后的查询文本。

        TODO: 后续增加上下文大小限制，限制用于改写的上下文最大 token 量
        """
        # 格式化对话历史
        history_text = self._format_history(standalone_context)

        # 构建提示词消息列表
        messages = [
            Message(
                role=ChatMessageRole.SYSTEM,
                content=STANDALONE_QUERY_REWRITE_PROMPT,
            ),
            Message(
                role=ChatMessageRole.USER,
                content=f"Conversation history:\n{history_text}\n\n"
                f"Latest user question:\n{query}",
            ),
        ]

        # 添加用户当前的查询作为最后一条消息
        messages.append(Message(role=ChatMessageRole.USER, content=query))

        # 调用 completer 生成改写后的查询
        rewritten_query = await self._completer.complete_structured(
            messages=messages,
            model_settings=ModelSettings.for_standalone_rewrite(),
            schema=StandaloneQueryOutput,
        )
        return rewritten_query.query.strip() or query.strip()

    def _format_history(self, messages: list[Message]) -> str:
        """格式化历史对话内容；避免 LLM 将历史消息误判为上下文对话记录"""
        lines = []
        for msg in messages:
            if msg.role in (ChatMessageRole.USER, ChatMessageRole.ASSISTANT):
                lines.append(f"{msg.role.value}: {msg.content}")
            elif msg.role == ChatMessageRole.SYSTEM:
                # Compaction 消息
                lines.append(f"[Compaction]: {msg.content}")
        return "\n".join(lines)
