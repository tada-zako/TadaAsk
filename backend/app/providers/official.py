"""TadaAsk 内置官方模型提供商定义。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialProviderDefinition:
    """模型目录同步所需的官方 Provider 连接信息。"""

    name: str
    catalog_name: str
    base_url: str | None = None


# catalog_name 来自 models.dev；同一厂商的地域入口各自保存 API key 和启用状态。
OFFICIAL_PROVIDERS: tuple[OfficialProviderDefinition, ...] = (
    OfficialProviderDefinition(
        "openai",
        "openai",
    ),
    OfficialProviderDefinition("google", "google"),
    OfficialProviderDefinition("anthropic", "anthropic"),
    OfficialProviderDefinition(
        "deepseek",
        "deepseek",
        "https://api.deepseek.com",
    ),
    OfficialProviderDefinition(
        "kimi",
        "moonshotai",
        "https://api.moonshot.ai/v1",
    ),
    OfficialProviderDefinition(
        "alibaba",
        "alibaba",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ),
    OfficialProviderDefinition(
        "alibaba-cn",
        "alibaba-cn",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    OfficialProviderDefinition(
        "minimax",
        "minimax",
        "https://api.minimax.io/v1",
    ),
    OfficialProviderDefinition(
        "minimax-cn",
        "minimax-cn",
        "https://api.minimaxi.com/v1",
    ),
    OfficialProviderDefinition(
        "glm",
        "zhipuai",
        "https://open.bigmodel.cn/api/paas/v4",
    ),
    OfficialProviderDefinition(
        "groq",
        "groq",
        "https://api.groq.com/openai/v1",
    ),
)
