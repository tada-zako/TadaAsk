import { client } from "./client";
import { parseSseStream } from "@/shared/api/sse";
import type { components } from "@/shared/api/generated/schema";

/** OpenAPI 生成类型别名 */
export type SourceCreatePayload = components["schemas"]["SourceCreate"];
export type SourceUpdatePayload = components["schemas"]["SourceUpdate"];
export type SourceRead = components["schemas"]["SourceRead"];
export type SourceItemRead = components["schemas"]["SourceItemRead"];
export type SourceDeleteResponse =
  components["schemas"]["SourceDeleteResponse"];
export type SourceItemDeleteResponse =
  components["schemas"]["SourceItemDeleteResponse"];
export type SourceItemRenamePayload =
  components["schemas"]["SourceItemRenameRequest"];
export type SourceItemProcessStatus =
  components["schemas"]["SourceItemProcessStatus"];
export type SourceProcessStatus = components["schemas"]["SourceProcessStatus"];
export type IngestPausedResponse =
  components["schemas"]["IngestPausedResponse"];
export type RAGJobStartResponse = components["schemas"]["RAGJobStartResponse"];
export type RAGJobRead = components["schemas"]["RAGJobRead"];
export type ActiveRAGJobsResponse =
  components["schemas"]["ActiveRAGJobsResponse"];

export type SourceUploadPayload = {
  files: File[];
};

/** RAG Job 事件类型定义 */
export type RAGJobEventType =
  | "sync_start"
  | "sync_progress"
  | "sync_complete"
  | "sync_paused"
  | "sync_failed"
  | "item_discovered"
  | "item_fetched"
  | "item_upserted"
  | "item_progress"
  | "item_skipped"
  | "item_deleted"
  | "item_indexing"
  | "item_completed"
  | "item_paused"
  | "item_failed";

/** RAG Job 执行状态类型定义 */
export type RAGJobIngestStage =
  | "loading"
  | "discovering"
  | "fetching"
  | "checking"
  | "parsing"
  | "upserting"
  | "splitting"
  | "fts_tokenizing"
  | "embedding"
  | "indexing_sql"
  | "indexing_vector"
  | "processing_chunks"
  | "pruning"
  | "completed"
  | "failed"
  | "skipped"
  | "paused";

export interface RAGJobCounters {
  discovered: number;
  fetched: number;
  skipped: number;
  upserted: number;
  indexed: number;
  completed: number;
  paused: number;
  failed: number;
  pruned: number;
  cleanupFailed: number;
}

export interface RAGJobEvent {
  /** SSE Source 观察 API 接口响应 event 类型定义 */
  sseId?: string; // SSE id，用于 Last-Event-ID 续接
  event: RAGJobEventType;
  sourceUid: string;
  sourceStatus?: SourceProcessStatus | null;
  sourceItemUid?: string | null;
  sourceItemStatus?: SourceItemProcessStatus | null;
  sourceItem?: SourceItemRead | null;
  ingestStage?: RAGJobIngestStage | null;
  itemProgress?: number | null;
  syncProgress?: number | null;
  counters?: RAGJobCounters | null;
  message?: string | null;
  error?: string | null;
}

type RAGJobEventWirePayload = Partial<RAGJobEvent> & {
  source_uid?: string;
  source_status?: SourceProcessStatus | null;
  source_item_uid?: string | null;
  source_item_status?: SourceItemProcessStatus | null;
  source_item?: SourceItemRead | null;
  ingest_stage?: RAGJobIngestStage | null;
  item_progress?: number | null;
  sync_progress?: number | null;
};

export type StreamRAGJobEventsOptions = {
  lastEventId?: string;
  signal?: AbortSignal;
};

