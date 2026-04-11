from dataclasses import dataclass

from pydantic_ai import (
    Agent,
    RunContext,
    ModelRetry,
    FunctionToolset,
)
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.providers.prompts import DEFAULT_SYSTEM_PROMPT
from app.services.thread import ChatThreadService
from app.services.rag import RAGService


@dataclass
class AgentDeps:
    db_session: AsyncSession
    context_provider: ChatThreadService
    rag_provider: RAGService
    thread_uid: str
    collection_uid: (
        str | None
    )  # 允许为空，NOTE: 需要告知 Agent 此时不能使用 rag_search 工具


agent = Agent(
    # "google-gla:gemini-2.5-flash",  不设置模型模型配置，避免缺少 API_KEY 时无法实例化 Agent
    deps_type=AgentDeps,
    system_prompt=DEFAULT_SYSTEM_PROMPT,
    # capabilities=[WebSearch()],   # pydantic_ai v1.77 issue: google 的模型不能同时指定 bulid-in 工具和 function 工具
)


# @agent.tool(retries=2)    # 静态工具不方便根据不同模型进行调整，改为在 agent.run() 时动态指定 toolsets
async def rag_search(ctx: RunContext[AgentDeps], query: str, top_k: int = 5) -> str:
    """
    Agent 工具：执行 RAG 检索，返回相关文档内容

    Args:
        ctx: Agent 运行上下文，包含 AgentDeps 定义的依赖项
        query: 用户查询文本
        top_k: 返回的相关文档数量，默认为 5

    Returns:
        与 query 相关的文档内容字符串，格式化后返回给 Agent 进行后续处理
    """

    if not ctx.deps.collection_uid:
        logger.warning(
            "Agent 请求执行 RAG 检索，但 collection_uid 为空，无法执行检索工具"
        )
        return (
            "Current session does not support RAG retrieval. "
            "Please inform the user that RAG retrieval is unavailable, "
            "or proceed without using the RAG tool."
        )

    logger.info(f"Agent 调用 RAG 检索工具，查询文本：{query[:50]}，top_k={top_k}")
    docs = await ctx.deps.rag_provider.get_related_documents(
        ctx.deps.db_session,
        collection_uid=ctx.deps.collection_uid,
        query_text=query,
        top_k=top_k,
    )

    if not docs:
        logger.debug("RAG 检索未返回相关文档，将执行重试")
        raise ModelRetry(
            "RAG search did not return any relevant documents. Please try a different query or use another tool."
        )

    # 格式化相关文档内容
    formatted_content = "RAG 检索结果：\n<Context>\n"
    for doc in docs:
        formatted_content += (
            f"[context{doc.id}]:\n{doc.document}\n" + f"Metadata: {doc.metadata}\n\n"
        )
    return formatted_content + "</Context>\n"


extra_toolset = FunctionToolset(tools=[rag_search])
