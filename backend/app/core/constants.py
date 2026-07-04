import enum
from typing import Literal

# ================ 常量定义 ==================
PDF_EXTS = {".pdf"}
DOC_EXTS = {".docx"}
DATA_EXTS = {".json", ".xml", ".yaml", ".yml"}
TEXT_EXTS = {".txt", ".md", ".html"}
# AST 支持解析的源码文件类型
AST_CODE_EXTS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mts",
    ".cts",
    ".mjs",
    ".cjs",
    ".py",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".cs",
}
# 其它源码文件类型
OTHER_CODE_EXTS = {".sh", ".bash", ".sql"}
ALLOWED_FILE_TYPES = (
    PDF_EXTS | DOC_EXTS | DATA_EXTS | TEXT_EXTS | AST_CODE_EXTS | OTHER_CODE_EXTS
)

# AST Scanner 支持的语言类型
type ASTScannerSupportedLanguages = Literal[
    "python",
    "javascript",
    "java",
    "rust",
    "go",
    "typescript",
    "tsx",
    "c",
    "cpp",
    "csharp",
]

# 文件后缀对应的语言映射
EXTENSION_MAP: dict[str, ASTScannerSupportedLanguages] = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
}


# ================ 枚举定义 ==================
class SourceType(str, enum.Enum):
    """
    数据源类型
    """

    LOCAL_FILE = "local_file"
    WEB_CRAWL = "web_crawl"
    GITHUB_REPO = "github_repo"
    CUSTOM_CONTENT = "custom_content"  # 用户直接输入的文本内容


class CrawlEntryType(str, enum.Enum):
    """
    爬取条目类型
    """

    URL_LIST = "url_list"
    SITEMAP_URL = "sitemap_url"
    SITE_ROOT = "site_root"


class SourceProcessStatus(str, enum.Enum):
    """
    source 数据源处理状态
    """

    PENDING = "pending"
    PROCESSING = "processing"
    PAUSE_REQUESTED = "pause_requested"  # 请求暂停
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
    DISCOVERING = "discovering"
    FETCHING = "fetching"
    CHECKING = "checking"
    PARSING = "parsing"
    UPSERTING = "upserting"
    SPLITTING = "splitting"
    FTS_TOKENIZING = "fts_tokenizing"
    EMBEDDING = "embedding"
    INDEXING_SQL = "indexing_sql"
    INDEXING_VECTOR = "indexing_vector"
    PROCESSING_CHUNKS = "processing_chunks"  # 批处理阶段；包括 fts_tokenizing、embedding、indexing_sql/vector 等子阶段；用于前端展示整体进度
    PRUNING = "pruning"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # 文档状态不匹配，跳过处理
    PAUSED = "paused"


class RAGSyncEventType(str, enum.Enum):
    """RAG sync 事件类型；用于不同 Source 类型的 ingest/sync"""

    SYNC_START = "sync_start"
    SYNC_PROGRESS = "sync_progress"
    SYNC_COMPLETE = "sync_complete"
    SYNC_PAUSED = "sync_paused"
    SYNC_FAILED = "sync_failed"

    ITEM_DISCOVERED = "item_discovered"
    ITEM_FETCHED = "item_fetched"
    ITEM_UPSERTED = "item_upserted"
    ITEM_PROGRESS = "item_progress"
    ITEM_SKIPPED = "item_skipped"
    ITEM_DELETED = "item_deleted"
    ITEM_INDEXING = "item_indexing"
    ITEM_COMPLETED = "item_completed"
    ITEM_PAUSED = "item_paused"
    ITEM_FAILED = "item_failed"


class RAGJobStatus(str, enum.Enum):
    """RAG 后台任务状态"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RAGJobType(str, enum.Enum):
    """RAG 后台任务类型"""

    INDEXING = "indexing"
    RESUME_INGEST = "resume_ingest"
    WEB_CRAWL_SYNC = "web_crawl_sync"


# 兼容旧命名；后续前端/API 已迁移到 RAGJobStatus 后可移除。
IndexingJobStatus = RAGJobStatus


class SearchMode(str, enum.Enum):
    """
    搜索模式
    """

    FAST = "fast"  # 快速模式；raw FTS + raw vector -> rrf rank -> rerank(可选)
    ADAPTIVE = "adaptive"  # 自适应模式；根据 raw query 结果判断是否 query expansion
    FULL = "full"  # 全量模式；raw FTS + raw vector -> query expansion -> rrf rank -> rerank(可选)


class ChatSessionType(str, enum.Enum):
    """
    会话类型
    """

    ADMIN = "admin"
    VISITOR = "visitor"


class ChatMessageRole(str, enum.Enum):
    """
    消息角色
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessageType(str, enum.Enum):
    """
    消息类型
    """

    MESSAGE = "message"
    COMPACTION = "compaction"
