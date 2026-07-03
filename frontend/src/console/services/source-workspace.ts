import {
  parseRAGJobEventStream,
  sourceApi,
  type IngestPausedResponse,
  type RAGJobEvent,
  type RAGJobRead,
  type RAGJobStartResponse,
  type SourceCreatePayload,
  type SourceDeleteResponse,
  type SourceItemDeleteResponse,
  type SourceItemDownloadResponse,
  type SourceItemProcessStatus,
  type SourceItemRead,
  type SourceItemRenamePayload,
  type SourceProcessStatus,
  type SourceRead,
  type SourceUpdatePayload,
  type StreamRAGJobEventsOptions,
} from "@/console/api/sources";
import { translate as t } from "@/console/i18n";
import type { components } from "@/shared/api/generated/schema";

export type SourceType = SourceRead["sourceType"];
export type SourceTone = "success" | "warning" | "danger" | "muted";
export type SourceItemsRouteName =
  "source-local-file-items" | "source-web-crawl-items";
export type RAGJobStatus = components["schemas"]["RAGJobStatus"];
export type RAGJobType = components["schemas"]["RAGJobType"];
export type WebCrawlConfigInput = components["schemas"]["WebCrawlConfig-Input"];
export type WebCrawlConfigOutput =
  components["schemas"]["WebCrawlConfig-Output"];

// 创建数据源的表单输入载荷
export type CreateSourceInput = Omit<SourceCreatePayload, "status">;

// 知识库管理主列表中的行数据结构
export interface SourceRow {
  uid: string;
  name: string;
  sourceType: SourceType;
  typeLabel: string;
  isPublic: boolean;
  visibilityLabel: string;
  visibilityTone: "success" | "muted";
  status: SourceProcessStatus;
  statusLabel: string;
  statusTone: SourceTone;
  lastUpdatedLabel: string;
  createdLabel: string;
  itemsRouteName: SourceItemsRouteName | null;
  source: SourceRead;
}

// 知识库详情子项列表行展示模型
export interface SourceItemRow {
  uid: string;
  title: string;
  sourceType: SourceType;
  filename: string | null;
  originUrl: string | null;
  displayOrigin: string; // 优先展示 url，无 url 展示文件名
  status: SourceItemProcessStatus;
  statusLabel: string;
  statusTone: SourceTone;
  createdLabel: string;
  updatedLabel: string;
  progress: number | null;
  showProgress: boolean;
  canIndex: boolean;
  canPause: boolean;
  canResume: boolean;
  canRename: boolean;
  canDelete: boolean;
  canDownload: boolean;
  sourceItem: SourceItemRead;
}

export interface SourceListWorkspaceViewModel {
  sources: SourceRead[];
  sourceRows: SourceRow[];
}

export interface SourceWorkspaceViewModel {
  source: SourceRead;
  sourceRow: SourceRow;
  sourceItemRows: SourceItemRow[];
}

export interface SourceJobViewModel {
  jobUid: string;
  jobType: RAGJobType;
  sourceUid: string;
  sourceItemUids: string[];
  status: RAGJobStatus;
  statusLabel: string;
  statusTone: SourceTone;
  createdLabel: string;
  startedLabel: string;
  finishedLabel: string;
  error: string | null;
  job: RAGJobRead | RAGJobStartResponse;
}

export interface SourceWorkspaceOptions {
  itemProgressByUid?: Record<string, number | null | undefined>;
}

/**
 * 统一 API 响应解包处理，避免组件和 store 反复处理 openapi-fetch 形态。
 */
function unwrapApiData<T>(
  data: T | undefined,
  error: unknown,
  fallbackMessage: string,
): T {
  if (error) {
    throw new Error(getApiErrorMessage(error, fallbackMessage));
  }

  if (data === undefined) {
    throw new Error(fallbackMessage);
  }

  return data;
}

// 解析 FastAPI 错误结构，支持 string 和数组详情
function getApiErrorMessage(error: unknown, fallbackMessage: string): string {
  if (!error || typeof error !== "object") {
    return fallbackMessage;
  }

  if ("detail" in error) {
    const detail = error.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String(item.msg)
            : String(item),
        )
        .join(", ");
    }
  }

  return fallbackMessage;
}

// 拉取所有知识库，组装列表页视图模型
export async function loadSourcesWorkspace(): Promise<SourceListWorkspaceViewModel> {
  const { data, error } = await sourceApi.list({ limit: 100, offset: 0 });
  const sources = unwrapApiData(
    data,
    error,
    t("sources.service.errors.loadSources"),
  );

  return {
    sources,
    sourceRows: sources.map(toSourceRow),
  };
}

