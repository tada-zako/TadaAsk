import hashlib


def calculate_file_hash(file_content: bytes) -> str:
    """计算文件内容的 SHA256 哈希值，用于生成唯一 ID"""
    return hashlib.sha256(file_content).hexdigest()
