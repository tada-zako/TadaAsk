class DocumentPausedException(Exception):
    """文档处理被用户请求暂停时抛出的异常，用于触发暂停事件"""

    pass


class SecretCryptoError(RuntimeError):
    """密钥加密相关错误的基类"""


class SecretKeyNotConfiguredError(SecretCryptoError):
    """密钥未配置错误，当尝试加密或解密时，如果没有正确配置加密密钥，则抛出此异常"""
