import type {
  RAGJobRead,
  RAGJobStartResponse,
  SourceItemRead,
  SourceRead,
} from "@/console/api/sources";
import { translate as t } from "@/console/i18n";
import {
  formatDate,
  formatRelativeDate,
  type RelativeDateMessages,
} from "@/console/lib/date-format";
import { normalizeProgress } from "@/console/lib/normalize";
import {
  sourceItemStatusLabel,
  sourceItemStatusTone,
  sourceJobStatusLabel,
  sourceJobStatusTone,
  sourceStatusLabel,
  sourceStatusTone,
  sourceTypeLabel,
  sourceVisibilityLabel,
} from "./source-display";
import type {
  SourceItemRow,
  SourceItemsRouteName,
  SourceJobViewModel,
  SourceRow,
  SourceType,
  SourceWorkspaceOptions,
  SourceWorkspaceViewModel,
} from "./source-types";

// 由 source 和 items 原始数据构造详情页视图模型。
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

// 转换单个知识库为前端统一的表格行视图模型。
export function toSourceRow(source: SourceRead): SourceRow {
  return {
    uid: source.uid,
    name: source.sourceName,
    sourceType: source.sourceType,
    typeLabel: sourceTypeLabel(source.sourceType),
    isPublic: source.isPublic,
    visibilityLabel: sourceVisibilityLabel(source.isPublic),
    visibilityTone: source.isPublic ? "success" : "muted",
    status: source.status,
    statusLabel: sourceStatusLabel(source.status),
    statusTone: sourceStatusTone(source.status),
    lastUpdatedLabel: formatRelativeDate(
      source.updatedAt,
      sourceRelativeDateMessages(),
    ),
    createdLabel: formatDate(
      source.createdAt,
      t("sources.service.dates.unknown"),
    ),
    itemsRouteName: getSourceItemsRouteName(source.sourceType),
    source,
  };
}

// 转换知识库子项为前端表格行视图模型，并补充权限与状态标识。
export function toSourceItemRow(
  sourceItem: SourceItemRead,
  sourceType: SourceType,
  itemProgressByUid: Record<string, number | null | undefined> = {},
): SourceItemRow {
  const progress = normalizeProgress(itemProgressByUid[sourceItem.uid]);
  const status = sourceItem.status;
  const showProgress =
    progress !== null ||
    status === "processing" ||
    status === "pause_requested";

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
    createdLabel: formatDate(
      sourceItem.createdAt,
      t("sources.service.dates.unknown"),
    ),
    updatedLabel: formatRelativeDate(
      sourceItem.updatedAt,
      sourceRelativeDateMessages(),
    ),
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

// 转换 RAG 任务为前端任务行视图模型。
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
    createdLabel:
      "createdAt" in job
        ? formatDate(job.createdAt, t("sources.service.dates.unknown"))
        : "",
    startedLabel:
      "startedAt" in job && job.startedAt
        ? formatDate(job.startedAt, t("sources.service.dates.unknown"))
        : t("sources.service.dates.notStarted"),
    finishedLabel:
      "finishedAt" in job && job.finishedAt
        ? formatDate(job.finishedAt, t("sources.service.dates.unknown"))
        : t("sources.service.dates.notFinished"),
    error: "error" in job ? (job.error ?? null) : null,
    job,
  };
}

// 根据知识库类型返回对应的子项列表路由名称。
export function getSourceItemsRouteName(
  sourceType: SourceType,
): SourceItemsRouteName | null {
  if (sourceType === "local_file" || sourceType === "web_crawl") {
    return "source-items";
  }

  return null;
}

// 判断知识库类型是否拥有可操作的子项列表。
export function isSourceTypeWithItems(sourceType: SourceType): boolean {
  return getSourceItemsRouteName(sourceType) !== null;
}

function sourceRelativeDateMessages(): RelativeDateMessages {
  return {
    unknown: t("sources.service.dates.unknown"),
    justNow: t("sources.service.dates.justNow"),
    minutesAgo: (count: number) =>
      t("sources.service.dates.minutesAgo", { count }),
    hoursAgo: (count: number) => t("sources.service.dates.hoursAgo", { count }),
    daysAgo: (count: number) => t("sources.service.dates.daysAgo", { count }),
  };
}
