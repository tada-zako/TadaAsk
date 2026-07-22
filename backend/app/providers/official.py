"""TadaAsk 内置官方模型提供商定义。"""

from dataclasses import dataclass
from typing import Literal


type ProviderProtocol = Literal["anthropic", "gemini", "openai_compatible"]


@dataclass(frozen=True)
class OfficialProviderDefinition:
    """官方 Provider 的稳定本地标识与运行时连接配置。"""

    name: str
    catalog_name: str
    protocol: ProviderProtocol
    base_url: str | None = None


# catalog_name 来自 models.dev；同一厂商的地域入口各自保存 API key 和启用状态。
OFFICIAL_PROVIDERS: tuple[OfficialProviderDefinition, ...] = (
    OfficialProviderDefinition("openai", "openai", "openai_compatible"),
    OfficialProviderDefinition("google", "google", "gemini"),
    OfficialProviderDefinition("anthropic", "anthropic", "anthropic"),
    OfficialProviderDefinition(
        "deepseek",
        "deepseek",
        "openai_compatible",
        "https://api.deepseek.com",
    ),
    OfficialProviderDefinition(
        "kimi",
        "moonshotai",
        "openai_compatible",
        "https://api.moonshot.ai/v1",
    ),
    OfficialProviderDefinition(
        "alibaba",
        "alibaba",
        "openai_compatible",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ),
    OfficialProviderDefinition(
        "alibaba-cn",
        "alibaba-cn",
        "openai_compatible",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    OfficialProviderDefinition(
        "minimax",
        "minimax",
        "openai_compatible",
        "https://api.minimax.io/v1",
    ),
    OfficialProviderDefinition(
        "minimax-cn",
        "minimax-cn",
        "openai_compatible",
        "https://api.minimaxi.com/v1",
    ),
    OfficialProviderDefinition(
        "glm",
        "zhipuai",
        "openai_compatible",
        "https://open.bigmodel.cn/api/paas/v4",
    ),
    OfficialProviderDefinition(
        "groq",
        "groq",
        "openai_compatible",
        "https://api.groq.com/openai/v1",
    ),
)


OFFICIAL_PROVIDER_BY_NAME = {provider.name: provider for provider in OFFICIAL_PROVIDERS}
