from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, SourceItem, DocumentChunk, ProjectSourceLink
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

    async def get_search_results_by_chunk_ids(
        self,
        chunk_ids: list[int],
        # TODO: 这里应该返回 list[HybridSearchResult]
    ) -> dict[int, int]:
        """
        根据 chunk ID 列表获取对应的 source_item_id 列表，返回一个映射字典 {chunk_id: source_item_id}。
        如果某个 chunk_id 没有找到对应的 source_item_id，则在结果中不包含该 chunk_id。
        """
        if not chunk_ids:
            return {}

        stmt = select(DocumentChunk.id, DocumentChunk.source_item_id).where(
            DocumentChunk.id.in_(chunk_ids)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        # 构建 chunk_id -> source_item_id 的映射字典
        chunk_id_to_source_item_id = {row[0]: row[1] for row in rows}
        return chunk_id_to_source_item_id
