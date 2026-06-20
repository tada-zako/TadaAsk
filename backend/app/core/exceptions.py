class DocumentPausedException(Exception):
    """文档处理被用户请求暂停时抛出的异常，用于触发暂停事件"""

    pass


class SecretCryptoError(RuntimeError):
    """密钥加密相关错误的基类"""


class SecretKeyNotConfiguredError(SecretCryptoError):
    """密钥未配置错误，当尝试加密或解密时，如果没有正确配置加密密钥，则抛出此异常"""


class FileParserError(ValueError):
    """文件解析失败时抛出的业务异常"""


class SourceCreateError(Exception):
    """Source 创建异常基类"""

    pass


class SourceCreateValidationError(SourceCreateError):
    """Source 创建数据验证错误"""

    pass


class SourceCreateConflictError(SourceCreateError):
    """Source 创建冲突错误，例如同名数据源已存在"""

    pass


class SourceCreateStorageError(SourceCreateError):
    """Source 创建存储错误"""

    pass
