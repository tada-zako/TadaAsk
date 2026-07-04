import {
  sourceApi,
  type SourceCreatePayload,
  type SourceDeleteResponse,
  type SourceItemDeleteResponse,
  type SourceItemDownloadResponse,
  type SourceItemRead,
  type SourceItemRenamePayload,
  type SourceRead,
  type SourceUpdatePayload,
} from "@/console/api/sources";
import { translate as t } from "@/console/i18n";
import { unwrapApiData } from "@/console/lib/api-result";
import { normalizeOptionalText } from "@/console/lib/normalize";
import { createSourceWorkspaceViewModel, toSourceRow } from "./source-mappers";
import type {
  CreateSourceInput,
  SourceListWorkspaceViewModel,
  SourceWorkspaceViewModel,
} from "./source-types";

// 拉取所有知识库，组装列表页视图模型。
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

// 获取知识库详情及子项列表并组装为 Workspace 视图模型。
export async function loadSourceWorkspace(
  sourceUid: string,
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

  return createSourceWorkspaceViewModel(source, sourceItems);
}

// 仅拉取指定知识库的子项列表，不包含 source 详情。
export async function loadSourceItems(
  sourceUid: string,
): Promise<SourceItemRead[]> {
  const { data, error } = await sourceApi.listItems(sourceUid, {
    limit: 100,
    offset: 0,
  });

  return unwrapApiData(data, error, t("sources.service.errors.loadItems"));
}

// 创建单个 Source，并触发后端保存流程。
export async function createSource(
  input: CreateSourceInput,
): Promise<SourceRead> {
  const { data, error } = await sourceApi.create(
    normalizeCreateSourceInput(input),
  );

  return unwrapApiData(data, error, t("sources.service.errors.createSource"));
}

// 更新指定数据源，PATCH 局部提交机制。
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

// 物理删除数据源，级联清理所有子项。
export async function deleteSource(
  sourceUid: string,
): Promise<SourceDeleteResponse> {
  const { data, error } = await sourceApi.remove(sourceUid);

  return unwrapApiData(data, error, t("sources.service.errors.deleteSource"));
}

// 上传文件到 local_file 类型知识库。
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

// 重命名知识库子项（local_file 同步更新文件名）。
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

// 删除知识库子项，触发向量/文件清理。
export async function deleteSourceItem(
  sourceUid: string,
  sourceItemUid: string,
): Promise<SourceItemDeleteResponse> {
  const { data, error } = await sourceApi.deleteItem(sourceUid, sourceItemUid);

  return unwrapApiData(data, error, t("sources.service.errors.deleteItem"));
}

// 获取 local_file 子项下载地址并通过动态 <a> 元素触发浏览器下载。
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

// 补齐创建载荷缺省字段并 trim 文本值。
function normalizeCreateSourceInput(
  input: CreateSourceInput,
): SourceCreatePayload {
  return {
    ...input,
    sourceName: input.sourceName.trim(),
    status: "pending", // 创建时不允许自定义 status。
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
