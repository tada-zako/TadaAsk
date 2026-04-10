from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入的消息文本")
    doc_top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="RAG 检索相关文档的数量",
    )

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
    )


class AgentRequest(ChatRequest):
    # 额外字段，指定 Agent 运行支持的功能
    mode: Literal["rag_search", "web_search"] = Field(
        default="rag_search",
        description="Agent 运行模式，决定使用哪个工具集，目前支持 'rag_search' 和 'web_search'",
    )
