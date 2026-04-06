from typing import Protocol, runtime_checkable, AsyncGenerator, AsyncIterator, Literal
from contextlib import asynccontextmanager

from pydantic_ai import ModelMessage, WebSearchTool
from pydantic_ai.models import Model as AgentModel

from .agent import agent, AgentDeps, extra_toolset


class AgentResponse:
    def __init__(self, stream: AsyncIterator[str]):
        self._stream = stream
        self._buffer = []

    async def text_chunks(self) -> AsyncGenerator[str, None]:
        async for chunk in self._stream:
            self._buffer.append(chunk)
            yield chunk

    async def full_text(self) -> str:
        if not self._buffer:
            async for chunk in self._stream:
                self._buffer.append(chunk)
        return "".join(self._buffer)


@runtime_checkable
class AgentExecutor(Protocol):
    @asynccontextmanager
    async def run(
        self,
        user_message: str,
        *,
        deps: AgentDeps,
        message_history: list[ModelMessage],
        model: AgentModel,
    ) -> AsyncIterator[AgentResponse]:
        """
        执行 Agent 对话逻辑，返回一个异步生成器，用于逐步获取 Agent 回复内容

        Args:
            user_message: 当前用户输入的消息文本
            deps: AgentDeps 实例，包含 Agent 运行所需的依赖项
            message_history: Agent 对话历史消息列表，用于提供上下文
            model: AgentModel 实例，指定 Agent 使用的语言模型

        Returns:
            AsyncIterator，逐步返回 AgentResponse 实例，包含原始流式回复接口和缓冲区管理
        """
        raise NotImplementedError(
            "AgentExecutor subclasses must implement the run method."
        )
        yield  # pragma: no cover


class AgentExecutorRegistry:
    _registry: dict[str, AgentExecutor] = {}

    @classmethod
    def register(cls, executor_type: str):
        def wrapper(executor_cls: type[AgentExecutor]):
            cls._registry[executor_type] = executor_cls()
            return executor_cls

        return wrapper

    @classmethod
    def get_executor(
        cls, executor_type: Literal["rag_search", "web_search"]
    ) -> AgentExecutor:
        if executor_type not in cls._registry:
            raise ValueError(f"Agent executor '{executor_type}' is not registered.")
        return cls._registry[executor_type]


@AgentExecutorRegistry.register("rag_search")
class RAGAgentExecutor(AgentExecutor):
    @asynccontextmanager
    async def run(
        self,
        user_message: str,
        *,
        deps: AgentDeps,
        message_history: list[ModelMessage],
        model: AgentModel,
    ) -> AsyncIterator[AgentResponse]:
        """
        配置 RAG 检索工具的 Agent 执行器

        Args:
            user_message: 当前用户输入的消息文本
            deps: RAGSearchDeps 实例，包含 Agent 运行所需的依赖项
            message_history: Agent 对话历史消息列表，用于提供上下文
            model: AgentModel 实例，指定 Agent 使用的语言模型

        Returns:
            返回封装后的 AgentResponse 实例，包含原始流式回复接口和缓冲区管理
        """
        async with agent.run_stream(
            user_message,
            deps=deps,
            message_history=message_history,
            model=model,
            toolsets=[extra_toolset],
        ) as result:
            raw_stream = result.stream_text(delta=True)
            agent_response = AgentResponse(raw_stream)

            try:
                yield agent_response
            finally:
                pass  # 这里可以添加一些清理逻辑，但是目前不清楚具体如何清理


@AgentExecutorRegistry.register("web_search")
class WebSearchAgentExecutor(
    AgentExecutor
):  # TODO: 这里的策略模式实现，说实话我不是很满意，由于注册器对于类型判断的限制，
    # 这里不得不直接继承 AgentExecutor，后续如果有更好的实现方式，可以考虑重构这里的设计
    @asynccontextmanager
    async def run(
        self,
        user_message: str,
        *,
        deps: AgentDeps,
        message_history: list[ModelMessage],
        model: AgentModel,
    ) -> AsyncIterator[AgentResponse]:
        """
        配置 WebSearch 工具的 Agent 执行器

        Args:
            user_message: 当前用户输入的消息文本
            deps: AgentDeps 实例，包含 Agent 运行所需的依赖项
            message_history: Agent 对话历史消息列表，用于提供上下文
            model: AgentModel 实例，指定 Agent 使用的语言模型

        Returns:
            返回封装后的 AgentResponse 实例，包含原始流式回复接口和缓冲区管理
        """
        async with agent.run_stream(
            user_message,
            deps=deps,
            message_history=message_history,
            model=model,
            builtin_tools=[WebSearchTool()],
        ) as result:
            raw_stream = result.stream_text(delta=True)
            agent_response = AgentResponse(raw_stream)

            try:
                yield agent_response
            finally:
                pass
