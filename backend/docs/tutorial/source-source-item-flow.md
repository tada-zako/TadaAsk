# Source 与 SourceItem 异步生命周期 (Source & SourceItem Lifecycle)

在 TadaAsk 的 RAG（检索增强生成）知识库架构中，数据管理采用 **“两层实体 + 两段异步”** 的设计。前端必须理解其核心状态机与工作流，以在 Admin Console 中提供合理的交互反馈。

---

## 1. 概念模型说明

- **知识源 (Source)**：对一种知识输入途径的逻辑封装（比如“一个文档集”或“一个静态网站”）。
  - **当前 MVP 支持类型** (`sourceType`)：
    - `local_file` (本地文件上传)
    - `web_crawl` (网页同步与抓取)
  - **保留/未来支持类型**：`github_repo` (GitHub 仓库同步), `custom_content` (手写 Markdown / 自定义录入)。由于后端代码中已定义这些枚举值，但在服务中暂未实现完整处理逻辑，前端请将其标记为暂不开放或测试。
- **知识子项 (SourceItem)**：Source 实例化后的具体颗粒度文档。
  - 对于 `local_file`，每个 SourceItem 对应**一个具体上传的文件**（如 `readme.md`）。
  - 对于 `web_crawl`，每个 SourceItem 对应**一个具体抓取到的 URL 网页**。

---

## 2. 数据处理两阶段流程

数据从管理员录入到最终在 RAG 中“可检索”，必须依次通过 **发现/同步阶段 (Discover & Sync)** 和 **解析/向量化索引阶段 (Ingestion & Indexing)**。抓取、索引、恢复导入都以后台 RAG Job 运行；前端通过单独的 SSE 观察接口追踪进度。

```
[管理员交互]
    │
    ▼ (1. 发现/同步)
Create Source ───► Local File Upload      ───► SourceItems (PENDING)
               ───► Start Web Crawl Job   ───► SourceItems (PENDING)
                                                │
                                                ▼ (2. 索引)
                                          Start Index Job ───► Parse ───► Chunk ───► FTS & Vector Index ───► Completed (可检索)
```

### 2.1 流程 A：本地文件流程 (Local File Flow)
1. **创建 Source**：发送 `POST /admin/source/new`，设置 `sourceType="local_file"`。
2. **上传文件**：向 `POST /admin/source/{source_uid}/items/upload` 上传文件（支持多文件）。
   - *后端规则*：在此阶段，后端会：
     1. 验证文件合法性（后缀合法、大小不超限、总数不超限）。
     2. 对文件进行 **CAS (Content-Addressable Storage, 内容寻址存储)** 哈希哈希计算，生成基于内容 SHA256 的存储路径（即 `storageKey`），保存文件。
     3. 自动将文件映射为 `SourceItem` 记录入库。
     4. 这些新增的 SourceItem 的初始状态为 `pending`。
3. **查询 Items 列表**：通过 `GET /admin/source/{source_uid}/items` 查询，此时文件状态均为 `pending`。
4. **启动 Ingestion (解析/索引)**：执行 Flow C。

### 2.2 流程 B：网页抓取流程 (Web Crawl Flow)
1. **创建 Source**：发送 `POST /admin/source/new`，设置 `sourceType="web_crawl"`，并填充 `webCrawlConfig`（包括抓取入口 `entryType`：`url_list` / `sitemap` / `site_root`，以及爬取域名规则和 content/exclude DOM 选择器）。
2. **触发同步 (Discover & Crawl)**：发送 `POST /admin/source/{source_uid}/crawl/sync`。
   - *返回值*：该接口返回 `202` 和 `RAGJobStartResponse`，其中包含 `jobUid`，不会直接返回 SSE。
   - *后端工作*：后台 job 会按配置规则下载页面、解析有效链接，并为有效网页写入或更新 `SourceItem`，通常保持为 `pending`，等待后续索引。
3. **观察同步进度**：使用上一步拿到的 `jobUid` 连接 `GET /admin/source/jobs/{job_uid}/events`。
4. **查询 Items 列表**：同步完成后，通过 `GET /admin/source/{source_uid}/items` 获取最新 SourceItem 列表。
5. **启动 Ingestion (解析/索引)**：执行 Flow C。

### 2.3 流程 C：向量化索引流程 (Ingestion/Indexing Flow)
无论文件还是抓取的网页，新建立的 SourceItem 均处于 `pending`。必须通过 **Ingestion API** 触发深度解析与向量库索引：

1. **启动 Ingestion**：发送 `POST /admin/source/{source_uid}/document/indexing`，并在请求体中传入要处理的 `itemUids: [string]` 数组。
2. **保存 Job 信息**：该接口返回 `202` 和 `RAGJobStartResponse`，前端需要保存 `jobUid`。此端点不是 SSE 事件流。
3. **SSE 进度追踪**：连接 `GET /admin/source/jobs/{job_uid}/events`。关于事件体详见 [sse-contract.md](./sse-contract.md)。后端会逐个对传入的 Item 进行：
   - 提取正文并转化为 Markdown
   - 保存 Markdown 全文到数据库中（用作后续 RAG 重新索引免解析缓存）
   - 按规则切片 (Chunking)
   - 为每个 Chunk 生成 globally unique vector ID (uuid5)
   - 同步至 FTS 全文检索虚拟表 (`documents_fts`)
   - 提取向量 embedding，存入 ChromaDB 向量集合
   - 成功后将 SourceItem 的状态标记为 `completed`。

### 2.4 流程 D：暂停与恢复 (Pause/Resume Flow)

