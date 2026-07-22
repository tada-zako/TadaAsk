"""智谱 GLM 官方 Provider。"""

from .openai_compatible import OpenAICompatibleModel


class GLMModel(OpenAICompatibleModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(
            model_perf=model_perf,
            provider_name="glm",
            api_key=api_key,
            base_url=base_url,
        )
