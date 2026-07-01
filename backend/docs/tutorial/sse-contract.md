# Server-Sent Events (SSE) 事件契约 (SSE Contract)

TadaAsk 在**流式聊天问答 (Chat Streams)** 以及 **异步知识导入/抓取 (Crawl/Ingest)** 场景下，统一采用 Server-Sent Events (SSE) 协议来进行后端到前端的准实时数据推送。

---

## 1. 协议规范与前端传输基础

1. **HTTP 请求方式为 POST**：  
   TadaAsk 的所有 SSE 端点（无论是聊天流还是索引进度流）均采用 **HTTP `POST`** 方法传输（为了在 Body 中传递复杂的 RAG 参数、历史消息或 URL 规则配置）。
2. **SSE 标准格式约定**：  
   每一条推送数据严格符合 SSE 标准格式，即：
   ```text
   event: <事件名称>
   data: <JSON 字符串>
   [空行分隔符 \n\n]
   ```
   前端在接收到文本后，需要根据 `event` 分发不同的处理函数，并对 `data` 进行 `JSON.parse` 转换。

---

## 2. 场景 A：流式聊天事件契约 (Chat Stream Events)

流式聊天接口包括：
- `/admin/project/{project_uid}/chat/stream`
- `/admin/chat/stream`
- `/visitor/project/{project_uid}/widget/{widget_uid}/chat/stream`

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

## 3. 场景 B：Ingest / Crawl 同步与索引事件契约

知识源（Source）同步与 Ingestion（解析和向量化）接口均采用 SSE 方式报告复杂步骤进度。

- 网页抓取同步：`POST /admin/source/{source_uid}/crawl/sync`
- 向量化索引：`POST /admin/source/{source_uid}/document/indexing`

这些接口统一推送基于 `RAGSyncEvent` 结构的数据：

### 3.1 常见事件名列表 (`event`)

| 事件名称          | 描述说明                                                                                            |
| :---------------- | :-------------------------------------------------------------------------------------------------- |
| `sync_start`      | 全局同步/索引任务启动。                                                                             |
| `item_discovered` | （仅 Crawl）发现了一个新的待抓取 URL（此时尚未 upsert 产生本地 SourceItem 记录）。                  |
| `item_upserted`   | 抓取过程中对发现的页面进行加载解析并更新/保存对应 `pending` 或最新状态的 `SourceItem` 属性。        |  |
| `item_progress`   | 具体的 SourceItem 正在经历解析（Parsing）、切片（Chunking）或向量化（Embedding）阶段。              |
| `item_skipped`    | 该 SourceItem 重复或由于状态冲突，被跳过。                                                          |
| `item_completed`  | 单个 SourceItem 已经完全成功写入向量索引并更新为 `completed` 状态。                                 |
| `item_paused`     | 响应了 `pause_requested`，当前 SourceItem 的 Ingest 进度被安全冻结在 checkpoint 并标记为 `paused`。 |
| `item_failed`     | 单个 SourceItem 转换中发生故障，标记为 `failed`。                                                   |
| `sync_complete`   | 全局同步/索引批次任务全部结束。                                                                     |

### 3.2 Payload 数据示例 (`data` 内 JSON 结构)
```json
{
  "stage": "indexing",
  "message": "Indexing completed for document TadaAsk-Spec.pdf (12 chunks, 452 tokens)",
  "progress": 85.5,
  "sourceItemUid": "item_pdf_112233",
  "details": {
    "chunksCount": 12,
    "tokensCount": 452,
    "elapsedTimeMs": 1420
  }
}
```

---

## 4. 前端对接与状态更新处理建议 (Best Practices)

1. **`delta` 与 `message_done` 渲染优先级**：
   - 收到 `delta` 时，前端直接将文本**追加**到界面 Assistant 消息气泡的末尾即可。
   - 收到 `message_done` 后，前端**必须以后端最终返回的 `message` 对象（含 `ragSnapshot` 和规范化后的 `content`）全量覆盖当前气泡的数据状态**。
2. **`generationUid` 存储与取消绑定**：
   - 在流对话开始时，前端会收到 `generation_start` 事件，其中包含后端自动为本次流请求生成的 `generationUid`。
   - **前端必须保存此 `generationUid`**。若用户在回答生成完结前点击了“停止生成”按钮，前端应向 `/admin/generation/{generation_uid}/cancel` (或访客侧对应 cancel 端点) 发送 POST 请求。
3. **不支持 Stream 断线断点续传 (Stream Resume)**：
   - 本系统**不支持**流网络断线后从 delta 中途断点恢复。
   - 如果发生弱网断连或连接中断，前端应直接切断该 Stream 监听。此时不需要强行重新生成，而是建议通过时间轴查询接口：`GET /admin/session/{chat_session_uid}/messages` **重新拉取当前会话已落库的历史消息**，以保持内容一致。