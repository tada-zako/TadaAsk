from typing import Protocol, runtime_checkable, TypeVar, Generic, AsyncIterator
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass

from app.rag import VectorQueryItem
from app.db.schemas import ChatMessageInternal

T = TypeVar("T")


@dataclass
class ModelRequestContext(Generic[T]):
    system_prompt: str
    user_message: str
    chat_history: list[T] | None = None


class StreamedResponse(ABC):
    """
    LLM SDK 流式响应接口的返回类型：将 AsyncIterator 封装在类中，方
    便业务层调用以及方便未来扩展 LLM 调用的其它信息记录（例如 token 使用量、调用时长等）
    """

    def __init__(self):
        self._stream_iter: AsyncIterator[str] | None = None

    def __aiter__(self):
        if self._stream_iter is None:
            # 由子类决定内部迭代器如何实现
            self._stream_iter = self._get_stream_iter()
        return self._stream_iter

    @abstractmethod
    async def _get_stream_iter(self) -> AsyncIterator[str]:
        """
        获取流式响应的异步生成器
        具体实现由子类完成，封装具体 LLM 的流式响应接口
        """
        raise NotImplementedError()
        yield


@runtime_checkable
class Model(Protocol, Generic[T]):
    def construct_messages(
        self,
        document: list[VectorQueryItem],
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
    @asynccontextmanager
    async def stream_chat(
        self, context: ModelRequestContext[T]
    ) -> AsyncIterator[StreamedResponse]:
        """
        LLM 流式对话接口：通过对具体 LLM 的封装，提供简洁的流式对话接口，
        返回一个 StreamedResponse 对象，供业务层异步迭代获取流式响应内容
        """
        raise NotImplementedError()
        yield

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        raise NotImplementedError()
