from typing import Protocol, runtime_checkable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .utils import FTSTokenizer


@dataclass
class FTSResult:
    """FTS 检索结果"""

    doc_id: int
    score: float


@runtime_checkable
class FTSProvider(Protocol):
    """FTS 检索接口"""

    def tokenize_for_index(self, text: str) -> str:
        """将原始文本处理为空格分隔的 token 串（用于构建 FTS 索引）"""
        ...

    def tokenize_for_query(self, text: str) -> str:
        """将查询文本处理为 FTS5 MATCH 表达式（用于构建 FTS 查询语句）"""
        ...

    async def semantic_search(
        self,
        session: AsyncSession,
        user_query: str,
        *,
        limit: int = 10,
    ) -> list[FTSResult]:
        """执行语义搜索，返回匹配的文档 ID 列表"""
        ...

    async def keywords_search(
        self,
        session: AsyncSession,
        lex_queries: list[str],
        *,
        limit: int = 10,
    ) -> list[FTSResult]:
        """基于关键词列表执行 FTS 搜索，返回匹配的文档 ID 列表"""
        ...

    async def index_document(
        self, session: AsyncSession, *, doc_id: int, title: str, content: str
    ) -> None:
        """将文档内容索引到 FTS 虚表中"""
        ...

    async def remove_document(self, session: AsyncSession, doc_id: int) -> None:
        """从 FTS 索引中删除指定文档 ID"""
        ...

    async def rebuild_index(self, session: AsyncSession) -> None:
        """重建 FTS 索引"""
        ...


class SQLiteFTSProvider:
    """基于 SQLite FTS5 的全文检索实现"""

    def __init__(self, tokenizer: FTSTokenizer):
        self._tokenizer = tokenizer

    # FTS 分词接口代理
    def tokenize_for_index(self, text: str) -> str:
        return self._tokenizer.tokenize(text)

    def tokenize_for_query(self, text: str) -> str:
        return self._tokenizer.tokenize_for_query(text)

    # --- FTS 搜索与索引管理接口 ---
    async def semantic_search(
        self,
        session: AsyncSession,
        user_query: str,
        *,
        limit: int = 10,
    ) -> list[FTSResult]:
        """执行 FTS 搜索，返回匹配的文档 ID 列表"""
        fts_query = self._tokenizer.tokenize_for_query(user_query)
        return await self._fts_search(session, fts_query, limit=limit)

    async def keywords_search(
        self,
        session: AsyncSession,
        lex_queries: list[str],
        *,
        limit: int = 10,
    ) -> list[FTSResult]:
        """基于关键词列表执行 FTS 搜索，返回匹配的文档 ID 列表"""
        if not lex_queries:
            return []

        # 构建 MATCH 表达式
        match_expr = self._tokenizer.build_match_expr_from_expanded_tokens(lex_queries)
        return await self._fts_search(session, match_expr, limit=limit)

    async def _fts_search(
        self,
        session: AsyncSession,
        fts_query: str,
        *,
        limit: int = 10,
    ) -> list[FTSResult]:
        """执行 FTS 搜索，返回匹配的文档 ID 列表"""
        if not fts_query.strip():
            return []

        rows = await session.execute(
            text(
                """
                SELECT rowid, bm25(documents_fts, 3.0, 1.0) AS bm25_score
                FROM documents_fts
                WHERE documents_fts MATCH :query
                ORDER BY bm25_score ASC
                LIMIT :limit
                """
            ),
            {"query": fts_query, "limit": limit},
        )

        return [FTSResult(doc_id=row.rowid, score=row.bm25_score) for row in rows]

    async def index_document(
        self, session: AsyncSession, *, doc_id: int, title: str, content: str
    ) -> None:
        """将文档内容索引到 FTS 虚表中"""
        # NOTE: 暂不清楚用处，保留接口以备后续实现增量索引或其他索引维护策略
        tokens = self._tokenizer.tokenize(content)
        await session.execute(
            text(
                """
                INSERT INTO document_contents (rowid, title, tokens)
                VALUES (:doc_id, :title, :tokens)
                ON CONFLICT(rowid) DO UPDATE SET
                    title=excluded.title,
                    tokens=excluded.tokens
                """
            ),
            {"doc_id": doc_id, "title": title, "tokens": tokens},
        )

    async def remove_document(self, session: AsyncSession, doc_id: int) -> None:
        """从 FTS 索引中删除指定文档 ID"""
        # NOTE: 暂不清楚用处，保留接口以备后续实现增量索引或其他索引维护策略
        await session.execute(
            text("INSERT INTO documents_fts(documents_fts) VALUES('delete', :doc_id)"),
            {"doc_id": doc_id},
        )

    async def rebuild_index(self, session: AsyncSession) -> None:
        """重建 FTS 索引"""
        # NOTE: 暂不清楚用处，保留接口以备后续实现增量索引或其他索引维护策略
        await session.execute(
            text("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
        )
