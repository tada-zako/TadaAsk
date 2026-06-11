import asyncio
from dataclasses import dataclass
import uuid


@dataclass
class ActiveGeneration:
    """LLM 生成对象；用于管理 LLM 输出的连接"""

    generation_uid: str
    session_uid: str
    message_uid: str | None
    cancel_event: asyncio.Event


class GenerationRegistry:
    """LLM 生成对象注册器；用于跟踪和管理活跃的 LLM 生成对象"""

    def __init__(self):
        self._registry: dict[str, ActiveGeneration] = {}

    def register(
        self,
        *,
        session_uid: str,
        message_uid: str | None = None,
    ) -> ActiveGeneration:
        """注册新的 LLM 生成对象"""
        generation = ActiveGeneration(
            generation_uid=str(uuid.uuid4()),
            session_uid=session_uid,
            message_uid=message_uid,
            cancel_event=asyncio.Event(),
        )

        self._registry[generation.generation_uid] = generation
        return generation

    def cancel(self, generation_uid: str) -> bool:
        """设置取消事件；用于通知 LLM 异步生成器取消生成"""
        generation = self._registry.get(generation_uid)
        if not generation:
            return False

        generation.cancel_event.set()
        return True

    def is_cancelled(self, generation_uid: str) -> bool:
        """检查 cancel 信号是否被设置"""
        generation = self._registry.get(generation_uid)
        return bool(generation and generation.cancel_event.is_set())

    def unregister(self, generation_uid: str) -> None:
        """移除 LLM 生成对象"""
        self._registry.pop(generation_uid, None)