// 获取知识库详情及子项列表并组装为 Workspace 视图模型
export async function loadSourceWorkspace(
  sourceUid: string,
  options: SourceWorkspaceOptions = {},
): Promise<SourceWorkspaceViewModel> {
  const [sourceResult, itemsResult] = await Promise.all([
    sourceApi.get(sourceUid),
    sourceApi.listItems(sourceUid, { limit: 100, offset: 0 }),
  ]);

  const source = unwrapApiData(
    sourceResult.data,
    sourceResult.error,
    t("sources.service.errors.loadSource"),
  );
  const sourceItems = unwrapApiData(
    itemsResult.data,
    itemsResult.error,
    t("sources.service.errors.loadItems"),
  );

  return createSourceWorkspaceViewModel(source, sourceItems, options);
}

// 仅拉取指定知识库的子项列表，不包含 source 详情
export async function loadSourceItems(
  sourceUid: string,
): Promise<SourceItemRead[]> {
  const { data, error } = await sourceApi.listItems(sourceUid, {
    limit: 100,
    offset: 0,
  });

  return unwrapApiData(data, error, t("sources.service.errors.loadItems"));
}

// 创建单个 Source，并触发后端保存流程
export async function createSource(
  input: CreateSourceInput,
): Promise<SourceRead> {
  const { data, error } = await sourceApi.create(
    normalizeCreateSourceInput(input),
  );

  return unwrapApiData(data, error, t("sources.service.errors.createSource"));
}

// 更新指定数据源，PATCH 局部提交机制
export async function updateSource(
  sourceUid: string,
  input: SourceUpdatePayload,
): Promise<SourceRead> {
  const { data, error } = await sourceApi.update(
    sourceUid,
    normalizeSourceUpdatePayload(input),
  );

  return unwrapApiData(data, error, t("sources.service.errors.updateSource"));
}

// 物理删除数据源，级联清理所有子项
export async function deleteSource(
  sourceUid: string,
): Promise<SourceDeleteResponse> {
  const { data, error } = await sourceApi.remove(sourceUid);

  return unwrapApiData(data, error, t("sources.service.errors.deleteSource"));
}

// 上传文件到 local_file 类型知识库
export async function uploadLocalSourceItems(
  sourceUid: string,
  files: File[],
  signal?: AbortSignal,
): Promise<SourceItemRead[]> {
  const { data, error } = await sourceApi.uploadItems(
    sourceUid,
    { files },
    signal,
  );

  return unwrapApiData(data, error, t("sources.service.errors.uploadItems"));
}

// 重命名知识库子项（local_file 同步更新文件名）
export async function renameSourceItem(
  sourceUid: string,
  sourceItemUid: string,
  title: string,
): Promise<SourceItemRead> {
  const payload: SourceItemRenamePayload = { title: title.trim() };
  const { data, error } = await sourceApi.renameItem(
    sourceUid,
    sourceItemUid,
    payload,
  );

  return unwrapApiData(data, error, t("sources.service.errors.renameItem"));
}

// 删除知识库子项，触发向量/文件清理
export async function deleteSourceItem(
  sourceUid: string,
  sourceItemUid: string,
): Promise<SourceItemDeleteResponse> {
  const { data, error } = await sourceApi.deleteItem(sourceUid, sourceItemUid);

  return unwrapApiData(data, error, t("sources.service.errors.deleteItem"));
}

// 获取 local_file 子项下载地址并通过动态 <a> 元素触发浏览器下载
export async function downloadSourceItem(
  sourceUid: string,
  sourceItemUid: string,
): Promise<SourceItemDownloadResponse> {
  const { data, error } = await sourceApi.getItemDownload(
    sourceUid,
    sourceItemUid,
  );
  const download = unwrapApiData(
    data,
    error,
    t("sources.service.errors.downloadItem"),
  );

  if (typeof document !== "undefined") {
    const link = document.createElement("a");
    link.href = download.downloadUrl;
    link.download = download.filename;
    document.body.append(link);
    link.click();
    link.remove();
  }

  return download;
}

// 触发 web_crawl 类型知识库的抓取同步任务
export async function syncWebCrawlSource(
  sourceUid: string,
): Promise<RAGJobStartResponse> {
  const { data, error } = await sourceApi.syncWebCrawl(sourceUid);

  return unwrapApiData(data, error, t("sources.service.errors.syncWebCrawl"));
}

// 对指定子项启动索引后台任务
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

// 请求暂停正在处理中的子项索引任务
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

// 恢复已暂停子项的索引后台任务
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

// 获取当前所有活跃 RAG 任务，并转为视图模型列表
export async function listActiveSourceJobs(): Promise<SourceJobViewModel[]> {
  const { data, error } = await sourceApi.listActiveJobs();
  const response = unwrapApiData(
    data,
    error,
    t("sources.service.errors.loadJobs"),
  );

  return (response.jobs ?? []).map(toSourceJobViewModel);
}

