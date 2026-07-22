"""DeepSeek 官方 Provider。"""

from .openai import OpenAIModel


class DeepSeekModel(OpenAIModel):
    def __init__(self, *, model_perf: str, api_key: str, base_url: str | None = None):
        super().__init__(model_perf=model_perf, api_key=api_key, base_url=base_url)
        self._provider_name = "deepseek"

    def _use_developer_role(self) -> bool:
        return False
