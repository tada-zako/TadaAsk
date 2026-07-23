from typing import (
    Any,
    TYPE_CHECKING,
    Protocol,
    runtime_checkable,
    AsyncIterator,
    TypeVar,
    Literal,
)
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import ChatMessageRole

if TYPE_CHECKING:
    # 避免循环导入
    from app.api.schemas import AdminChatRequest
    from app.db.schemas import ModelProfileRead
    from app.db.models import ProjectSettings


# LLM 思考等级定义
type ThinkingEffort = Literal["minimal", "low", "medium", "high", "xhigh", "max"]
type ThinkingLevel = bool | ThinkingEffort

# LLM 响应状态定义
type ModelResponseState = Literal["complete", "incomplete", "interrupted"]


def _now_utc() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(tz=timezone.utc)


@dataclass
class Message:
    role: ChatMessageRole
    content: str


@dataclass
class TokenUsage:
    """
    Token 用量封装结构。

    - input_tokens: 本次请求发送给模型的输入 token 数。
    - cache_write_tokens: 本次请求写入 provider 缓存的 token 数。
    - cache_read_tokens: 本次请求从 provider 缓存命中的输入 token 数。
    - output_tokens: 返回给业务层的可见模型输出 token 数。
    - reasoning_tokens: 模型内部推理/思考消耗的 token 数，不应重复计入 output_tokens。
    - raw_usage: provider SDK 返回的原始 usage 对象，供排查 provider 差异时使用。
    """

    input_tokens: int = 0

    cache_write_tokens: int = 0
    cache_read_tokens: int = 0

    output_tokens: int = 0

    reasoning_tokens: int = 0
    raw_usage: Any | None = None

    @property
    def total_tokens(self) -> int:
        """总 token 用量"""
        return self.input_tokens + self.output_tokens + self.reasoning_tokens


@dataclass
class ModelSettings:
    """
    LLM API 请求参数配置
    """

    max_tokens: int
    """
    最大生成 token

    Supported by:

    * Gemini
    * Anthropic
    * OpenAI
    * Groq
    * Cohere
    * Mistral
    * Bedrock
    * MCP Sampling
    * Outlines (all providers)
    * xAI
    """

    temperature: float
    """Amount of randomness injected into the response.

    Use `temperature` closer to `0.0` for analytical / multiple choice, and closer to a model's
    maximum `temperature` for creative and generative tasks.

    Note that even with `temperature` of `0.0`, the results will not be fully deterministic.

    Supported by:

    * Gemini
    * Anthropic
    * OpenAI
    * Groq
    * Cohere
    * Mistral
    * Bedrock
    * Outlines (Transformers, LlamaCpp, SgLang, VLLMOffline)
    * xAI
    """

    top_p: float
    """An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass.

    So 0.1 means only the tokens comprising the top 10% probability mass are considered.

    You should either alter `temperature` or `top_p`, but not both.

    Supported by:

    * Gemini
    * Anthropic
    * OpenAI
    * Groq
    * Cohere
    * Mistral
    * Bedrock
    * Outlines (Transformers, LlamaCpp, SgLang, VLLMOffline)
    * xAI
    """

    timeout: float
    """Override the client-level default timeout for a request, in seconds.

    Supported by:

    * Gemini
    * Anthropic
    * OpenAI
    * Groq
    * Mistral
    * xAI
    """

    thinking: ThinkingLevel
    """Enable or configure thinking/reasoning for the model.

    - `True`: Enable thinking with the provider's default effort level.
    - `False`: Disable thinking (silently ignored if the model always thinks).
    - `'minimal'`/`'low'`/`'medium'`/`'high'`/`'xhigh'`/`'max'`: Enable thinking at a specific effort level.

    When omitted, the model uses its default behavior (which may include thinking
    for reasoning models).

    Provider-specific thinking settings (e.g., `anthropic_thinking`,
    `openai_reasoning_effort`) take precedence over this unified field.

    Supported by:

    * Anthropic
    * OpenAI
    * Gemini
    * Groq
    * Bedrock
    * OpenRouter
    * Cerebras
    * xAI
    """

    @classmethod
    def for_admin_chat(
        cls,
        *,
        profile: "ModelProfileRead",
        request: "AdminChatRequest | None" = None,
    ) -> "ModelSettings":
        """
        Admin Chat 的模型配置入口。

        Admin 允许请求级字段覆盖全局默认值；max_tokens 仍以模型配置为准。
        """
        temperature = settings.llm_default_temperature
        top_p = settings.llm_default_top_p
        thinking = settings.llm_default_thinking

        if request:
            if request.temperature is not None:
                temperature = request.temperature
            if request.top_p is not None:
                top_p = request.top_p
            thinking = request.thinking

        return cls(
            max_tokens=int(
                profile.max_output_tokens or settings.llm_default_max_output_tokens
            ),
            temperature=float(temperature),
            top_p=float(top_p),
            timeout=float(settings.llm_default_timeout),
            thinking=thinking,
        )

    @classmethod
    def for_visitor_chat(
        cls,
        *,
        profile: "ModelProfileRead",
        project_settings: "ProjectSettings",
    ) -> "ModelSettings":
        """
        Visitor Chat 的模型配置入口。

        Visitor 不接受请求级模型参数，只使用 project setting 和最基础的后端兜底。
        """
        max_tokens = (
            project_settings.visitor_max_output_tokens
            if project_settings.visitor_max_output_tokens
            else profile.max_output_tokens or settings.llm_default_max_output_tokens
        )
        temperature = (
            project_settings.visitor_temperature
            if project_settings.visitor_temperature is not None
            else settings.llm_default_temperature
        )
        top_p = (
            project_settings.visitor_top_p
            if project_settings.visitor_top_p is not None
            else settings.llm_default_top_p
        )
        timeout = (
            project_settings.visitor_timeout
            if project_settings.visitor_timeout is not None
            else settings.llm_default_timeout
        )
        thinking = (
            project_settings.visitor_thinking
            if project_settings.visitor_thinking is not None
            else settings.llm_default_thinking
        )

        return cls(
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            timeout=float(timeout),
            thinking=thinking,  # type: ignore
        )

    @classmethod
    def for_compaction(cls, *, max_tokens: int = 2048) -> "ModelSettings":
        """会话压缩摘要：忠实、稳定、结构化，避免使用用户的回答偏好。"""
        return cls(
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=1.0,
            timeout=60.0,
            thinking=False,
        )

    @classmethod
    def for_query_expansion(cls) -> "ModelSettings":
        """查询扩展：低发散度，生成短 JSON 和一段 HyDE 文本。"""
        return cls(
            max_tokens=768,
            temperature=0.2,
            top_p=1.0,
            timeout=30.0,
            thinking=False,
        )

    @classmethod
    def for_standalone_rewrite(cls) -> "ModelSettings":
        """独立查询改写：确定性优先，只产出短检索 query。"""
        return cls(
            max_tokens=256,
            temperature=0.0,
            top_p=1.0,
            timeout=20.0,
            thinking=False,
        )

    @classmethod
    def for_title_generation(cls) -> "ModelSettings":
        """会话标题生成：短输出、低发散度、失败时业务层可静默降级。"""
        return cls(
            max_tokens=64,
            temperature=0.2,
            top_p=1.0,
            timeout=10.0,
            thinking=False,
        )


