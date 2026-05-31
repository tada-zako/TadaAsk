import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.rag import (
    VectorQueryResult,
    VectorDatabase,
    EmbeddingProvider,
    RerankProvider,
    FTSProvider,
    QueryExpander,
)
from app.rag.file_parser import FileParser
from app.providers import Message
from app.db.models import Source, SourceItem, DocumentContent, DocumentChunk
from app.db.schemas import (
    SourceInternal,
    SourceRead,
    SourceItemRead,
)
from app.utils.calcu_file_hash import calculate_file_hash

# TODO: 需要完整重构，新增的 Project 模型尚未与 Service 集成

# TODO: "chat messages 构建方法后续提升到 Service 层，确保 messages 构建与 Provider 无关"
# def build_chat_messages(
#     self,
#     document: list[VectorQueryItem],
#     user_message: str,
#     chat_history: list[ChatMessageInternal] | None = None,
# ) -> list[Message]:
#     """
#     构建符合 Gemini LLM 请求接口格式的消息实例
#     """
#     history_contents: list[types.ContentOrDict] | None = None
#     if chat_history:
#         history_contents = [
#             types.Content(
#                 role="model" if entry.role == "assistant" else "user",
#                 parts=[types.Part(text=entry.message)],
#             )
#             for entry in chat_history
#         ]

#     # NOTE: 目前只提供静态系统提示词
#     system_prompt = DEFAULT_SYSTEM_PROMPT

#     if document:
#         # 允许 document 为空
#         context = "\n<Context>\n"
#         for doc in document:
#             context += (
#                 f"[context{doc.id}]:\n{doc.document}\n"
#                 + f"Metadata: {doc.metadata}\n\n"
#             )
#         context += "</Context>\n"

#         user_message = (
#             context + "\n<user_message>\n" + user_message + "\n</user_message>\n"
#         )

#     return [
#         Message(role="system", content=system_prompt),
#     ]


