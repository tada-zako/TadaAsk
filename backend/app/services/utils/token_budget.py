from dataclasses import dataclass

from app.db.models import ModelProfile
from app.core.config import settings


@dataclass
class TokenBudget:
    """Token 预算封装数据结构"""

    context_window_tokens: int  # 模型上下文窗口
    max_output_tokens: int  # 模型最大输出 token 数量

    # conversation compaction 触发阈值
    compaction_trigger_ratio: float = 0.85

    # 存在 RAG 时，recent_messages 最大占用比率
    rag_recent_max_ratio: float = 0.50
    # 不使用 RAG 时，recent_messages 最大占用比率
    recent_max_ratio: float = 0.75

    # compact 后，保留的 recent_messages 比率
    recent_tail_keep_ratio: float = 0.20

    # RAG context 允许的最大占用
    rag_context_ratio: float = 0.30

    # standalone rewrite 的上下文预算
    standalone_context_ratio: float = 0.20

    @property
    def max_input_tokens(self) -> int:
        """最大允许输入 tokens"""
        return max(0, self.context_window_tokens - self.max_output_tokens)

    @classmethod
    def from_model_profile(cls, profile: ModelProfile | None) -> "TokenBudget":
        """根据模型配置文件创建 TokenBudget 实例；提供默认值回退机制"""
        return cls(
            context_window_tokens=(
                profile.context_window_tokens
                if profile and profile.context_window_tokens
                else settings.llm_default_context_window_tokens
            ),
            max_output_tokens=(
                profile.max_output_tokens
                if profile and profile.max_output_tokens
                else settings.llm_default_max_output_tokens
            ),
        )
