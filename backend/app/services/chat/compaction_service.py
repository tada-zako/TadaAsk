from typing import cast
from dataclasses import dataclass

from ..utils import TokenBudget
from app.providers import (
    TextCompleter,
    Message,
    SUMMARIZATION_PROMPT,
    UPDATE_SUMMARIZATION_PROMPT,
)
from app.crud import ChatMessageCRUD, ChatSessionCRUD
from app.db.models import ChatMessage, ModelProfile
from app.core.constants import ChatMessageRole, ChatMessageType
from app.utils import TokenCounter


@dataclass
class CompactionPlan:
    """Compaction 判断结果数据封装"""

    need_compaction: bool
    tail_start_sequence: int | None = None  # tail 消息的起始 sequence
    compact_until_sequence: int | None = (
        None  # 需要 compact 的消息的截止 sequence（包含该消息）
    )


class CompactionService:
    def __init__(
        self,
        chat_message_crud: ChatMessageCRUD,
        chat_session_crud: ChatSessionCRUD,
        text_completer: TextCompleter,
        token_counter: TokenCounter,
    ):
        self.chat_message_crud = chat_message_crud
        self.chat_session_crud = chat_session_crud
        self.text_completer = text_completer
        self.token_counter = token_counter

    def estimate_without_rag(
        self,
        *,
        system_prompt: str,
        compaction_message: ChatMessage | None,
        recent_messages: list[ChatMessage],
        current_message: ChatMessage,
        token_budget: TokenBudget,
    ) -> bool:
        """
        估算没有 RAG context block 情况下，上下文是否可能超出窗口限制

        计入计算的内容：
            - system prompt
            - compaction_message（如果存在）
            - recent_messages
            - current_message

        比较 total_tokens 与 max_input_tokens * compaction_trigger_ratio
        """
        system_tokens = self.token_counter.count_message(system_prompt)
        compaction_tokens = (
            self.token_counter.count_message(compaction_message.message)
            if compaction_message
            else 0
        )
        recent_tokens = sum(
            self.token_counter.count_message(message.message)
            for message in recent_messages
        )
        current_user_tokens = self.token_counter.count_message(current_message.message)

        total = system_tokens + compaction_tokens + recent_tokens + current_user_tokens

        trigger_tokens = int(
            token_budget.max_input_tokens * token_budget.compaction_trigger_ratio
        )

        return total >= trigger_tokens

    def plan_compaction(
        self,
        *,
        recent_messages: list[ChatMessage],
        token_budget: TokenBudget,
    ) -> CompactionPlan:
        """
        规划 compaction 策略

        1. 从 recent_messages 的最后一条消息开始，
            逐条向前计算累计 token 数量直到 used_tokens
            超过 token_budget.max_input_tokens * token_budget.recent_tail_keep_ratio
        2. 此时，如果 compact_until_sequence - 1 < 0，说明此时上下文过短，尚无法进行 compaction；
              否则，返回 compaction 计划，包含 tail_start_sequence 和 compact_until_sequence
        """
        tail_keep_tokens = int(
            token_budget.max_input_tokens * token_budget.recent_tail_keep_ratio
        )

        used_tokens = 0
        tail_start_sequence = None

        # 累计 recent_messages 的 token 数量，找到 tail_start_sequence
        for msg in reversed(recent_messages):
            msg_tokens = self.token_counter.count_message(msg.message)
            if used_tokens + msg_tokens > tail_keep_tokens:
                break

            used_tokens += msg_tokens
            tail_start_sequence = msg.sequence

        if tail_start_sequence is None:
            return CompactionPlan(need_compaction=False)

        compact_until_sequence = tail_start_sequence - 1
        if compact_until_sequence <= 0:
            return CompactionPlan(need_compaction=False)

        return CompactionPlan(
            need_compaction=True,
            tail_start_sequence=tail_start_sequence,
            compact_until_sequence=compact_until_sequence,
        )

    def _build_compaction_input(
        self,
        *,
        old_compaction_message: ChatMessage | None,
        compactable_messages: list[ChatMessage],
    ) -> str:
        """
        构建 compaction 输入文本
        """
        blocks: list[str] = []

        # 压入上一次的 compaction 消息
        if old_compaction_message:
            blocks.append(
                "[Previous Compaction]\n"
                f"{old_compaction_message.message}\n"
                "[/Previous Compaction]"
            )

        lines = []
        for message in compactable_messages:
            lines.append(f"{message.role.value}: {message.message}")

        blocks.append(
            "[Messages To Compact]\n" + "\n".join(lines) + "\n[/Messages To Compact]"
        )

        return "\n\n".join(blocks)

    async def compact(
        self,
        *,
        chat_session_id: int,
        recent_messages: list[ChatMessage],
        old_compaction_message: ChatMessage | None,
        text_completer: TextCompleter,
        model_profile: ModelProfile,
        token_budget: TokenBudget,
    ) -> ChatMessage:
        """
        执行 compaction 操作

        1. 规划 compaction 策略，获取 CompactionPlan
        2. 如果需要 compaction，则调用 TextCompleter 进行文本生成，生成新的 compaction 消息内容
        3. 将新的 compaction 消息保存到数据库，并返回该消息实例
        """
        plan = self.plan_compaction(
            recent_messages=recent_messages,
            token_budget=token_budget,
        )
        if not plan.need_compaction:
            raise ValueError("Compaction is not needed.")

        # 获取需要 compact 的消息列表
        compact_until_sequence = cast(int, plan.compact_until_sequence)
        compactable_messages = [
            msg for msg in recent_messages if msg.sequence <= compact_until_sequence
        ]

        # 构建 compaction 输入文本
        summary_input = self._build_compaction_input(
            old_compaction_message=old_compaction_message,
            compactable_messages=compactable_messages,
        )

        # 调用 TextCompleter 进行文本生成，获取新的 compaction 消息内容
        system_prompt = (
            UPDATE_SUMMARIZATION_PROMPT
            if old_compaction_message
            else SUMMARIZATION_PROMPT
        )
        new_compaction_content = await self.text_completer.chat(
            messages=[
                Message(role=ChatMessageRole.SYSTEM, content=system_prompt),
                Message(role=ChatMessageRole.USER, content=summary_input),
            ]
        )

        # 保存新的 compaction 消息到数据库
        return await self.chat_message_crud.append_message(
            chat_session_id=chat_session_id,
            role=ChatMessageRole.SYSTEM,
            message=new_compaction_content,
            type=ChatMessageType.COMPACTION,
            provider=model_profile.provider,
            model=model_profile.model,
            tail_start_sequence=plan.tail_start_sequence,
        )
