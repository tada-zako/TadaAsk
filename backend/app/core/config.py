import pathlib
from loguru import logger

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 后端项目根路径，指向 backend/ 目录
PROJECT_ROOT = pathlib.Path(__file__).parents[2]


class Settings(BaseSettings):
    project_root: str = str(PROJECT_ROOT)

    # ================= LLM 配置 =================
    llm_provider_admin: str = "google"  # Admin LLM 提供商，默认为 "google"
    llm_provider_visitor: str = "deepseek"  # Visitor LLM 提供商，默认为 "deepseek"

    # ================= Gemini LLM 配置 =================
    gemini_api_key: str = ""
    gemini_model_perf: str = "gemini-2.5-flash"

    # ================= Chat 上下文窗口配置 =================
    sql_history_fetch_limit: int = 100  # 数据库中获取的历史消息数量上限
    max_context_tokens: int = 12000  # LLM 输入的最大上下文 token 长度，只包含历史对话
    max_single_message_tokens: int = 2048  # 最大单条消息 token 长度，只约束历史消息

    # ================= 文本切割配置 =================
    chunk_size_tokens: int = 1000  # 文本块的目标 token 长度
    chunk_overlap_tokens: int = 0  # 文本块之间的重叠 token 数量
    chunk_window_tokens: int = (
        200  # 文本块窗口大小，优先在窗口范围内寻找切割点，默认为 200 tokens
    )

    chunk_size_chars: int = 0  # 文本块的目标字符长度，默认值为 token 长度的 4 倍
    chunk_overlap_chars: int = 0
    chunk_window_chars: int = 0

    # ================= 向量库配置 =================
    vector_store_perf: str = "chromadb"  # 向量库，默认为 "chromadb"

    # ================= ChromaDB 配置 =================
    chromadb_path: str = ""
    # ================= 数据库配置 =================
    sqlite_path: str = ""

    # ================= JWT 配置 =================
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # ================= 管理员账号配置 =================
    admin_username: str = "admin"
    admin_password: str = "admin123"

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env")

    @model_validator(mode="after")
    def compute_chunk_defaults(self) -> "Settings":
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


settings = Settings()
