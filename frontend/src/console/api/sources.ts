import { client } from "./client";
import { parseSseStream } from "@/shared/api/sse";
import type { components } from "@/shared/api/generated/schema";

export type SourceCreatePayload = components["schemas"]["SourceCreate"];
export type SourceRead = components["schemas"]["SourceRead"];
export type SourceItemRead = components["schemas"]["SourceItemRead"];
export type SourceItemDeleteResponse =
  components["schemas"]["SourceItemDeleteResponse"];
export type SourceItemProcessStatus =
  components["schemas"]["SourceItemProcessStatus"];
export type SourceProcessStatus = components["schemas"]["SourceProcessStatus"];
export type IngestPausedResponse =
  components["schemas"]["IngestPausedResponse"];
export type RAGJobStartResponse = components["schemas"]["RAGJobStartResponse"];
export type RAGJobRead = components["schemas"]["RAGJobRead"];
export type ActiveRAGJobsResponse =
  components["schemas"]["ActiveRAGJobsResponse"];

export type SourceListQuery = {
  limit?: number;
  offset?: number;
};

export type SourceItemListQuery = {
  limit?: number;
  offset?: number;
};

export type SourceItemUidPayload = {
  itemUids: string[];
};

export type SourceUploadPayload = {
  files: File[];
};

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
  | "item_indexing"
  | "item_completed"
  | "item_paused"
  | "item_failed";

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
}

export interface RAGJobEvent {
  /** SSE id，用于 Last-Event-ID 续接。 */
  sseId?: string;
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
  list: (query: SourceListQuery = {}) =>
    client.GET("/admin/source/list", {
      params: { query },
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
      bodySerializer: (body) => body as unknown as FormData,
      signal,
    });
  },

  /** 获取 source 下的数据项 */
  listItems: (sourceUid: string, query: SourceItemListQuery = {}) =>
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
        header: options.lastEventId
          ? { "Last-Event-ID": options.lastEventId }
          : undefined,
      },
      headers: { Accept: "text/event-stream" },
      parseAs: "stream",
      signal: options.signal,
    }),
};

/** 将 RAG job SSE ReadableStream 解析为业务事件。 */
export function parseRAGJobEventStream(stream: ReadableStream<Uint8Array>) {
  return parseSseStream<RAGJobEvent>(stream);
}
