from collections.abc import Sequence
from functools import lru_cache

from tiktoken import Encoding, encoding_for_model, get_encoding

from app.db.models import ChatMessages
from app.db.schemas import ChatMessageInternal


MESSAGE_OVERHEAD_TOKENS = 4  # 对话文本外的固定 token 开销（估计值）


@lru_cache(maxsize=8)
def _resolve_encoding(model_name: str | None = None) -> Encoding:
    if model_name:
        try:
            return encoding_for_model(model_name)
        except KeyError:
            pass
    return get_encoding("o200k_base")


def estimate_text_tokens(text: str, *, model_name: str | None = None) -> int:
    """使用 tiktoken 估算文本 token 数。"""
    if not text:
        return 0
    encoding = _resolve_encoding(model_name)
    return len(encoding.encode(text))


def truncate_text_by_tokens(
    text: str,
    max_tokens: int,
    *,
    model_name: str | None = None,
) -> str:
    """将文本裁剪到给定 token 预算内。"""
    if not text or max_tokens <= 0:
        return ""

    if estimate_text_tokens(text, model_name=model_name) <= max_tokens:
        return text

    # 二分法查找最大可接受文本长度
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if estimate_text_tokens(text[:mid], model_name=model_name) <= max_tokens:
            low = mid
        else:
            high = mid - 1

    clipped = text[:low].rstrip()
    return f"{clipped} ..." if clipped else ""


def build_history_context_window(
    chats: Sequence[ChatMessages],
    *,
    max_context_tokens: int,
    max_single_message_tokens: int = 2048,
    model_name: str | None = None,
) -> list[ChatMessageInternal]:
    """
    基于 token 预算，从最近消息向前构建动态窗口。
    保证返回窗口首条消息是 user（若存在）。
    """
    # 如果没有历史消息或上下文窗口大小为 0，直接返回空列表
    if max_context_tokens <= 0 or not chats:
        return []

    selected_message: list[ChatMessageInternal] = []
    used_tokens = 0

    for chat in chats:
        # 确保单次消息不会过长
        safe_message = truncate_text_by_tokens(
            chat.message,
            max_single_message_tokens,
            model_name=model_name,
        )
        msg_tokens = (
            estimate_text_tokens(safe_message, model_name=model_name)
            + MESSAGE_OVERHEAD_TOKENS
        )

        # 超出上下文预算，退出循环
        if selected_message and used_tokens + msg_tokens > max_context_tokens:
            break

        # 第一条消息超出预算，强制裁剪后加入窗口
        if not selected_message and msg_tokens > max_context_tokens:
            budget = max_context_tokens - MESSAGE_OVERHEAD_TOKENS
            safe_message = truncate_text_by_tokens(
                safe_message,
                budget,
                model_name=model_name,
            )
            msg_tokens = (
                estimate_text_tokens(safe_message, model_name=model_name)
                + MESSAGE_OVERHEAD_TOKENS
            )

        internal_chat = ChatMessageInternal.model_validate(chat)
        selected_message.append(
            internal_chat.model_copy(update={"message": safe_message})
        )
        used_tokens += msg_tokens

    # 倒置消息顺序，符合 SDK 调用逻辑
    window = list(reversed(selected_message))

    # 确保窗口首条消息是 user（若存在）
    while window and window[0].role != "user":
        window.pop(0)

    return window
