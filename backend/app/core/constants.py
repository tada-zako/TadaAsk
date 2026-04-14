import enum


class SourceProcessStatus(str, enum.Enum):
    """
    资源处理状态
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatSessionType(str, enum.Enum):
    """
    会话类型
    """

    ADMIN = "admin"
    VISITOR = "visitor"
