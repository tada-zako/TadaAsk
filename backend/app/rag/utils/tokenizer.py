from typing import Protocol

from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download

from app.core.config import settings


class TokenizerBase(Protocol):
    """Tokenizer 协议接口，定义 tokenize 和 detokenize 方法"""

    def tokenize(self, text: str) -> list[int]:
        """将文本转换为 token ID 列表"""
        raise NotImplementedError()

    def detokenize(self, tokens: list[int]) -> str:
        """将 token ID 列表转换回文本"""
        raise NotImplementedError()


class HuggingFaceTokenizer:
    """基于 HuggingFace Hub 模型的 Tokenizer 适配器"""

    def __init__(self, model_name: str):
        cache_dir = settings.hf_hub_cache or None

        # 下载 tokenizer 配置文件，获取 tokenizer.json 的本地路径
        try:
            tokenizer_path = hf_hub_download(
                repo_id=model_name,
                filename="tokenizer.json",
                cache_dir=cache_dir,
            )
            self.tokenizer: Tokenizer = Tokenizer.from_file(tokenizer_path)
        except Exception as e:
            raise ValueError(f"无法加载模型 {model_name} 的 tokenizer: {e}")

    def tokenize(self, text: str) -> list[int]:
        """将文本转换为 token ID 列表"""
        return self.tokenizer.encode(text).ids

    def detokenize(self, tokens: list[int]) -> str:
        """将 token ID 列表转换回文本"""
        return self.tokenizer.decode(tokens)
