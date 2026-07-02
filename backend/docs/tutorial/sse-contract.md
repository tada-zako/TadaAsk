# Server-Sent Events (SSE) 事件契约 (SSE Contract)

TadaAsk 在**流式聊天问答 (Chat Streams)** 以及 **异步知识导入/抓取观察 (RAG Jobs)** 场景下使用 Server-Sent Events (SSE) 做后端到前端的准实时推送。

---

## 1. 协议规范与前端传输基础

TadaAsk 目前有两类 SSE 接入方式：

1. **Chat Stream**：聊天流接口本身直接返回 SSE，仍通过 `POST` 发送请求体中的聊天参数。
2. **Source RAG Job**：抓取、索引、恢复导入先通过 `POST` 启动后台任务并返回 `jobUid`，前端再通过 `GET /admin/source/jobs/{job_uid}/events` 观察任务事件。

每一条推送数据符合 SSE 标准格式：

```text
id: <事件序号，可选>
event: <事件名称>
data: <JSON 字符串>

[空行分隔符 \n\n]
```

前端在接收到文本后，需要根据 `event` 分发不同处理函数，并对 `data` 做 `JSON.parse`。Source RAG Job 的 SSE 会额外设置递增的 `id`，用于断线后通过 `Last-Event-ID` 请求头补发缓存事件。

---

## 2. 场景 A：流式聊天事件契约 (Chat Stream Events)

流式聊天接口包括：

- `POST /admin/project/{project_uid}/chat/stream`
- `POST /admin/chat/stream`
- `POST /visitor/project/{project_uid}/widget/{widget_uid}/chat/stream`

聊天流推送的事件和对应的 payload Schema (对应后端 `app.services.schemas` 下的定义) 如下：

### 2.1 `session_ready` (会话准备就绪)
在会话启动时发送。若前端请求中未携带 `chatSessionUid`（代表开启新对话），后端会完成 Session 创建，并在此事件中将新 Session 实体下发。
- **Payload 数据示例** (`data` 字段反序列化后)：
  ```json
  {
    "event": "session_ready",
    "session": {
      "uid": "session_abc123xyz",
      "projectUid": "project_proj999",
      "sessionType": "admin_project_chat",
      "createdAt": "2026-06-27T10:00:00.000Z"
    },
    "created": true
  }
  ```

### 2.2 `generation_start` (流式输出开始)
在此阶段，后端已经完成了 RAG 检索并装配好上下文，大模型开始准备吐字，下发生成的唯一 `generationUid`（用于前端在生成过程中发送“取消/强断”信号）。
- **Payload 数据示例**：
  ```json
  {
    "event": "generation_start",
    "generationUid": "gen_8888-8888-8888",
    "sessionUid": "session_abc123xyz",
    "userMessage": {
      "uid": "msg_user_111",
      "role": "user",
      "messageType": "text",
      "content": "什么是 RAG 技术？",
      "sequence": 1,
      "createdAt": "2026-06-27T10:00:01.000Z"
    },
    "assistantMessage": {
      "uid": "msg_assistant_222",
      "role": "assistant",
      "messageType": "text",
      "content": "",
      "sequence": 2,
      "createdAt": "2026-06-27T10:00:02.000Z"
    }
  }
  ```

### 2.3 `delta` (文本增量推送)
模型吐字过程中的连续增量。
- **Payload 数据示例**：
  ```json
  {
    "event": "delta",
    "messageUid": "msg_assistant_222",
    "delta": "RAG（"
  }
  ```

