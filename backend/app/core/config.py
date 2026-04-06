import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict


# 后端项目根路径，指向 backend/ 目录
PROJECT_ROOT = pathlib.Path(__file__).parents[2]


class Settings(BaseSettings):
    project_root: str = str(PROJECT_ROOT)

    llm_provider_perf: str = "google"  # LLM 提供商，默认为 "google"

    # Gemini LLM 配置
    gemini_api_key: str = ""
    gemini_model_perf: str = "gemini-2.5-flash"

    # Chat 上下文窗口配置
    sql_history_fetch_limit: int = 200  # 数据库中获取的历史消息数量上限
    max_context_tokens: int = 12000  # LLM 输入的最大上下文 token 长度，只包含历史对话
    max_single_message_tokens: int = 2048  # 最大单条消息 token 长度，只约束历史消息

    # 数据库配置
    chromadb_path: str = ""
    sqlite_path: str = ""

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env")


settings = Settings()