@dataclass
class ModelResponse:
    """
    LLM SDK 异步响应结果封装（非流式）
    """

    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    state: ModelResponseState = "complete"


class StreamedResponse(ABC):
    """
    LLM SDK 流式响应接口的返回类型：将 AsyncIterator 封装在类中，方
    便业务层调用以及方便未来扩展 LLM 调用的其它信息记录（例如 token 使用量、调用时长等）
    """

    def __init__(self):
        self._stream_iter: AsyncIterator[str] | None = None
        self._cancelled: bool = False

        self._usage: TokenUsage = TokenUsage()
        self._text_buffer: list[str] = []

    def __aiter__(self):
        if self._stream_iter is None:
            # 由子类决定内部迭代器如何实现
            self._stream_iter = self._get_stream_iter()
        return self._stream_iter

    @property
    def text(self) -> str:
        """返回 buffer 中已经生成的文本内容"""
        return "".join(self._text_buffer)

    @property
    def usage(self) -> TokenUsage:
        """返回当前的 token 用量统计信息"""
        return self._usage

    @abstractmethod
    async def _get_stream_iter(self) -> AsyncIterator[str]:
        """
        获取流式响应的异步生成器
        具体实现由子类完成，封装具体 LLM 的流式响应接口
        """
        raise NotImplementedError()
        yield

    async def cancel(self) -> None:
        """
        取消流式响应输出；确保底层 client 连接正确关闭
        """
        if self._cancelled:
            return
        self._cancelled = True
        await self.close_stream()

    async def close_stream(self) -> None:
        """
        关闭底层流式连接，释放资源
        具体实现由子类完成，封装具体 LLM 的流式响应接口的连接关闭逻辑
        """
        raise NotImplementedError()

    def get(self) -> ModelResponse:
        """流式调用完成或中断后，将完整内容和 token 用量封装成 ModelResponse 对象返回"""
        if self._cancelled:
            state: ModelResponseState = "interrupted"
        # TODO: 暂不设置 "incomplete"
        else:
            state = "complete"

        return ModelResponse(
            text=self.text,
            usage=self.usage,
            state=state,
        )


@runtime_checkable
class TextCompleter(Protocol):
    """流式文本生成"""

    async def chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
    ) -> ModelResponse:
        """
        LLM 文本生成接口：通过对具体 LLM 的封装，提供简洁的文本生成接口，
        返回一个 ModelResponse 对象，包含生成文本内容和 token 用量等信息
        """
        raise NotImplementedError()

    @asynccontextmanager
    async def stream_chat(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
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

    @property
    def provider_name(self) -> str:
        """返回模型所属的 provider 名称，供业务层记录日志等使用"""
        raise NotImplementedError()


T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class StructuredCompleter(Protocol):
    """结构化输出"""

    async def complete_structured(
        self,
        *,
        messages: list[Message],
        model_settings: ModelSettings,
        schema: type[T],
    ) -> T:
        """
        LLM 结构化输出接口：按照指定的 Pydantic 模型 schema 对 LLM 输出进行解析和校验，
        返回一个符合 schema 定义的 Pydantic 模型实例
        """
        raise NotImplementedError()

    @property
    def model_name(self) -> str:
        """返回模型名称，供业务层记录日志等使用"""
        raise NotImplementedError()

    @property
    def provider_name(self) -> str:
        """返回模型所属的 provider 名称，供业务层记录日志等使用"""
        raise NotImplementedError()
