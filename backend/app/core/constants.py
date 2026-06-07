import enum


class SourceProcessStatus(str, enum.Enum):
    """
    source 数据源处理状态
    """

    PENDING = "pending"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceItemProcessStatus(str, enum.Enum):
    """
    source_item 文档处理状态
    """

    PENDING = "pending"
    PROCESSING = "processing"
    PAUSE_REQUESTED = "pause_requested"  # 请求暂停；业务逻辑中需要到下一个检查点处理
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestStage(str, enum.Enum):
    """
    文档解析阶段
    """

    LOADING = "loading"
    PARSING = "parsing"
    SPLITTING = "splitting"
    FTS_TOKENIZING = "fts_tokenizing"
    EMBEDDING = "embedding"
    INDEXING_SQL = "indexing_sql"
    INDEXING_VECTOR = "indexing_vector"
    PROCESSING_CHUNKS = "processing_chunks"  # 批处理阶段；包括 fts_tokenizing、embedding、indexing_sql/vector 等子阶段；用于前端展示整体进度
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # 文档状态不匹配，跳过处理
    PAUSED = "paused"


class RAGIngestEventType(str, enum.Enum):
    INGEST_START = "ingest_start"
    INGEST_PROGRESS = "ingest_progress"
    _WORKER_DONE = "_worker_done"  # 内部事件，表示单个文档处理完成
    INGEST_COMPLETE = "ingest_complete"
    ITEM_SKIPPED = "item_skipped"  # 文档状态不匹配，跳过处理
    ITEM_PAUSED = "item_paused"
    ITEM_FAILED = "item_failed"
    ITEM_RESUMED = "item_resumed"


class ChatSessionType(str, enum.Enum):
    """
    会话类型
    """

    ADMIN = "admin"
    VISITOR = "visitor"
