import hashlib
import json
from typing import Any


def normalize_text(text: str) -> str:
    """规范化文本：去除多余空白，统一为单个空格分隔"""
    return " ".join(text.strip().split())


def stable_hash(value: Any) -> str:
    """对任意 JSON-serializable 的值计算稳定的哈希值"""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
