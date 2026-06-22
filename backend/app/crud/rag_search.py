from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceItem, DocumentChunk, ProjectSourceLink
from app.db.schemas import HybridSearchResult
from app.core.constants import SourceItemProcessStatus


class RAGSearchCRUD:
    """RAG search 相关的 CRUD 操作"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_visitor_search_sources(self, project_id: int) -> list[Source]:
        """
        根据 project_id 获取当前项目下所有可用于游客搜索的 sources。
        过滤策略：
            - project_id 对应的 source
            - source.is_public = True
            - source 至少有一个 source_item.status = 'completed' 的数据项
            - source_item.status = 'completed'
        """

        stmt = (
            select(Source)
            .join(ProjectSourceLink, ProjectSourceLink.source_id == Source.id)
            .where(
                and_(
                    ProjectSourceLink.project_id == project_id,
                    Source.is_public,
                    Source.source_items.any(
                        SourceItem.status == SourceItemProcessStatus.COMPLETED
                    ),
                )
            )
            .options(
                selectinload(
                    Source.source_items.and_(
                        SourceItem.status == SourceItemProcessStatus.COMPLETED
                    )
                )
            )
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_admin_search_sources(
        self, source_uids: list[str]
    ) -> list[Source]:
        """
        根据 source_uids 获取对应的 sources，供 Admin 端搜索使用。
        过滤策略：
            - source.uid 在 source_uids 列表中
            - source 至少有一个 source_item.status = 'completed' 的数据项
            - source_item.status = 'completed'
        """

        stmt = (
            select(Source)
            .where(Source.uid.in_(source_uids))
            .where(
                Source.source_items.any(
                    SourceItem.status == SourceItemProcessStatus.COMPLETED
                )
            )
            .options(
                selectinload(
                    Source.source_items.and_(
                        SourceItem.status == SourceItemProcessStatus.COMPLETED
                    )
                )
            )
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_admin_project_sources(self, project_id: int) -> list[Source]:
        """
        根据 project_id 获取当前项目下所有可用于 Admin 搜索的 sources。
        Admin 项目上下文不要求 source.is_public，只要求 source 有已完成的数据项。
        """

        stmt = (
            select(Source)
            .join(ProjectSourceLink, ProjectSourceLink.source_id == Source.id)
            .where(
                and_(
                    ProjectSourceLink.project_id == project_id,
                    Source.source_items.any(
                        SourceItem.status == SourceItemProcessStatus.COMPLETED
                    ),
                )
            )
            .options(
                selectinload(
                    Source.source_items.and_(
                        SourceItem.status == SourceItemProcessStatus.COMPLETED
                    )
                )
            )
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_chunk_ids_by_vector_ids(
        self, vector_ids: list[str]
    ) -> dict[str, int]:
        """
        根据向量 ID 列表获取对应的 chunk ID 列表，返回一个映射字典 {vector_id: chunk_id}。
        如果某个 vector_id 没有找到对应的 chunk_id，则在结果中不包含该 vector_id。
        """
        if not vector_ids:
            return {}

        stmt = select(DocumentChunk.vector_id, DocumentChunk.id).where(
            DocumentChunk.vector_id.in_(vector_ids)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        # 构建 vector_id -> chunk_id 的映射字典
        vector_id_to_chunk_id = {row[0]: row[1] for row in rows}
        return vector_id_to_chunk_id

    async def get_ranked_results_by_chunk_ids(
        self,
        chunk_ids: list[int],
    ) -> list[HybridSearchResult]:
        """
        根据 chunk_id 列表获取对应的 search result 详情列表
        返回结果列表顺序与传入 chunk_ids 保持一致
        """
        if not chunk_ids:
            return []

        stmt = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.vector_id,
                DocumentChunk.chunk_index,
                DocumentChunk.chunk_content.label("content"),
                DocumentChunk.page_number,
                DocumentChunk.section_header,
                DocumentChunk.metadata_json.label("metadata"),
                SourceItem.id.label("source_item_id"),
                SourceItem.uid.label("source_item_uid"),
                SourceItem.title,
                SourceItem.filename,
                SourceItem.origin_url,
                Source.id.label("source_id"),
                Source.uid.label("source_uid"),
                Source.source_name,
            )
            # 多表联合查询
            .join(SourceItem, DocumentChunk.source_item_id == SourceItem.id)
            .join(Source, SourceItem.source_id == Source.id)
            # 过滤条件
            .where(DocumentChunk.id.in_(chunk_ids))
        )

        result = await self.session.execute(stmt)
        rows = result.mappings().all()

        # NOTE: 数据库检索结果会打乱原本的 chunk_ids 顺序
        row_map = {row["chunk_id"]: row for row in rows}

        search_results = []
        for cid in chunk_ids:
            row = row_map.get(cid)
            if not row:
                continue

            search_results.append(
                HybridSearchResult(
                    chunk_id=row["chunk_id"],
                    vector_id=row["vector_id"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    page_number=row["page_number"],
                    section_header=row["section_header"],
                    metadata=row["metadata"],
                    source_item_id=row["source_item_id"],
                    source_item_uid=row["source_item_uid"],
                    title=row["title"],
                    filename=row["filename"],
                    origin_url=row["origin_url"],
                    source_id=row["source_id"],
                    source_uid=row["source_uid"],
                    source_name=row["source_name"],
                    # RRF 分数和 Rerank 分数后续填入
                    rrf_score=None,
                    rerank_score=None,
                )
            )

        return search_results
