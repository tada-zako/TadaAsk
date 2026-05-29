from typing import Literal

import pathlib
from loguru import logger

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 后端项目根路径，指向 backend/ 目录
PROJECT_ROOT = pathlib.Path(__file__).parents[2]

# 类型别名
type EmbeddingBackend = Literal["fastembed", "llamacpp"]  # 文本嵌入后端
type RerankBackend = Literal["fastembed", "llamacpp"]  # Rerank 后端


class Settings(BaseSettings):
    project_root: str = str(PROJECT_ROOT)

    # =======================================
    # LLM 配置
    # =======================================

    llm_provider_admin: str = "google"  # Admin LLM 提供商
    llm_provider_visitor: str = "deepseek"  # Visitor LLM 提供商

    # Gemini LLM 配置
    gemini_api_key: str = ""
    gemini_model_perf: str = "gemini-2.5-flash"

    # DeepSeek LLM 配置
    deepseek_api_key: str = ""
    deepseek_model_perf: str = "DeepSeek-V4-Flash"

    sql_history_fetch_limit: int = 100  # 数据库中获取的历史消息数量上限
    max_context_tokens: int = 12000  # LLM 输入的最大上下文 token 长度，只包含历史对话
    max_single_message_tokens: int = 2048  # 最大单条消息 token 长度，只约束历史消息

    # =======================================
    # RAG 相关配置
    # =======================================

    embedding_backend: EmbeddingBackend = "fastembed"  # 文本嵌入后端
    rerank_backend: RerankBackend = "fastembed"  # Rerank 后端
    hyde_enabled: bool = False  # 是否启用 HyDE 生成虚拟文档增强检索，默认为 False

    embedding_model_name: str = ""  # 文本嵌入模型名称，默认由具体嵌入实现内部处理
    rerank_model_name: str = ""  # Rerank 模型名称，默认由具体实现内部处理

    chunk_size_tokens: int = 1000  # 文本块的目标 token 长度
    chunk_overlap_tokens: int = 0  # 文本块之间的重叠 token 数量
    chunk_window_tokens: int = (
        200  # 文本块窗口大小，优先在窗口范围内寻找切割点，默认为 200 tokens
    )

    chunk_size_chars: int = 0  # 文本块的目标字符长度，默认值为 token 长度的 4 倍
    chunk_overlap_chars: int = 0
    chunk_window_chars: int = 0

    # =======================================
    # 系统配置
    # =======================================

    vector_store_perf: str = "chromadb"  # 向量库配置

    # 模型缓存路径
    fastembed_model_path: str = ""  # FastEmbed 模型路径
    llamacpp_model_path: str = ""  # LLaMA.cpp 模型路径
    hf_hub_cache: str = ""  # HuggingFace Hub 模型缓存路径

    chromadb_path: str = ""  # ChromaDB 数据库文件存储路径
    sqlite_path: str = ""  # SQLite 数据库文件存储路径

    # =======================================
    # 权限配置
    # =======================================

    # JWT 配置
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # 管理员账号配置
    admin_username: str = "admin"
    admin_password: str = "admin123"

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env")

    # ================================
    # 验证逻辑
    # ================================
    @model_validator(mode="after")
    def compute_chunk_defaults(self) -> "Settings":
        """计算文本切割相关的默认值，并进行合法性检查"""
        # 未显式设置常量时，内部计算结果
        if self.chunk_overlap_tokens == 0:
            self.chunk_overlap_tokens = int(self.chunk_size_tokens * 0.15)

        # 假设平均每个 token 约为 4 个字符
        if self.chunk_overlap_chars == 0:
            self.chunk_overlap_chars = self.chunk_overlap_tokens * 4
        if self.chunk_window_chars == 0:
            self.chunk_window_chars = self.chunk_window_tokens * 4
        if self.chunk_size_chars == 0:
            self.chunk_size_chars = self.chunk_size_tokens * 4

        # 确保配置合法
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError(
                f"Overlap tokens ({self.chunk_overlap_tokens}) must be less than chunk size tokens "
                f"({self.chunk_size_tokens})"
            )
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError(
                f"Overlap chars ({self.chunk_overlap_chars}) must be less than chunk size chars "
                f"({self.chunk_size_chars})"
            )

        if self.chunk_window_tokens >= self.chunk_size_tokens:
            logger.warning(
                "Window size is larger than chunk size, checking if this is intentional."
            )

        return self

    @model_validator(mode="after")
    def validate_model_paths(self) -> "Settings":
        """验证模型路径配置是否存在"""
        # 验证 FastEmbed 模型路径是否存在（如果使用 fastembed 作为嵌入后端）
        if self.embedding_backend == "fastembed" and self.fastembed_model_path:
            if not pathlib.Path(self.fastembed_model_path).exists():
                raise ValueError(
                    f"FastEmbed model path does not exist: {self.fastembed_model_path}"
                )
        # 验证 LLaMA.cpp 模型路径是否存在（如果使用 llamacpp 作为 LLM 后端）
        if self.llm_provider_admin == "llamacpp" and self.llamacpp_model_path:
            if not pathlib.Path(self.llamacpp_model_path).exists():
                raise ValueError(
                    f"LLaMA.cpp model path does not exist: {self.llamacpp_model_path}"
                )

        return self


settings = Settings()
