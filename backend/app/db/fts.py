from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# FTS5 虚表及相关触发器 DDL
_FTS_DDLS: list[str] = [
    # 1. 创建 FTS5 虚表（external content 模式）
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts 
    USING fts5(
        title, 
        content, 
        content='document_contents', 
        content_rowid='id',
        tokenize='porter unicode61'
    )
    """,
    # 2. INSERT 触发器
    """
    CREATE TRIGGER IF NOT EXISTS documents_ai 
    AFTER INSERT ON document_contents BEGIN
        INSERT INTO documents_fts(rowid, title, content)
        VALUES (new.id, new.title, new.content);
    END
    """
    # 3. UPDATE 触发器
    """
    CREATE TRIGGER IF NOT EXISTS documents_au
    AFTER UPDATE ON document_contents BEGIN
        UPDATE documents_fts 
        SET title = new.title, content = new.content 
        WHERE rowid = new.id;
    END
    """,
    # 4. DELETE 触发器
    """
    CREATE TRIGGER IF NOT EXISTS documents_ad
    AFTER DELETE ON document_contents BEGIN
        DELETE FROM documents_fts WHERE rowid = old.id;
    END
    """,
]


async def init_fts_tables(conn: AsyncConnection) -> None:
    """执行 FTS5 虚表及相关触发器 DDL"""
    for ddl in _FTS_DDLS:
        await conn.execute(text(ddl))
