import re

from .generation_registry import GenerationRegistry
from app.crud import ChatMessageCRUD, ChatSessionCRUD
from app.db.models import ChatSession, ChatMessage
from app.db.schemas import ChatMessageInternal, ChatSessionInternal, RAGSnapshot
from app.core.exceptions import GenerationScopeError

# fork session 后缀正则
_FORK_SUFFIX_RE = re.compile(r"\(fork #(\d+)\)$")


class ChatSessionOpsService:
    """对话操作服务；包括对 chat_message 的回退/分支操作"""

    def __init__(
        self,
        *,
        chat_session_crud: ChatSessionCRUD,
        chat_message_crud: ChatMessageCRUD,
        generation_registry: GenerationRegistry,
    ):
        self.chat_session_crud = chat_session_crud
        self.chat_message_crud = chat_message_crud
        self.generation_registry = generation_registry

    @staticmethod
    def _generate_forked_session_title(original_title: str) -> str:
        """
        生成分叉对话的标题

        生成策略：
            - 末尾追加 " (fork #n)" 后缀，n 从 1 开始递增
            - 如果 original_title 末尾已经有类似后缀，则在原有数字基础上递增 n
        """
        # 检查后缀
        match = _FORK_SUFFIX_RE.search(original_title)

        if match:
            # 已有后缀，提取数字并递增
            n = int(match.group(1)) + 1
            base_title = original_title[: match.start()].rstrip()
            return f"{base_title} (fork #{n})"

        return f"{original_title} (fork #1)"

    async def fork_session(
        self,
        *,
        source_session: ChatSession,
        target_msg_sequence: int,
    ) -> ChatSession:
        """对话分支操作"""

        # 创建新的 chat_session 对象
        new_session = await self.chat_session_crud.create_chat_session(
            ChatSessionInternal(
                project_id=source_session.project_id,
                owner_type=source_session.owner_type,
                visitor_id=source_session.visitor_id,
                title=self._generate_forked_session_title(source_session.title),
                provider=source_session.provider,
                model=source_session.model,
            )
        )

        # 需要需要复制的 messages
        source_messages = await self.chat_message_crud.list_messages_until_sequence(
            chat_session_id=source_session.id,
            target_sequence=target_msg_sequence,
        )

        # 源消息 sequence -> index 映射
        sequence_index_map = {
            msg.sequence: idx for idx, msg in enumerate(source_messages, start=1)
        }

        # 创建新的 messages internal 对象列表；预备批量插入
        rows = []
        for index, msg in enumerate(source_messages, start=1):
            tail_start_sequence = None
            if msg.tail_start_sequence is not None:
                tail_start_sequence = sequence_index_map.get(msg.sequence, index)

            new_message = ChatMessageInternal(
                chat_session_id=new_session.id,
                sequence=index,
                role=msg.role,
                message=msg.message,
                type=msg.type,
                provider=msg.provider,
                model=msg.model,
                tail_start_sequence=tail_start_sequence,
                rag_snapshot=RAGSnapshot.model_validate(msg.rag_snapshot)
                if msg.rag_snapshot
                else None,
            )
            rows.append(new_message)

        if rows:
            await self.chat_message_crud.bulk_add_messages(messages_data=rows)

        return new_session

    async def revert_session(
        self,
        *,
        chat_session: ChatSession,
        message: ChatMessage,
    ) -> int:
        """
        对话回退操作；
        删除指定 sequence 及之后的消息，并返回删除的消息数量
        NOTE: 目前回退操作只是删除消息，有较大风险
        """
        deleted_count = await self.chat_message_crud.delete_messages_after_sequence(
            chat_session_id=chat_session.id,
            target_sequence=message.sequence,
        )
        return deleted_count

    def cancel_generation(
        self,
        *,
        chat_session: ChatSession,
        generation_uid: str,
    ) -> bool:
        """取消属于当前 session 的活跃 generation；不存在时幂等返回 False。"""
        generation = self.generation_registry.get(generation_uid)
        if not generation:
            return False

        if generation.session_uid != chat_session.uid:
            # 确保请求的 generation 属于当前 session
            raise GenerationScopeError("Generation not found")

        return self.generation_registry.cancel(generation_uid)
