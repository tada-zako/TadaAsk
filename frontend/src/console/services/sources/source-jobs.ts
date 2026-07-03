import {
  parseRAGJobEventStream,
  sourceApi,
  type IngestPausedResponse,
  type RAGJobEvent,
  type RAGJobStartResponse,
  type StreamRAGJobEventsOptions,
} from "@/console/api/sources";
import { translate as t } from "@/console/i18n";
import { unwrapApiData } from "@/console/lib/api-result";
import { toSourceJobViewModel } from "./source-mappers";
import type { SourceJobViewModel } from "./source-types";

// 触发 web_crawl 类型知识库的抓取同步任务。
export async function syncWebCrawlSource(
  sourceUid: string,
): Promise<RAGJobStartResponse> {
  const { data, error } = await sourceApi.syncWebCrawl(sourceUid);

  return unwrapApiData(data, error, t("sources.service.errors.syncWebCrawl"));
}

// 对指定子项启动索引后台任务。
export async function indexSourceItems(
  sourceUid: string,
  sourceItemUids: string[],
): Promise<RAGJobStartResponse> {
  const { data, error } = await sourceApi.indexDocuments(
    sourceUid,
    sourceItemUids,
  );

  return unwrapApiData(data, error, t("sources.service.errors.indexItems"));
}

// 请求暂停正在处理中的子项索引任务。
export async function pauseSourceItems(
  sourceUid: string,
  sourceItemUids: string[],
): Promise<IngestPausedResponse[]> {
  const { data, error } = await sourceApi.pauseIngest(
    sourceUid,
    sourceItemUids,
  );

  return unwrapApiData(data, error, t("sources.service.errors.pauseItems"));
}

// 恢复已暂停子项的索引后台任务。
export async function resumeSourceItems(
  sourceUid: string,
  sourceItemUids: string[],
): Promise<RAGJobStartResponse> {
  const { data, error } = await sourceApi.resumeIngest(
    sourceUid,
    sourceItemUids,
  );

  return unwrapApiData(data, error, t("sources.service.errors.resumeItems"));
}

// 获取当前所有活跃 RAG 任务，并转为视图模型列表。
export async function listActiveSourceJobs(): Promise<SourceJobViewModel[]> {
  const { data, error } = await sourceApi.listActiveJobs();
  const response = unwrapApiData(
    data,
    error,
    t("sources.service.errors.loadJobs"),
  );

  return (response.jobs ?? []).map(toSourceJobViewModel);
}

// 获取指定 RAG 任务详情并转为视图模型。
export async function getSourceJob(
  jobUid: string,
): Promise<SourceJobViewModel> {
  const { data, error } = await sourceApi.getJob(jobUid);
  const job = unwrapApiData(data, error, t("sources.service.errors.loadJob"));

  return toSourceJobViewModel(job);
}

// 连接 SSE 事件流，解析并流式返回 RAG Job 进度事件。
export async function streamRagJobEvents(
  jobUid: string,
  options: StreamRAGJobEventsOptions = {},
): Promise<AsyncGenerator<RAGJobEvent, void, unknown>> {
  const { data, error } = await sourceApi.streamJobEvents(jobUid, options);
  const stream = unwrapApiData(
    data ?? undefined,
    error,
    t("sources.service.errors.streamJob"),
  );

  return parseRAGJobEventStream(stream as ReadableStream<Uint8Array>);
}