class RAGService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        vector_db: VectorDatabase,
        embedding: EmbeddingProvider,
        query_expander: QueryExpander,
        reranker: RerankProvider,
        fts_provider: FTSProvider,
    ):
        """
        具体的参数由依赖注入传入
        """
        self.session = session
        self.vector_db = vector_db
        self.embedding = embedding
        self.query_expander = query_expander
        self.reranker = reranker
        self.fts_provider = fts_provider

    async def create_collection(self, source_data: SourceInternal) -> SourceRead:
        """创建新的 self.vector_db 集合"""
        logger.info(f"创建 self.vector_db 集合 '{source_data.source_name}'")

        # 检查数据库中是否已存在同名集合记录
        result = await self.session.execute(
            select(1).where(Source.source_name == source_data.source_name).limit(1)
        )
        if result.scalar():
            logger.warning(f"集合 '{source_data.source_name}' 已存在")
            raise ValueError(
                f"Collection with name '{source_data.source_name}' already exists"
            )

        try:
            # 创建向量集合
            await asyncio.to_thread(
                self.vector_db.create_collection,
                collection_name=source_data.collection_name,  # 使用内部生成的 collection_name 字段
            )
        except ValueError as e:
            # 集合可能已存在或集合名不合法
            logger.warning(f"集合 '{source_data.source_name}' 创建失败，错误信息：{e}")
            raise

        try:
            # 数据库中创建集合记录
            new_collection = Source(**source_data.model_dump())
            self.session.add(new_collection)
            await self.session.flush()

            logger.info(f"集合 '{source_data.source_name}' 已创建")
            return SourceRead.model_validate(new_collection)
        except Exception as e:
            # 若数据库写入失败，回滚 Chroma 集合
            logger.error(
                f"集合 '{source_data.source_name}' 数据库写入失败，准备回滚 Chroma 集合，错误信息：{e}"
            )
            try:
                await asyncio.to_thread(
                    self.vector_db.delete_collection,
                    collection_name=source_data.collection_name,
                )
            except Exception as rollback_err:
                logger.error(
                    f"回滚 Chroma 集合失败，collection_name={source_data.collection_name}, 错误信息：{rollback_err}"
                )
            raise

    async def get_collections(
        self, *, limit: int = 10, offset: int = 0
    ) -> list[SourceRead]:
        """获取所有集合列表"""
        result = await self.session.execute(
            select(Source)
            .offset(offset)
            .limit(limit)
            .order_by(Source.created_at.desc())
        )
        collections = result.scalars().all()
        return [SourceRead.model_validate(col) for col in collections]

    async def process_and_store_document(
        self,
        *,
        parser: FileParser,  # 解析器实例，便于后续扩展支持不同类型文档解析
        collection_uid: str,
        file_content: bytes,
        filename: str,
        source: str,
    ) -> SourceItemRead:
        """
        解析文档内容并存储到指定集合中

        Args:
            self.session: 数据库会话
            parser: 文件解析器实例，负责将文件内容解析成文本块列表
            collection_uid: 目标集合 ID
            file_content: 文档文件内容
            filename: 文档文件名，网络爬取时传入 url 的最后一部分
            source: 文档来源，local_file 或 web_scrape

        Returns:
            SourceItemRead 模型，包含文档基本信息
        """
        logger.info(f"处理并存入文档 '{filename}'，来源：{source}")

        # 获取 collection
        collection_res = await self.session.execute(
            select(Source).where(Source.uid == collection_uid)
        )
        collection = collection_res.scalar_one_or_none()
        if not collection:
            logger.error(f"未找到 collection_uid={collection_uid} 对应的集合")
            raise ValueError(f"Collection with uid {collection_uid} does not exist")

        # 检查文件是否已处理过（通过 file_hash 判断）
        # TODO: 可以考虑按照文件大小，控制是否需要扔到线程池中运行
        file_hash = calculate_file_hash(file_content)

        is_duplicate = await self.session.execute(
            select(1)
            .where(
                SourceItem.item_hash == file_hash,
                SourceItem.source_id == collection.id,
            )
            .limit(1)
        )
        if is_duplicate.scalar():
            logger.info(
                f"文档 '{filename}' 已存在于集合 UID {collection_uid} 中，跳过处理"
            )
            raise ValueError(
                f"Document with the same content already exists in the collection. Filename: '{filename}'"
            )

        # 解析文档内容为文本块列表
        # TODO: NOTE: 小心这里可能会有并发性能问题
        documents = await asyncio.to_thread(
            parser.parse, file_input=file_content, filename=filename
        )

        # 存储文本块到向量库
        stored_count = await asyncio.to_thread(
            self.vector_db.upsert_documents,
            collection_name=collection.collection_name,
            documents=documents,
            hash_key=file_hash,
        )

        # 写入文档数据
        new_document = SourceItem(
            filename=filename,
            source=source,
            file_hash=file_hash,
            vector_collection_id=collection.id,
        )
        self.session.add(new_document)
        await self.session.flush()

        logger.info(f"文档 '{filename}' 已处理并存储，文本块数量：{stored_count}")
        return SourceItemRead.model_validate(new_document)

    async def get_related_documents(
        self,
        *,
        collection_uid: str,
        query_text: str,
        top_k: int = 5,
    ) -> list[VectorQueryItem]:
        """
        获取 collection_uid 对应向量集合，
        并执行向量库查询，返回与 query_text 相关文档内容
        """
        logger.info(
            f"进行向量库查询，collection_uid={collection_uid}, query_text='{query_text[:50]}', top_k={top_k}"
        )
        result = await self.session.execute(
            select(Source.collection_name).where(
                Source.uid == collection_uid,
            )
        )
        collection_name = result.scalar_one_or_none()

        if not collection_name:
            raise ValueError(
                f"Can not find vector collection for collection_uid={collection_uid}"
            )

        # 执行向量库查询，获取相关文档
        return await asyncio.to_thread(
            self.vector_db.query,
            collection_name=collection_name,
            query_text=query_text,
            top_k=top_k,
        )
