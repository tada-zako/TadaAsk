# TadaAsk — 项目需求与架构文档

## 1. 项目定位

TadaAsk 是一款轻量级、可自托管的开源 AI 知识库助手。核心集成方式为 **Widget 优先**：通过一行 `<script>` 标签即可将具备 RAG 能力的对话组件嵌入任意静态站点或文档页面。

本项目以个人学习为主要目标，**不以商业规模为设计约束**。参考产品为 [kapa.ai](https://kapa.ai)。

---

## 2. 用户角色

| 角色                | 说明                                                                      |
| ------------------- | ------------------------------------------------------------------------- |
| **Admin（站主）**   | 唯一特权用户，管理项目、知识源和管理控制台，可使用高级/Agentic RAG 能力   |
| **Visitor（访客）** | 匿名终端用户，通过部署了该服务的网站访问 Widget，受速率限制和费用控制约束 |

---

## 3. 功能需求

### 3.1 Widget（访客侧）

- 通过单个 HTML 标签嵌入任意静态站点、博客或文档页面。
- 基于 **Web Components** 实现（框架无关，CSS 完全隔离，不污染宿主页面样式）。
- 访客可发起对话、发送消息、接收基于知识库的流式 AI 回复。
- 每次访客会话创建一条 `ChatSession`，消息持久化到 `ChatMessage` 表。
- 访客身份通过匿名 `visitor_id` 标识（如浏览器指纹或 Session Token）。
- **费用控制**：访客侧检索使用简化路径（跳过昂贵的查询扩展），速率限制在 API 层统一执行。

### 3.2 管理控制台（Admin）

- 多项目统一管理仪表盘（一个 Project 可对应多个 Widget 部署实例）。
- **知识源管理**：上传文件、查看 Ingestion 状态、启用/禁用/删除数据源。
- **RAG 数据清洗器**：浏览已索引的 Chunk，手动删除噪声数据（如页脚、备案号等无效内容）。
- **对话监控**：查看访客对话记录，检查每条回复所引用的 RAG 来源。
- **使用统计**：最高频查询的文档、查询量趋势。
- **模型配置**：为每个 Project 设置 LLM 提供商/模型，配置系统提示词，未来支持温度等参数。
- **Widget 定制**：主题色、语言、占位文本。
- 管理员侧 Advanced/Agentic RAG（见第 7 节）。

### 3.3 知识摄取（Ingestion）

支持的数据源类型（渐进式扩展）：

| 数据源类型                             | 状态   |
| -------------------------------------- | ------ |
| 本地文件上传（PDF、MD、TXT、代码文件） | 进行中 |
| 网页爬取（URL / Sitemap）              | 计划中 |
| GitHub 仓库（原始 Markdown + 代码）    | 计划中 |

每个文件的 Ingestion 流程分两阶段：
1. **Upload（上传）** → 存储原始文件字节，创建 `SourceItem`（`status=PENDING`），立即返回
2. **Process（处理，SSE 流式推送）** → 解析 → 分块 → 向量化 → FTS 索引 → 写入 `DocumentChunk` 行

### 3.4 多项目 / 多数据源

- 一个 **Project** 表示一组可复用的知识库与对话配置，可关联多个 **Source**，并可通过多个 **Widget** 部署到不同站点。
- 一个 **Source** 对应一个 ChromaDB Collection（一对一）。
- 多源查询：`asyncio.gather()` 并发查多个 Collection → 在 SQL 层通过 RRF 合并结果。
- Source 通过 `is_public` 字段控制是否对访客侧 RAG 可见。

---

## 4. 架构决策

### 4.1 后端技术栈

- **FastAPI**（异步优先）+ **SQLAlchemy async** + **SQLite**（元数据、对话历史、Chunk 内容存储）
- **ChromaDB**（`PersistentClient`）作为向量库，每个 Source 对应一个 Collection
- **fastembed**：向量化与重排序（ONNX 运行，释放 GIL，可安全放入 `asyncio.to_thread()`）
- **jieba**：中文分词（纯 Python，**不释放 GIL**，必须包裹在 `asyncio.to_thread()` 中）
- **SQLite FTS5**：全文检索（`documents_fts` 虚表，绑定 `document_chunks` 表）
- **sse-starlette**：Ingestion 进度端点的 SSE 流式推送

### 4.2 层次边界

```
Router（HTTP 层，极薄）
    ↓ 不含业务逻辑
Service（编排层）
    ↓ RAGService、ChatService、SourceItemService
Provider / RAG / CRUD（叶子模块）
    ↓ VectorDatabase、EmbeddingProvider、FTSProvider、SourceCRUD ...
```

### 4.3 异步模式

- 所有同步 CPU 密集型操作（`parse`、`embed`、`tokenize`、`split`）必须包裹在 `asyncio.to_thread()` 中运行。
- MVP 阶段**不引入 Celery / 分布式任务队列**，个人规模的吞吐量无需此复杂度。
- `asyncio.gather()` 用于并发多 Collection 向量查询。
- 封装原则：**组件自身**知道它是 CPU 密集型时，由自身负责 `to_thread` 包裹，而非调用方。

### 4.4 文件存储

- **内容寻址存储（CAS）**：物理路径 = `uploads/{hash[:2]}/{hash}{ext}`，路径由内容哈希决定，与 Source 无关。
- `SourceItem.storage_key` 存储路径 key（非原始路径），与 `FileStorage` 实现解耦。
- `FileStorage` 是 Protocol；MVP 实现为 `LocalFileStorage`；未来可替换为 OSS/S3 兼容实现。
- 文件去重：`storage_key` 已存在则跳过写入；通过 `SourceItem` 行数做引用计数，删除时 GC。

### 4.5 SourceItem 跨 Source 去重

- 物理文件通过 CAS 去重（磁盘只存一份）。
- SQL `SourceItem` 行 + `DocumentChunk` 行 + ChromaDB 向量**不跨 Source 共享**。
- 理由：保持 `Source → SourceItem` 严格 1:N 关系，确保级联删除和 ChromaDB Collection 隔离的清晰性。
- 未来优化：`item_hash` 命中已有 `SourceItem` 时，复制 Chunk 数据并向新 Collection 写入向量（跳过解析和向量化步骤）。

### 4.6 Source 可见性控制

- `Source.is_public: bool = False` — 仅 `is_public=True` 的 Source 参与访客侧 RAG 查询。
- 管理员侧 RAG 忽略此字段，查询所有 Source。

### 4.7 DocumentContent 与 DocumentChunk 的职责划分

- `DocumentChunk.chunk_content` — RAG 检索的**权威内容存储**。SQL 是内容的唯一来源，ChromaDB 只存向量。
- `DocumentContent.document_content` — 存储 **file_parser 处理后的 Markdown 文本**（非原始字节）。用于跳过重新索引时昂贵的解析步骤：重新索引只需从此字段读取 → 重跑分块和向量化。
- 原始文件字节通过 `SourceItem.storage_key` 保留，支持完整重新摄取。

---

## 5. RAG 架构

### 5.1 索引流程

```
原始文件字节
    → FileParser.parse()          → ParsedDocument（Markdown 文本 + page_boundaries）
    → TextSplitter.split_text()   → list[TextChunk]（content, pos）
    → FTSProvider.tokenize()      → chunk_tokens（空格分隔的 token 串，用于 FTS 索引）
    → EmbeddingProvider.embed()   → list[NDArray[float32]]
    → SQL: DocumentChunk 行       （chunk_content, chunk_tokens, vector_id, chunk_pos, ...）
    → ChromaDB: 写入向量           （ids=vector_ids, embeddings=..., metadatas={source_item_id}）
    → FTS5: 触发器自动维护索引      （通过 document_chunks 上的 INSERT 触发器）
```

### 5.2 查询流程（Hybrid Search）

```
用户查询
    → QueryExpander.expand_query()   → ExpandedQuery
        .keywords                    → FTSProvider.keywords_search()  → FTSResult list（chunk_id, score）
        .hypothetical_document       → EmbeddingProvider.embed()
        .alternative_queries         → EmbeddingProvider.embed()（逐条或平均）
    → VectorDatabase.query_collection()  → VectorQueryResult list（vector_id, distance）
    → SQL: 解析 vector_id → DocumentChunk.id
    → RRF 融合（k=60）
    → SQL: SELECT chunk_content WHERE id IN (融合后的 id 列表)
    → RerankProvider.rerank()        → 最终排序列表
    → 组装 LLM 上下文 → 生成回复
```

### 5.3 RRF 融合公式

$$\text{score}(chunk) = \sum_{r \in \{\text{fts}, \text{vector}\}} \frac{1}{k + \text{rank}_r(chunk)}, \quad k = 60$$

### 5.4 vector_id 设计

`vector_id = uuid5(RAG_NAMESPACE, f"{source_item_id}_{chunk_index}")`

- 全局唯一、确定性生成、抗碰撞。
- 作为 SQL 与 ChromaDB 之间的桥接键：FTS 返回 `DocumentChunk.id`，ChromaDB 返回 `vector_id`，两者均可通过 SQL 解析到 `chunk_content`。

### 5.5 FTS 索引

- 虚表 `documents_fts` 绑定 `document_chunks.chunk_tokens`。
- `content='document_chunks', content_rowid='id'`。
- 通过 `document_chunks` 上的 `AFTER INSERT / UPDATE / DELETE` 触发器自动维护。
- BM25 评分：`bm25(documents_fts, 3.0, 1.0)`，按升序排列（SQLite BM25 返回负值）。

---

## 6. Ingestion API 设计

### 上传接口（非阻塞）

```
POST /api/admin/sources/{source_uid}/items/upload
Content-Type: multipart/form-data
Body: files[]

← 202 Accepted
← list[SourceItemRead]（status=PENDING）
```

### 处理接口（SSE 流式）

```
POST /api/admin/sources/{source_uid}/document/ingest
Content-Type: application/json
Body: { "itemUids": ["uid1", "uid2"] }

← 200 text/event-stream
← 事件格式：{ stage, message, progress }
   阶段：PARSING | SPLITTING | EMBEDDING | INDEXING | COMPLETED | FAILED
```

### SSE 进度感知设计

`RAGService.process_document_with_progress()` 被设计为 **AsyncGenerator**，逐个 yield `ProgressEvent` 数据类。这避免了 callback 方案的跨线程通信复杂度：每个 pipeline 阶段之间天然存在 `await` 边界，即为进度上报的最佳时机。单个 `to_thread` 调用内部的细粒度进度（如 embedding 第 50/100 个 chunk）暂不支持，留待后续迭代。

---

## 7. Advanced RAG（管理员侧，规划中）

- **Agentic RAG**：LLM 自主决策是否继续检索、调用工具或直接回答。使用 pydantic-ai 作为 Agent 框架。
- **LLM Wiki**：站主侧的私有知识库助手，基于对话历史和手动编辑构建并维护专属知识库。
- **MCP 集成**：通过自然语言对话触发更新向量库、清理缓存、重新索引等管理操作。
- **查询扩展**（已实现）：`ExpandedQuery` 包含 `keywords`、`alternative_queries`、`hypothetical_document`（HyDE）。

---

## 8. LLM 提供商支持

| 提供商                                | 状态   |
| ------------------------------------- | ------ |
| Gemini                                | 已实现 |
| OpenAI 兼容接口（DeepSeek、本地模型） | 已实现 |
| Ollama                                | 规划中 |

所有提供商均实现 `Model` Protocol，提供商选择以 Project 为粒度（存储在 `Project.provider` + `Project.model`）。

---

## 9. 后续规划

- [ ] 基于 Sitemap 的增量网页爬取
- [ ] GitHub 仓库摄取（通过 API 获取原始 Markdown + 代码）
- [ ] Qdrant / LanceDB 作为替代向量库
- [ ] 访客侧速率限制与用量配额
- [ ] 管理员首次运行初始化向导
- [ ] Web Components Widget（框架无关实现）
- [ ] 多进程部署兼容性（ChromaDB Client 模式）
