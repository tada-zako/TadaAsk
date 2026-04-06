from typing import Protocol, runtime_checkable, AsyncGenerator, TypeVar, Generic
from dataclasses import dataclass

from app.db.schemas import ChatMessageInternal

T = TypeVar("T")


@dataclass
class ModelRequestContext(Generic[T]):
    system_prompt: str
    user_message: str
    chat_history: list[T] | None = None


@runtime_checkable
class Model(Protocol, Generic[T]):
    def construct_messages(
        self,
        document: list,
        user_message: str,
        chat_history: list[ChatMessageInternal] | None = None,
    ) -> ModelRequestContext[T]:
        """
        构建符合 LLM 请求接口格式的消息实例

        Args:
            document: 向量库查询返回的相关文档列表，允许为空
            user_message: 用户输入的消息内容
            chat_history: 线程历史消息列表（可选）

        Returns:
            构建好的消息实例，包含系统提示语、用户消息和历史消息
        """
        ...

    # TODO: 参考 AgentResponse 的实现，封装流式响应接口，对外提供更加安全的流式响应接口
    def stream_chat(self, context: ModelRequestContext[T]) -> AsyncGenerator[str, None]:
        """
        LLM 流式对话接口
        通过对具体 LLM 的封装，提供简洁的流式对话接口
        """
        ...