// 获取指定 RAG 任务详情并转为视图模型
export async function getSourceJob(
  jobUid: string,
): Promise<SourceJobViewModel> {
  const { data, error } = await sourceApi.getJob(jobUid);
  const job = unwrapApiData(data, error, t("sources.service.errors.loadJob"));

  return toSourceJobViewModel(job);
}

// 连接 SSE 事件流，解析并流式返回 RAG Job 进度事件
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

  // 调用 SSE Parse Helper 处理 stream
  return parseRAGJobEventStream(stream as ReadableStream<Uint8Array>);
}

// 由 source 和 items 原始数据构造详情页视图模型
export function createSourceWorkspaceViewModel(
  source: SourceRead,
  sourceItems: SourceItemRead[],
  options: SourceWorkspaceOptions = {},
): SourceWorkspaceViewModel {
  return {
    source,
    sourceRow: toSourceRow(source),
    sourceItemRows: sourceItems.map((item) =>
      toSourceItemRow(item, source.sourceType, options.itemProgressByUid),
    ),
  };
}

// 转换单个知识库为前端统一的表格行视图模型 (ViewModel)
export function toSourceRow(source: SourceRead): SourceRow {
  return {
    uid: source.uid,
    name: source.sourceName,
    sourceType: source.sourceType,
    typeLabel: sourceTypeLabel(source.sourceType),
    isPublic: source.isPublic,
    visibilityLabel: source.isPublic
      ? t("sources.service.visibility.public")
      : t("sources.service.visibility.private"),
    visibilityTone: source.isPublic ? "success" : "muted",
    status: source.status,
    statusLabel: sourceStatusLabel(source.status),
    statusTone: sourceStatusTone(source.status),
    lastUpdatedLabel: formatRelativeDate(source.updatedAt),
    createdLabel: formatDate(source.createdAt),
    itemsRouteName: getSourceItemsRouteName(source.sourceType),
    source,
  };
}

// 转换知识库子项为前端表格行视图模型，并补充权限与状态标识
export function toSourceItemRow(
  sourceItem: SourceItemRead,
  sourceType: SourceType,
  itemProgressByUid: Record<string, number | null | undefined> = {},
): SourceItemRow {
  const progress = normalizeProgress(itemProgressByUid[sourceItem.uid]);
  const status = sourceItem.status;
  const showProgress = status === "processing" || status === "pause_requested";

  return {
    uid: sourceItem.uid,
    title: sourceItem.title,
    sourceType,
    filename: sourceItem.filename ?? null,
    originUrl: sourceItem.originUrl ?? null,
    displayOrigin:
      sourceItem.originUrl ??
      sourceItem.filename ??
      t("sources.service.items.originUnknown"),
    status,
    statusLabel: sourceItemStatusLabel(status),
    statusTone: sourceItemStatusTone(status),
    createdLabel: formatDate(sourceItem.createdAt),
    updatedLabel: formatRelativeDate(sourceItem.updatedAt),
    progress,
    showProgress,
    canIndex:
      status === "pending" || status === "failed" || status === "completed",
    canPause: status === "processing",
    canResume: status === "paused",
    canRename: status !== "processing" && status !== "pause_requested",
    canDelete: status !== "processing" && status !== "pause_requested",
    canDownload: sourceType === "local_file" && Boolean(sourceItem.storageKey),
    sourceItem,
  };
}

// 转换 RAG 任务为前端任务行视图模型
export function toSourceJobViewModel(
  job: RAGJobRead | RAGJobStartResponse,
): SourceJobViewModel {
  return {
    jobUid: job.jobUid,
    jobType: job.jobType,
    sourceUid: job.sourceUid,
    sourceItemUids: job.sourceItemUids ?? [],
    status: job.status,
    statusLabel: sourceJobStatusLabel(job.status),
    statusTone: sourceJobStatusTone(job.status),
    createdLabel: "createdAt" in job ? formatDate(job.createdAt) : "",
    startedLabel:
      "startedAt" in job && job.startedAt
        ? formatDate(job.startedAt)
        : t("sources.service.dates.notStarted"),
    finishedLabel:
      "finishedAt" in job && job.finishedAt
        ? formatDate(job.finishedAt)
        : t("sources.service.dates.notFinished"),
    error: "error" in job ? (job.error ?? null) : null,
    job,
  };
}

// 根据知识库类型返回对应的子项列表路由名称
export function getSourceItemsRouteName(
  sourceType: SourceType,
): SourceItemsRouteName | null {
  if (sourceType === "local_file") {
    return "source-local-file-items";
  }

  if (sourceType === "web_crawl") {
    return "source-web-crawl-items";
  }

  return null;
}

// 判断知识库类型是否拥有可操作的子项列表
export function isSourceTypeWithItems(sourceType: SourceType): boolean {
  return getSourceItemsRouteName(sourceType) !== null;
}