### 2.4 `message_done` (单条消息生成结束)
对话正常生成完毕，下发**最终、最完整、包含落库属性及 RAG 引用快照（`ragSnapshot`）**的 Message 实体。
- **Payload 数据示例**：
  ```json
  {
    "event": "message_done",
    "message": {
      "uid": "msg_assistant_222",
      "role": "assistant",
      "messageType": "text",
      "content": "RAG（检索增强生成）是一种通过外部检索获取关联文档并拼入 Context 以辅助大模型回答的技术。",
      "sequence": 2,
      "ragSnapshot": {
        "items": [
          {
            "citationId": 1,
            "sourceUid": "src_999",
            "sourceName": "TadaAsk Spec",
            "sourceItemUid": "item_888",
            "title": "TadaAsk Web Crawl Spec",
            "filename": "web-crawl-spec.md",
            "originUrl": "https://example.com/docs/web-crawl-spec",
            "sectionHeader": "MVP Scope",
            "pageNumber": null,
            "anchor": "mvp-scope",
            "excerpt": "MVP 阶段支持静态网页抓取，不处理复杂浏览器环境...",
            "score": 0.92
          }
        ]
      },
      "createdAt": "2026-06-27T10:00:15.000Z"
    }
  }
  ```

### 2.5 `cancelled` (用户主动取消)
当用户在大模型生成过程中，前端调用了 `cancel` 接口，后端成功切断流式生成，并推送该最终状态事件。
- **Payload 数据示例**：
  ```json
  {
    "event": "cancelled",
    "messageUid": "msg_assistant_222",
    "delta": " [已由用户取消生成]"
  }
  ```

### 2.6 `error` (异常中断)
流式生成中途发生严重错误（如 API key 失效，向量库连接超时）。
- **Payload 数据示例**：
  ```json
  {
    "event": "error",
    "message": "Model completion service error: Connection timed out."
  }
  ```

---

## 3. 场景 B：Source RAG Job 事件契约

Source 的网页抓取、文档索引、恢复导入已经拆成“启动任务”和“观察任务”两个阶段。前端不要再把启动接口当成 SSE 流读取。

### 3.1 启动与查询接口

| 用途 | 接口 | 返回 |
| :--- | :--- | :--- |
| 启动网页抓取同步 | `POST /admin/source/{source_uid}/crawl/sync` | `202` + `RAGJobStartResponse` |
| 启动文档索引 | `POST /admin/source/{source_uid}/document/indexing` | `202` + `RAGJobStartResponse` |
| 请求暂停索引 | `POST /admin/source/{source_uid}/document/pause` | `IngestPausedResponse[]`，不是后台 job |
| 启动暂停后的恢复导入 | `POST /admin/source/{source_uid}/document/resume` | `202` + `RAGJobStartResponse` |
| 查询所有活跃 RAG job | `GET /admin/source/jobs/active` | `ActiveRAGJobsResponse` |
| 查询单个 RAG job | `GET /admin/source/jobs/{job_uid}` | `RAGJobRead` |
| 观察单个 RAG job 事件 | `GET /admin/source/jobs/{job_uid}/events` | `text/event-stream` |

启动接口返回示例：

```json
{
  "jobUid": "rag_6ef9d6c6f8e04a80a2638b86a4b3c6b1",
  "jobType": "indexing",
  "sourceUid": "src_abc123",
  "sourceItemUids": ["item_001", "item_002"],
  "status": "queued"
}
```

`jobType` 可能值：

- `web_crawl_sync`
- `indexing`
- `resume_ingest`

`status` 可能值：

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

同一个 `sourceUid` 当前只允许一个活跃的 RAG 后台任务。也就是说，同一 Source 下的 `crawl/sync`、`document/indexing`、`document/resume` 彼此互斥；如果已有 `queued` 或 `running` 任务，重复启动会返回当前活跃 job，而不是新建第二个 job。

### 3.2 观察任务事件

前端拿到 `jobUid` 后，连接：

```http
GET /admin/source/jobs/{job_uid}/events
Accept: text/event-stream
```

事件示例：

```text
id: 12
event: item_progress
data: {"sourceUid":"src_abc123","sourceItemUid":"item_001","sourceItemStatus":"processing","ingestStage":"embedding","itemProgress":70.0,"syncProgress":35.0,"message":"Embedding chunks"}

```

如果 SSE 连接中断，前端可以在重连时带上最后收到的事件序号：

```http
GET /admin/source/jobs/{job_uid}/events
Last-Event-ID: 12
```

后端会补发缓存中 `sequence > 12` 的事件。当前缓存是进程内内存缓存，不能视为长期持久化事件日志；页面恢复时建议同时查询 `GET /admin/source/jobs/{job_uid}` 和 `GET /admin/source/{source_uid}/items` 校准最终状态。

