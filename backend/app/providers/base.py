from typing import Protocol, runtime_checkable, Literal, AsyncIterator, TypeVar
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


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
class TextCompleter(Protocol):
    """流式文本生成"""

    @asynccontextmanager
    async def stream_chat(
        self, messages: list[Message]
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


T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class StructuredCompleter(Protocol):
    """结构化输出"""

    async def complete_structured(self, messages: list[Message], schema: type[T]) -> T:
        """
        LLM 结构化输出接口：按照指定的 Pydantic 模型 schema 对 LLM 输出进行解析和校验，
        返回一个符合 schema 定义的 Pydantic 模型实例
        """
        raise NotImplementedError()
        yield

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        raise NotImplementedError()