/** Admin Console 数据源接口 */
export const sourceApi = {
  /** 创建 source */
  create: (body: SourceCreatePayload) =>
    client.POST("/admin/source/new", {
      body,
    }),

  /** 获取全局 sources 列表 */
  list: (query: { limit?: number; offset?: number } = {}) =>
    client.GET("/admin/source/list", {
      params: { query },
    }),

  /** 获取 source 详情 */
  get: (sourceUid: string) =>
    client.GET("/admin/source/{source_uid}", {
      params: { path: { source_uid: sourceUid } },
    }),

  /** 更新 source 基础信息或 web crawl 配置 */
  update: (sourceUid: string, body: SourceUpdatePayload) =>
    client.PATCH("/admin/source/{source_uid}", {
      params: { path: { source_uid: sourceUid } },
      body,
    }),

  /** 删除 source，并触发关联 item / 文件 / 向量清理 */
  remove: (sourceUid: string) =>
    client.DELETE("/admin/source/{source_uid}", {
      params: { path: { source_uid: sourceUid } },
    }),

  /** 上传 local_file source 下的文件，后端会创建 SourceItem */
  uploadItems: (
    sourceUid: string,
    payload: SourceUploadPayload,
    signal?: AbortSignal,
  ) => {
    const formData = new FormData();
    for (const file of payload.files) {
      formData.append("files", file);
    }

    return client.POST("/admin/source/{source_uid}/items/upload", {
      params: { path: { source_uid: sourceUid } },
      body: formData as never,
      // 避免 formData 被错误序列化为 JSON
      bodySerializer: (body) => body as unknown as FormData,
      signal,
    });
  },

  /** 获取 source 下的数据项 */
  listItems: (
    sourceUid: string,
    query: { limit?: number; offset?: number } = {},
  ) =>
    client.GET("/admin/source/{source_uid}/items", {
      params: { path: { source_uid: sourceUid }, query },
    }),

  /** 删除 source item，并触发向量/文件清理 */
  deleteItem: (sourceUid: string, sourceItemUid: string) =>
    client.DELETE("/admin/source/{source_uid}/items/{source_item_uid}", {
      params: {
        path: {
          source_uid: sourceUid,
          source_item_uid: sourceItemUid,
        },
      },
    }),

  /** 重命名 source item；local_file 会同步更新 filename */
  renameItem: (
    sourceUid: string,
    sourceItemUid: string,
    body: SourceItemRenamePayload,
  ) =>
    client.PATCH("/admin/source/{source_uid}/items/{source_item_uid}", {
      params: {
        path: {
          source_uid: sourceUid,
          source_item_uid: sourceItemUid,
        },
      },
      body,
    }),

  /** 通过 Admin Bearer token 获取 local_file source item 文件内容。 */
  getItemDownload: (sourceUid: string, sourceItemUid: string) =>
    client.GET("/admin/source/{source_uid}/items/{source_item_uid}/download", {
      params: {
        path: {
          source_uid: sourceUid,
          source_item_uid: sourceItemUid,
        },
      },
      parseAs: "blob",
    }),

  /** 启动 web_crawl 同步后台任务 */
  syncWebCrawl: (sourceUid: string) =>
    client.POST("/admin/source/{source_uid}/crawl/sync", {
      params: { path: { source_uid: sourceUid } },
    }),

  /** 启动 source items 索引后台任务 */
  indexDocuments: (sourceUid: string, itemUids: string[]) =>
    client.POST("/admin/source/{source_uid}/document/indexing", {
      params: { path: { source_uid: sourceUid } },
      body: { itemUids },
    }),

  /** 请求暂停正在处理的 source items */
  pauseIngest: (sourceUid: string, itemUids: string[]) =>
    client.POST("/admin/source/{source_uid}/document/pause", {
      params: { path: { source_uid: sourceUid } },
      body: { itemUids },
    }),

  /** 恢复 paused source items 的索引后台任务 */
  resumeIngest: (sourceUid: string, itemUids: string[]) =>
    client.POST("/admin/source/{source_uid}/document/resume", {
      params: { path: { source_uid: sourceUid } },
      body: { itemUids },
    }),

  /** 获取当前所有活跃 RAG jobs */
  listActiveJobs: () => client.GET("/admin/source/jobs/active"),

  /** 获取指定 RAG job 状态 */
  getJob: (jobUid: string) =>
    client.GET("/admin/source/jobs/{job_uid}", {
      params: { path: { job_uid: jobUid } },
    }),

  /** 连接 RAG job SSE 观察流 */
  streamJobEvents: (jobUid: string, options: StreamRAGJobEventsOptions = {}) =>
    client.GET("/admin/source/jobs/{job_uid}/events", {
      params: {
        path: { job_uid: jobUid },
      },
      headers: {
        Accept: "text/event-stream",
        ...(options.lastEventId
          ? { "Last-Event-ID": options.lastEventId }
          : {}),
      },
      parseAs: "stream",
      signal: options.signal,
    }),
};

/** 将 RAG job SSE ReadableStream 解析为业务事件。 */
export async function* parseRAGJobEventStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<RAGJobEvent, void, unknown> {
  for await (const event of parseSseStream<RAGJobEventWirePayload>(stream)) {
    yield normalizeRagJobEvent(event);
  }
}

// 后端当前按 camelCase 发送 SSE；这里同时兼容 snake_case，降低前后端字段微调的影响。
function normalizeRagJobEvent(event: RAGJobEventWirePayload): RAGJobEvent {
  return {
    sseId: event.sseId,
    event: event.event ?? "sync_progress",
    sourceUid: event.sourceUid ?? event.source_uid ?? "",
    sourceStatus: event.sourceStatus ?? event.source_status ?? null,
    sourceItemUid: event.sourceItemUid ?? event.source_item_uid ?? null,
    sourceItemStatus:
      event.sourceItemStatus ?? event.source_item_status ?? null,
    sourceItem: event.sourceItem ?? event.source_item ?? null,
    ingestStage: event.ingestStage ?? event.ingest_stage ?? null,
    itemProgress: event.itemProgress ?? event.item_progress ?? null,
    syncProgress: event.syncProgress ?? event.sync_progress ?? null,
    counters: event.counters ?? null,
    message: event.message ?? null,
    error: event.error ?? null,
  };
}