如果使用浏览器原生 `EventSource`，自动重连会沿用最近一次事件的 `id`；如果页面刷新后需要手动指定 `Last-Event-ID`，需要使用支持自定义 header 的 SSE 客户端或 fetch 型封装。

### 3.3 Source RAG 事件名列表

这些事件统一使用 `RAGSyncEvent` 结构。SSE 的 `event:` 字段是事件名，`data:` 中是除 `event` 以外的 JSON payload。

| 事件名称 | 描述说明 |
| :--- | :--- |
| `sync_start` | 全局抓取/索引/恢复任务启动。 |
| `sync_progress` | 全局任务进度更新。 |
| `sync_complete` | 全局任务正常结束。 |
| `sync_paused` | 全局任务因暂停而结束或进入暂停结果。 |
| `sync_failed` | 全局任务异常失败。 |
| `item_discovered` | Web Crawl 发现新的待抓取 URL。 |
| `item_fetched` | Web Crawl 已成功获取页面内容。 |
| `item_upserted` | Web Crawl 将页面写入或更新为 `SourceItem`。 |
| `item_progress` | 单个 `SourceItem` 的解析、切片、向量化等阶段进度。 |
| `item_skipped` | 单个 `SourceItem` 因状态、重复或规则原因被跳过。 |
| `item_indexing` | 单个 `SourceItem` 开始或处于索引写入阶段。 |
| `item_completed` | 单个 `SourceItem` 已成功完成索引并进入 `completed`。 |
| `item_paused` | 单个 `SourceItem` 响应暂停请求并进入 `paused`。 |
| `item_failed` | 单个 `SourceItem` 处理失败。 |

### 3.4 Source RAG Payload 字段

`data` 中常见字段如下，均使用 camelCase：

```json
{
  "sourceUid": "src_abc123",
  "sourceStatus": "processing",
  "sourceItemUid": "item_001",
  "sourceItemStatus": "processing",
  "sourceItem": null,
  "ingestStage": "embedding",
  "itemProgress": 70.0,
  "syncProgress": 35.0,
  "counters": {
    "discovered": 10,
    "fetched": 8,
    "skipped": 1,
    "upserted": 7,
    "indexed": 0,
    "completed": 3,
    "paused": 0,
    "failed": 0
  },
  "message": "Embedding chunks",
  "error": null
}
```

前端实现时建议优先使用：

- `sourceItem`：如果存在，可直接用于更新列表中的完整 item 行。
- `sourceItemUid` + `sourceItemStatus`：用于局部更新单个 item 的状态。
- `ingestStage`、`itemProgress`、`syncProgress`、`counters`：用于展示任务进度。
- `sync_complete`、`sync_failed`、`item_completed`、`item_failed`、`item_paused`：用于触发最终状态刷新。

---

## 4. 前端对接与状态更新处理建议 (Best Practices)

1. **聊天流渲染**：
   - 收到 `delta` 时，前端直接追加文本到当前 Assistant 消息。
   - 收到 `message_done` 后，必须以后端最终返回的 `message` 对象全量覆盖当前气泡状态。
2. **聊天取消**：
   - 收到 `generation_start` 后保存 `generationUid`。
   - 用户点击停止生成时，向 `/admin/generation/{generation_uid}/cancel` 或访客侧对应 cancel 端点发送 `POST`。
3. **聊天流不支持断点续传**：
   - 如果聊天 SSE 断连，不支持从某个 `delta` 中途恢复。
   - 前端应通过 `GET /admin/session/{chat_session_uid}/messages` 重新拉取已落库消息。
4. **Source Job 支持观察连接重建**：
   - 启动抓取、索引或恢复后，保存 `jobUid`。
   - 用户切换页面或 SSE 断线时，后台 job 会继续运行；回到页面后先查 `GET /admin/source/jobs/active` 或 `GET /admin/source/jobs/{job_uid}`，再连接 `/events`。
   - 若保留了最后的 SSE `id`，重连时带 `Last-Event-ID`，但仍应以 job 状态和 SourceItem 列表作为最终一致性来源。
