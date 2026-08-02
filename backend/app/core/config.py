from typing import Literal, cast

import pathlib
from loguru import logger

from pydantic import model_validator, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


# 后端项目根路径，指向 backend/ 目录
PROJECT_ROOT = pathlib.Path(__file__).parents[2]
DEFAULT_EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_RERANK_MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"

# 类型别名
type EmbeddingBackend = Literal["fastembed", "llamacpp"]  # 文本嵌入后端
type RerankBackend = Literal["fastembed", "llamacpp"]  # Rerank 后端
type LogLevel = Literal[
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
]
type LogFormat = Literal["console", "json"]


class Settings(BaseSettings):
    project_root: str = str(PROJECT_ROOT)

    # =======================================
    # LLM 相关配置
    # =======================================

    # API Key 加密配置
    provider_api_key_encryption_key: str = ""
    provider_api_key_previous_encryption_keys: str = ""

    sql_history_fetch_limit: int = 100  # 数据库中获取的历史消息数量上限
    max_context_tokens: int = 12000  # LLM 输入的最大上下文 token 长度，只包含历史对话
    max_single_message_tokens: int = 2048  # 最大单条消息 token 长度，只约束历史消息

    # LLM 请求默认参数
    llm_default_context_window_tokens: int = 32768
    llm_default_max_output_tokens: int = 4096
    llm_default_temperature: float = 0.7
    llm_default_top_p: float = 0.95
    llm_default_timeout: float = 60.0
    llm_default_thinking: (
        bool | Literal["minimal", "low", "medium", "high", "xhigh", "max"]
    ) = "medium"
    models_url: str = "https://models.dev/api.json"

    # =======================================
    # RAG 相关配置
    # =======================================

    embedding_backend: EmbeddingBackend = "fastembed"  # 文本嵌入后端
    rerank_backend: RerankBackend = "fastembed"  # Rerank 后端
    hyde_enabled: bool = False  # 是否启用 HyDE 生成虚拟文档增强检索，默认为 False

    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL_NAME  # 文本嵌入模型名称
    rerank_model_name: str = DEFAULT_RERANK_MODEL_NAME  # Rerank 模型名称

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
    # 默认支持本地 Vite 开发
    admin_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    file_storage_backend: str = "local"  # 文件存储后端，默认为本地存储
    max_file_size: int = 5 * 1024 * 1024  # 最大文件上传大小
    max_file_count: int = 8  # 最大文件上传数量
    upload_folder_path: str = str(PROJECT_ROOT / "data" / "uploads")  # 文件上传存储路径
    vector_store_perf: str = "chromadb"  # 向量库配置

    # 模型缓存路径
    fastembed_model_cache_dir: str | None = None  # FastEmbed 模型缓存目录
    llamacpp_model_cache_dir: str | None = None  # LLaMA.cpp 模型缓存目录
    hf_hub_cache_dir: str | None = None  # HuggingFace Hub 模型缓存目录

    chromadb_path: str = str(
        PROJECT_ROOT / "data" / "chromadb"
    )  # ChromaDB 数据存储路径
    sqlite_database_path: str = str(
        PROJECT_ROOT / "data" / "sqlite.db"
    )  # SQLite FTS 数据库路径
    sqlalchemy_echo: bool = False  # 是否输出 SQLAlchemy SQL 日志
    database_auto_migrate: bool = True  # FastAPI 启动时自动执行 Alembic upgrade head

    # 日志配置
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "console"
    log_file_enabled: bool = False
    log_file_path: str = str(PROJECT_ROOT / "data" / "logs" / "tadaask.log")

    # =======================================
    # visitor 侧请求限制
    # =======================================
    visitor_rate_limit_enabled: bool = True  # 是否启用 visitor 请求限制

    visitor_rate_limit_ip_project_per_minute: int = 6  # 每 IP + project：6 次 / 分钟
    visitor_rate_limit_ip_project_per_hour: int = 60  # 每 IP + project：60 次 / 小时
    visitor_rate_limit_ip_per_minute: int = 20  # 每 IP 全局：20 次 / 分钟
    visitor_rate_limit_project_per_minute: int = 120  # 每 project 全局：120 次 / 分钟

    visitor_stream_concurrency_per_ip: int = 2  # 每 IP 同时 stream：2
    visitor_stream_concurrency_per_project: int = 20  # 每 project 同时 stream：20

    visitor_message_max_chars: int = 4000  # visitor 侧单条消息最大字符数
    visitor_trust_proxy_headers: bool = False  # 是否信任 X-Forwarded-For

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
    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """日志级别统一使用 Loguru 的大写名称。"""
        return str(value).strip().upper()

    @field_validator("log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: str) -> str:
        """日志格式环境变量转换为小写。"""
        return str(value).strip().lower()

    @model_validator(mode="after")
    def normalize_model_defaults(self) -> "Settings":
        """允许 .env 显式留空时继续使用内置默认模型。"""
        if not self.embedding_model_name.strip():
            self.embedding_model_name = DEFAULT_EMBEDDING_MODEL_NAME
        if not self.rerank_model_name.strip():
            self.rerank_model_name = DEFAULT_RERANK_MODEL_NAME
        return self

    @field_validator("admin_username", mode="before")
    @classmethod
    def validate_admin_username(cls, value: str) -> str:
        """管理员用户名用于启动同步，禁止空值并移除意外的首尾空格。"""
        username = str(value).strip()
        if not username:
            raise ValueError("ADMIN_USERNAME must not be empty")
        return username

    @field_validator("admin_password", mode="before")
    @classmethod
    def validate_admin_password(cls, value: str) -> str:
        """密码保留原始字符，仅拒绝空值或纯空白配置。"""
        password = str(value)
        if not password.strip():
            raise ValueError("ADMIN_PASSWORD must not be empty")
        return password

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
                "Text splitter window is not smaller than chunk size: window={} size={}",
                self.chunk_window_tokens,
                self.chunk_size_tokens,
            )

        return self

    @field_validator(
        "fastembed_model_cache_dir",
        "llamacpp_model_cache_dir",
        "hf_hub_cache_dir",
        mode="before",
    )
    @classmethod
    def process_model_paths(cls, v: str | None) -> str | None:
        """如果为空白字符或None，返回None；
        否则对路径进行规范化"""
        if v is None or str(v).strip() == "":
            return None

        path = pathlib.Path(str(v).strip())
        if path.is_absolute():
            # 绝对路径
            # 确保路径存在
            path.mkdir(parents=True, exist_ok=True)
            return str(path)

        # 相对路径 -> 拼接 PROJECT_ROOT 并 resolve 规范化
        path = (PROJECT_ROOT / path).resolve()
        # 确保路径存在
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @classmethod
    def _resolve_path(cls, v: str | None, info: ValidationInfo) -> pathlib.Path:
        """将相对路径解析为绝对路径"""
        field_name = info.field_name
        if field_name is None:
            raise ValueError("Field name should not be None")

        if v is None or str(v).strip() == "":
            # 如果传入为空或 None，获取该字段在类中定义的默认值
            default_val = cls.model_fields[field_name].default
            if default_val is None:
                raise ValueError(f"Field '{field_name}' has no default value.")
            path = cast(str, default_val)
            raw_path = pathlib.Path(str(path).strip())
        else:
            raw_path = pathlib.Path(str(v).strip())

        if raw_path.is_absolute():
            # 绝对路径
            return raw_path

        # 相对路径 -> 拼接 PROJECT_ROOT 并 resolve 规范化
        return (PROJECT_ROOT / raw_path).resolve()

    @field_validator("upload_folder_path", "chromadb_path", mode="before")
    @classmethod
    def process_dir_paths(cls, v: str | None, info: ValidationInfo) -> str:
        """处理 dir 路径"""
        path = cls._resolve_path(v, info)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @field_validator("sqlite_database_path", mode="before")
    @classmethod
    def process_file_paths(cls, v: str | None, info: ValidationInfo) -> str:
        """处理 file 路径"""
        path = cls._resolve_path(v, info)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @field_validator("log_file_path", mode="before")
    @classmethod
    def process_log_file_path(cls, v: str | None, info: ValidationInfo) -> str:
        """解析日志文件路径；仅在启用文件 sink 时创建父目录。"""
        return str(cls._resolve_path(v, info))


settings = Settings()