1. **请求暂停**：发送 `POST /admin/source/{source_uid}/document/pause`，请求体同样传入 `itemUids: [string]`。
   - 该接口是普通命令接口，返回 `IngestPausedResponse[]`，不会创建 RAG job。
   - 暂停是协同式的：正在处理的 Item 会先进入 `pause_requested`，等索引流程到达 checkpoint 后再安全迁移到 `paused`。
2. **恢复导入**：对已经处于 `paused` 的 Item，发送 `POST /admin/source/{source_uid}/document/resume`。
   - 该接口返回 `202` 和 `RAGJobStartResponse`。
   - 如果传入的 Item 不是 `paused`，后端返回 `400`。
3. **观察恢复进度**：使用返回的 `jobUid` 连接 `GET /admin/source/jobs/{job_uid}/events`。

### 2.5 RAG Job 前端接入要点

- `crawl/sync`、`document/indexing`、`document/resume` 都是任务启动接口；真正的进度流统一来自 `GET /admin/source/jobs/{job_uid}/events`。
- `GET /admin/source/jobs/active` 可用于页面刷新、路由切换后恢复当前活跃任务列表。
- `GET /admin/source/jobs/{job_uid}` 可用于查询单个 job 的 `queued` / `running` / `completed` / `failed` / `cancelled` 状态。
- 同一个 `sourceUid` 当前只允许一个活跃 RAG job；同一 Source 的抓取、索引、恢复不会并发运行。重复启动时，后端会返回当前活跃 job，前端应以返回体中的 `jobType` 和 `sourceItemUids` 判断是否复用了已有任务。
- SSE 事件是进程内缓存，不是长期持久化日志。前端恢复页面时，应以 job 查询和 `GET /admin/source/{source_uid}/items` 的结果校准最终状态。

---

## 3. 状态机模型 (SourceItem State Machine)

SourceItem 的 `status` 字段定义了其生命周期的中间状态和终端状态：

| 状态值 (`status`) | 说明                                                                                                                  |
| :---------------- | :-------------------------------------------------------------------------------------------------------------------- |
| `pending`         | **初始/等待中**。Item 已在本地磁盘或网页同步中生成，等待运行 Ingestion 写入向量索引。                                 |
| `processing`      | **处理中**。正在经历 Ingestion 解析、切片或向量导入。                                                                 |
| `pause_requested` | **暂停请求中**。管理员点击了“暂停 Ingestion”按钮，后端会在下一个 Checkpoint 阶段捕获该信号并暂停。                    |
| `paused`          | **已暂停**。任务已经冻结，可被 Claim 重新恢复索引。                                                                   |
| `completed`       | **成功/可检索 (终端状态)**。该文档的切片和向量已完全入库，**此时该 Item 的内容方可被 Visitor/Admin RAG 检索并问答**。 |
| `failed`          | **失败 (终端状态)**。解析或向量计算过程中报错。                                                                       |

### 3.1 索引 Claim 与抢占规则 (Claims on Ingestion)
在触发索引 Ingest 时，只有处于以下状态的 SourceItem 才允许被“认领”处理：
- **可 Claim 状态**：`pending` / `paused` / `failed`
- **冲突/忙碌状态**：如果 Item 处于 `processing` 或 `pause_requested`，当前索引 job 中该项不会被重复处理，通常会通过 job 事件返回 `item_skipped`。
- **恢复导入限制**：`POST /admin/source/{source_uid}/document/resume` 只接受 `paused` 的 Item；如果传入非 `paused` Item，后端会返回 HTTP `400`。

### 3.2 暂停 (Pause) 机制说明
- 暂停并不是“强制立即杀死进程”，而是由 Ingestion 循环通过协同式 Checkpoint 捕捉管理员下发的 `pause_requested`。
- 当一个 SourceItem 达到 Checkpoint 时，如果检测到暂停请求，会保存当前已完成的部分进度，并安全地将状态迁移至 `paused`。

---

## 4. 删除 SourceItem 行为与安全约束

在 Admin Console 界面中，管理员可以对 SourceItem 进行删除操作（调用 `DELETE /admin/source/{source_uid}/items/{source_item_uid}`），后端具有如下安全边界：

1. **状态安全校验**：
   - 如果 SourceItem 处于 `processing` 或 `pause_requested`，**不允许进行删除**。后端会直接返回 `409 Conflict` 错误（提示：`Source item is busy, pause it or wait until processing finishes`）。
2. **级联清理范畴**：
   - 删除成功后，后端会级联删除：
     - 数据库中的 `SourceItem` 实体记录
     - 该 Item 下属的所有 `DocumentChunk` 数据库切片记录
     - 全文检索 FTS 对应的虚拟表分词记录
     - ChromaDB 向量库中与这些切片关联的所有向量节点
3. **CAS 物理文件清理约束（重点不承诺）**：
   - 当前后端实现中，删除 SourceItem 时，后端会*尝试*移除本地存储介质（如磁盘）中由 `storageKey` 标识的物理文件。
   - **文档注意**：请勿在前端向用户过度承诺“已经支持高并发安全的 CAS 引用计数物理文件垃圾回收 (GC)”。在多人协作或多个 SourceItem 共享同一物理内容哈希时，底层的物理删除可能会有简化处理。

---

## 5. 访客侧 (Visitor RAG) 的 Source 准入策略

当访客（Visitor）在 Widget 中发起带有 RAG 的对话时，后端对知识库有一套极为严格的可见性判定：
- **公共属性校验**：Source 必须设置 `isPublic = True`。
- **状态属性校验**：Source 本身及下属的 SourceItem，必须是 **至少存在一个已经达到 `completed`（完全索引成功）的 SourceItem**，该 Source 才能对 Visitor 生效。
- 只要 Source 内部没有任何 `completed` 的子项（即均处于 `pending`、`processing`、`failed`），该 Source 的数据就绝不会进入 Visitor 的检索召回链路。
