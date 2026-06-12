from .tokenizer import EmbeddingTokenizer

# 预测的每条消息固定 token 开销
MESSAGE_OVERHEAD_TOKENS = 4


class TokenCounter:
    """
    EmbeddingTokenizer 接口封装；
    提供基于 tokenizer 的文本 token 计数以及文本截断功能
    """

    def __init__(self, tokenizer: EmbeddingTokenizer):
        self.tokenizer = tokenizer

    def count_text(self, text: str) -> int:
        """计算文本的 token 数量"""
        tokens = self.tokenizer.tokenize(text)
        return len(tokens)

    def count_message(self, message: str) -> int:
        """计算消息文本的 token 数量；考虑 message_overhead 的影响"""
        return self.count_text(message) + MESSAGE_OVERHEAD_TOKENS

    def truncate_text(self, text: str, max_tokens: int) -> str:
        """将文本截断到指定的最大 token 数量"""
        tokens = self.tokenizer.tokenize(text)
        if len(tokens) <= max_tokens:
            return text
        return self.tokenizer.detokenize(tokens[:max_tokens]).rstrip()