// 补齐创建载荷缺省字段并 trim 文本值
function normalizeCreateSourceInput(
  input: CreateSourceInput,
): SourceCreatePayload {
  return {
    ...input,
    sourceName: input.sourceName.trim(),
    status: "pending", // 创建时不允许自定义 status
    isPublic: input.isPublic,
    syncInterval: input.syncInterval ?? null,
    webCrawlConfig: input.webCrawlConfig ?? null,
  };
}

function normalizeSourceUpdatePayload(
  input: SourceUpdatePayload,
): SourceUpdatePayload {
  const payload: SourceUpdatePayload = {};

  // PATCH 只提交显式存在字段，避免把未修改字段覆盖成 null。
  if ("sourceName" in input) {
    payload.sourceName = normalizeOptionalText(input.sourceName);
  }

  if ("isPublic" in input) {
    payload.isPublic = input.isPublic;
  }

  if ("webCrawlConfig" in input) {
    payload.webCrawlConfig = input.webCrawlConfig ?? null;
  }

  return payload;
}

// --- 展示标签 & 状态色调映射 ---
function sourceTypeLabel(sourceType: SourceType): string {
  const labels: Record<SourceType, string> = {
    custom_content: t("sources.service.sourceType.custom_content"),
    github_repo: t("sources.service.sourceType.github_repo"),
    local_file: t("sources.service.sourceType.local_file"),
    web_crawl: t("sources.service.sourceType.web_crawl"),
  };

  return labels[sourceType];
}

function sourceStatusLabel(status: SourceProcessStatus): string {
  const labels: Record<SourceProcessStatus, string> = {
    completed: t("sources.service.sourceStatus.completed"),
    failed: t("sources.service.sourceStatus.failed"),
    pause_requested: t("sources.service.sourceStatus.pause_requested"),
    paused: t("sources.service.sourceStatus.paused"),
    pending: t("sources.service.sourceStatus.pending"),
    processing: t("sources.service.sourceStatus.processing"),
  };

  return labels[status];
}

function sourceItemStatusLabel(status: SourceItemProcessStatus): string {
  const labels: Record<SourceItemProcessStatus, string> = {
    completed: t("sources.service.itemStatus.completed"),
    failed: t("sources.service.itemStatus.failed"),
    pause_requested: t("sources.service.itemStatus.pause_requested"),
    paused: t("sources.service.itemStatus.paused"),
    pending: t("sources.service.itemStatus.pending"),
    processing: t("sources.service.itemStatus.processing"),
  };

  return labels[status];
}

function sourceJobStatusLabel(status: RAGJobStatus): string {
  const labels: Record<RAGJobStatus, string> = {
    cancelled: t("sources.service.jobStatus.cancelled"),
    completed: t("sources.service.jobStatus.completed"),
    failed: t("sources.service.jobStatus.failed"),
    queued: t("sources.service.jobStatus.queued"),
    running: t("sources.service.jobStatus.running"),
  };

  return labels[status];
}

function sourceStatusTone(status: SourceProcessStatus): SourceTone {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  if (status === "processing" || status === "pause_requested") {
    return "warning";
  }

  return "muted";
}

function sourceItemStatusTone(status: SourceItemProcessStatus): SourceTone {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  if (status === "processing" || status === "pause_requested") {
    return "warning";
  }

  return "muted";
}

function sourceJobStatusTone(status: RAGJobStatus): SourceTone {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed" || status === "cancelled") {
    return "danger";
  }

  if (status === "queued" || status === "running") {
    return "warning";
  }

  return "muted";
}

// 可选文本规范化：空字符串/undefined 统一为 null
function normalizeOptionalText(
  value: string | null | undefined,
): string | null {
  if (value === undefined) {
    return null;
  }

  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

// 规范化进度值（0-100 整数），非法值返回 null
// 后端可能返回 0-1 小数或 0-100 整数，统一按 ≤1 判别并放大
function normalizeProgress(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }

  const normalized = value <= 1 ? value * 100 : value;
  return Math.min(100, Math.max(0, Math.round(normalized)));
}

// 格式化绝对日期（如 "15 Jan 2026"）
function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return t("sources.service.dates.unknown");
  }

  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// 格式化相对时间，如：刚刚、xx分钟前、xx小时前等
function formatRelativeDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return t("sources.service.dates.unknown");
  }

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.round(diffMs / 60_000));

  if (diffMinutes < 1) {
    return t("sources.service.dates.justNow");
  }

  if (diffMinutes < 60) {
    return t("sources.service.dates.minutesAgo", { count: diffMinutes });
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return t("sources.service.dates.hoursAgo", { count: diffHours });
  }

  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 8) {
    return t("sources.service.dates.daysAgo", { count: diffDays });
  }

  return formatDate(value);
}
