from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# FTS5 虚表及相关触发器 DDL
_FTS_DDLS: list[str] = [
    # 1. 创建 FTS5 虚表 (external content 模式)
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts 
    USING fts5(
        -- 实际存储应用层分词后的结果
        chunk_tokens,
        content='document_chunks', 
        content_rowid='id',
        tokenize='unicode61'
    )
    """,
    # 2. INSERT 触发器
    """
    CREATE TRIGGER IF NOT EXISTS documents_fts_ai 
    AFTER INSERT ON document_chunks BEGIN
        INSERT INTO documents_fts(rowid, chunk_tokens)
        VALUES (new.id, new.chunk_tokens);
    END
    """,
    # 3. UPDATE 触发器
    """
    CREATE TRIGGER IF NOT EXISTS documents_fts_au
    AFTER UPDATE ON document_chunks BEGIN
        -- 删除旧文档
        INSERT INTO documents_fts(documents_fts, rowid, chunk_tokens)
        VALUES('delete', old.id, old.chunk_tokens);

        -- 插入新文档
        INSERT INTO documents_fts(rowid, chunk_tokens)
        VALUES (new.id, new.chunk_tokens);
    END
    """,
    # 4. DELETE 触发器
    """
    CREATE TRIGGER IF NOT EXISTS documents_fts_ad
    AFTER DELETE ON document_chunks BEGIN
        INSERT INTO documents_fts(documents_fts, rowid, chunk_tokens)
        VALUES('delete', old.id, old.chunk_tokens);
    END
    """,
]


async def init_fts_tables(conn: AsyncConnection) -> None:
    """执行 FTS5 虚表及相关触发器 DDL"""
    for ddl in _FTS_DDLS:
        await conn.execute(text(ddl))
