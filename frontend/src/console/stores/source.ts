import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { translate as t } from "@/console/i18n";
import {
  createSource as createSourceRequest,
  createSourceWorkspaceViewModel,
  deleteSource as deleteSourceRequest,
  deleteSourceItem as deleteSourceItemRequest,
  downloadSourceItem as downloadSourceItemRequest,
  indexSourceItems as indexSourceItemsRequest,
  listActiveSourceJobs,
  loadSourceItems as loadSourceItemsRequest,
  loadSourcesWorkspace,
  loadSourceWorkspace as loadSourceWorkspaceRequest,
  pauseSourceItems as pauseSourceItemsRequest,
  renameSourceItem as renameSourceItemRequest,
  resumeSourceItems as resumeSourceItemsRequest,
  syncWebCrawlSource,
  toSourceJobViewModel,
  toSourceRow,
  updateSource as updateSourceRequest,
  uploadLocalSourceItems,
  type CreateSourceInput,
  type SourceJobViewModel,
  type SourceWorkspaceViewModel,
} from "@/console/services/source-workspace";
import type {
  IngestPausedResponse,
  RAGJobEvent,
  RAGJobStartResponse,
  SourceDeleteResponse,
  SourceItemDeleteResponse,
  SourceItemDownloadResponse,
  SourceItemProcessStatus,
  SourceItemRead,
  SourceRead,
  SourceUpdatePayload,
} from "@/console/api/sources";

/**
 * Source 共享状态。
 *
 * Store 管理 source 跨页面数据、选中态、任务进度；字段转换和 API 解包交给 service。
 */
export const useSourceStore = defineStore("console-source", () => {
  // --- 响应式状态 ---
  const sources = ref<SourceRead[]>([]);
  const currentSource = ref<SourceRead | null>(null);
  const itemsBySourceUid = ref<Record<string, SourceItemRead[]>>({});
  const selectedItemUidsBySourceUid = ref<Record<string, string[]>>({});
  const activeJobsBySourceUid = ref<Record<string, SourceJobViewModel[]>>({});
  const itemProgressByUid = ref<Record<string, number | null>>({});
  const jobProgressBySourceUid = ref<Record<string, number | null>>({});
  const isLoading = ref(false);
  const isMutating = ref(false);
  const errorMessage = ref<string | null>(null);

  // --- 派生计算 ---
  const sourceRows = computed(() => sources.value.map(toSourceRow));

  const currentSourceItems = computed(() =>
    currentSource.value
      ? (itemsBySourceUid.value[currentSource.value.uid] ?? [])
      : [],
  );

  const currentWorkspace = computed<SourceWorkspaceViewModel | null>(() =>
    currentSource.value
      ? createSourceWorkspaceViewModel(
          currentSource.value,
          currentSourceItems.value,
          { itemProgressByUid: itemProgressByUid.value },
        )
      : null,
  );

  // --- 异步动作 ---
  // 加载并初始化所有知识库列表
  async function loadSources(): Promise<SourceRead[]> {
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const workspace = await loadSourcesWorkspace();
      sources.value = workspace.sources;
      syncCurrentSourceFromList();
      return workspace.sources;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.loadSources"),
      );
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

  // 刷新知识库列表（loadSources 的快捷别名）
  async function refreshSources(): Promise<SourceRead[]> {
    return await loadSources();
  }

  // 加载知识库详情及子项，写入共享状态
  async function loadSourceWorkspace(
    sourceUid: string,
  ): Promise<SourceWorkspaceViewModel> {
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const workspace = await loadSourceWorkspaceRequest(sourceUid, {
        itemProgressByUid: itemProgressByUid.value,
      });
      upsertSource(workspace.source);
      currentSource.value = workspace.source;
      setSourceItems(
        sourceUid,
        workspace.sourceItemRows.map((row) => row.sourceItem),
      );
      return workspace;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.loadSource"),
      );
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

  // 仅加载子项（不包含 source 详情），写入共享状态
  async function loadSourceItems(sourceUid: string): Promise<SourceItemRead[]> {
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const items = await loadSourceItemsRequest(sourceUid);
      setSourceItems(sourceUid, items);
      return items;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.loadItems"),
      );
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

  // 创建知识库并 push 到本地列表
  async function createSource(input: CreateSourceInput): Promise<SourceRead> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const source = await createSourceRequest(input);
      upsertSource(source);
      return source;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.createSource"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 更新知识库并同步到本地列表
  async function updateSource(
    sourceUid: string,
    input: SourceUpdatePayload,
  ): Promise<SourceRead> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const source = await updateSourceRequest(sourceUid, input);
      upsertSource(source);
      return source;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.updateSource"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 删除知识库并从本地状态移除
  async function deleteSource(
    sourceUid: string,
  ): Promise<SourceDeleteResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const response = await deleteSourceRequest(sourceUid);
      removeSourceFromState(sourceUid);
      return response;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.deleteSource"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 上传本地文件到指定的知识库
  async function uploadItems(
    sourceUid: string,
    files: File[],
  ): Promise<SourceItemRead[]> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const uploadedItems = await uploadLocalSourceItems(sourceUid, files);
      setSourceItems(
        sourceUid,
        mergeSourceItems(
          itemsBySourceUid.value[sourceUid] ?? [],
          uploadedItems,
        ),
      );
      return uploadedItems;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.uploadItems"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 触发 web_crawl 同步任务，并将返回的 job 写入活跃任务状态
  async function syncWebCrawl(sourceUid: string): Promise<RAGJobStartResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const job = await syncWebCrawlSource(sourceUid);
      upsertActiveJob(toSourceJobViewModel(job));
      return job;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.syncWebCrawl"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 对选中子项启动索引，并将返回的 job 写入活跃任务状态
  async function indexItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<RAGJobStartResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const job = await indexSourceItemsRequest(sourceUid, sourceItemUids);
      upsertActiveJob(toSourceJobViewModel(job));
      return job;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.indexItems"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 暂停指定子项的索引处理
  async function pauseItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<IngestPausedResponse[]> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      return await pauseSourceItemsRequest(sourceUid, sourceItemUids);
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.pauseItems"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 恢复已暂停子项的索引，并将返回的 job 写入活跃任务状态
  async function resumeItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<RAGJobStartResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const job = await resumeSourceItemsRequest(sourceUid, sourceItemUids);
      upsertActiveJob(toSourceJobViewModel(job));
      return job;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.resumeItems"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 重命名子项并局部更新本地状态
  async function renameItem(
    sourceUid: string,
    sourceItemUid: string,
    title: string,
  ): Promise<SourceItemRead> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const item = await renameSourceItemRequest(
        sourceUid,
        sourceItemUid,
        title,
      );
      patchSourceItem(sourceUid, item);
      return item;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.renameItem"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 删除子项并从本地状态移除
  async function deleteItem(
    sourceUid: string,
    sourceItemUid: string,
  ): Promise<SourceItemDeleteResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const response = await deleteSourceItemRequest(sourceUid, sourceItemUid);
      removeSourceItemFromState(sourceUid, sourceItemUid);
      return response;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.deleteItem"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 触发 local_file 子项下载（service 层处理浏览器窗口打开）
  async function downloadItem(
    sourceUid: string,
    sourceItemUid: string,
  ): Promise<SourceItemDownloadResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      return await downloadSourceItemRequest(sourceUid, sourceItemUid);
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.downloadItem"),
      );
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  // 加载所有活跃 RAG 任务并按 sourceUid 分组存储
  async function loadActiveJobs(): Promise<SourceJobViewModel[]> {
    errorMessage.value = null;

    try {
      const jobs = await listActiveSourceJobs();
      activeJobsBySourceUid.value = jobs.reduce<
        Record<string, SourceJobViewModel[]>
      >((result, job) => {
        result[job.sourceUid] = [...(result[job.sourceUid] ?? []), job];
        return result;
      }, {});
      return jobs;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.loadJobs"),
      );
      throw error;
    }
  }

  // 应用 RAG 任务增量 SSE 事件，局部更新知识库及子项的状态与进度
  function applyRagJobEvent(event: RAGJobEvent): void {
    if (event.sourceStatus) {
      patchSourceStatus(event.sourceUid, event.sourceStatus);
    }

    if (event.sourceItem) {
      patchSourceItem(event.sourceUid, event.sourceItem);
    } else if (event.sourceItemUid && event.sourceItemStatus) {
      patchSourceItemStatus(
        event.sourceUid,
        event.sourceItemUid,
        event.sourceItemStatus,
      );
    }

    if (
      event.sourceItemUid &&
      event.itemProgress !== null &&
      event.itemProgress !== undefined
    ) {
      setSourceItemProgress(event.sourceItemUid, event.itemProgress);
    }

    if (event.syncProgress !== null && event.syncProgress !== undefined) {
      setSourceJobProgress(event.sourceUid, event.syncProgress);
    }
  }

  // --- 选中态管理 ---
  function setItemSelection(sourceUid: string, sourceItemUids: string[]): void {
    selectedItemUidsBySourceUid.value = {
      ...selectedItemUidsBySourceUid.value,
      [sourceUid]: Array.from(new Set(sourceItemUids)),
    };
  }

  // 切换单个子项的选中/取消选中
  function toggleItemSelection(sourceUid: string, sourceItemUid: string): void {
    const current = selectedItemUidsBySourceUid.value[sourceUid] ?? [];
    const next = current.includes(sourceItemUid)
      ? current.filter((uid) => uid !== sourceItemUid)
      : [...current, sourceItemUid];

    setItemSelection(sourceUid, next);
  }

  // 清除指定知识库下的所有子项选中状态
  function clearItemSelection(sourceUid: string): void {
    const next = { ...selectedItemUidsBySourceUid.value };
    delete next[sourceUid];
    selectedItemUidsBySourceUid.value = next;
  }

  // 更新指定子项的实时处理进度
  function setSourceItemProgress(
    sourceItemUid: string,
    progress: number | null,
  ): void {
    itemProgressByUid.value = {
      ...itemProgressByUid.value,
      [sourceItemUid]: normalizeProgress(progress),
    };
  }

  // 更新知识库层级的任务同步进度
  function setSourceJobProgress(
    sourceUid: string,
    progress: number | null,
  ): void {
    jobProgressBySourceUid.value = {
      ...jobProgressBySourceUid.value,
      [sourceUid]: normalizeProgress(progress),
    };
  }

  // 清除指定知识库的运行时临时数据（选中、活跃任务、任务进度）
  function clearSourceRuntimeState(sourceUid: string): void {
    clearItemSelection(sourceUid);

    const nextJobs = { ...activeJobsBySourceUid.value };
    delete nextJobs[sourceUid];
    activeJobsBySourceUid.value = nextJobs;

    const nextJobProgress = { ...jobProgressBySourceUid.value };
    delete nextJobProgress[sourceUid];
    jobProgressBySourceUid.value = nextJobProgress;
  }

  // --- 内部状态变更 ---
  // 插入或更新知识库（存在则替换，否则前插）
  function upsertSource(source: SourceRead): void {
    const index = sources.value.findIndex((item) => item.uid === source.uid);

    if (index === -1) {
      sources.value = [source, ...sources.value];
    } else {
      sources.value = sources.value.map((item) =>
        item.uid === source.uid ? source : item,
      );
    }

    if (currentSource.value?.uid === source.uid) {
      currentSource.value = source;
    }
  }

  // 移除知识库及其关联子项、运行时数据
  function removeSourceFromState(sourceUid: string): void {
    sources.value = sources.value.filter((source) => source.uid !== sourceUid);

    if (currentSource.value?.uid === sourceUid) {
      currentSource.value = null;
    }

    const nextItems = { ...itemsBySourceUid.value };
    delete nextItems[sourceUid];
    itemsBySourceUid.value = nextItems;
    clearSourceRuntimeState(sourceUid);
  }

  // 用 sources 主列表同步 currentSource 引用（列表刷新后保持一致性）
  function syncCurrentSourceFromList(): void {
    if (!currentSource.value) {
      return;
    }

    currentSource.value =
      sources.value.find((source) => source.uid === currentSource.value?.uid) ??
      null;
  }

  // 设置知识库子项列表，并清理已不存在的选中项
  function setSourceItems(sourceUid: string, items: SourceItemRead[]): void {
    itemsBySourceUid.value = {
      ...itemsBySourceUid.value,
      [sourceUid]: items,
    };

    const validItemUids = new Set(items.map((item) => item.uid));
    const selected = selectedItemUidsBySourceUid.value[sourceUid] ?? [];
    setItemSelection(
      sourceUid,
      selected.filter((uid) => validItemUids.has(uid)),
    );
  }

  // 局部更新知识库状态
  function patchSourceStatus(
    sourceUid: string,
    status: SourceRead["status"],
  ): void {
    const patch = (source: SourceRead): SourceRead =>
      source.uid === sourceUid ? { ...source, status } : source;

    sources.value = sources.value.map(patch);

    if (currentSource.value?.uid === sourceUid) {
      currentSource.value = patch(currentSource.value);
    }
  }

  // 合并单个子项到本地列表（存在则替换）
  function patchSourceItem(sourceUid: string, item: SourceItemRead): void {
    setSourceItems(
      sourceUid,
      mergeSourceItems(itemsBySourceUid.value[sourceUid] ?? [], [item]),
    );
  }

  // 局部更新子项处理状态
  function patchSourceItemStatus(
    sourceUid: string,
    sourceItemUid: string,
    status: SourceItemProcessStatus,
  ): void {
    const current = itemsBySourceUid.value[sourceUid] ?? [];
    setSourceItems(
      sourceUid,
      current.map((item) =>
        item.uid === sourceItemUid ? { ...item, status } : item,
      ),
    );
  }

  // 从本地状态移除子项，并清理其进度
  function removeSourceItemFromState(
    sourceUid: string,
    sourceItemUid: string,
  ): void {
    setSourceItems(
      sourceUid,
      (itemsBySourceUid.value[sourceUid] ?? []).filter(
        (item) => item.uid !== sourceItemUid,
      ),
    );

    const nextProgress = { ...itemProgressByUid.value };
    delete nextProgress[sourceItemUid];
    itemProgressByUid.value = nextProgress;
  }

  // 插入或更新活跃任务（存在则替换，否则追加）
  function upsertActiveJob(job: SourceJobViewModel): void {
    const current = activeJobsBySourceUid.value[job.sourceUid] ?? [];
    const next = current.some((item) => item.jobUid === job.jobUid)
      ? current.map((item) => (item.jobUid === job.jobUid ? job : item))
      : [...current, job];

    activeJobsBySourceUid.value = {
      ...activeJobsBySourceUid.value,
      [job.sourceUid]: next,
    };
  }

  return {
    activeJobsBySourceUid,
    applyRagJobEvent,
    clearItemSelection,
    clearSourceRuntimeState,
    createSource,
    currentSource,
    currentSourceItems,
    currentWorkspace,
    deleteItem,
    deleteSource,
    downloadItem,
    errorMessage,
    indexItems,
    isLoading,
    isMutating,
    itemProgressByUid,
    itemsBySourceUid,
    jobProgressBySourceUid,
    loadActiveJobs,
    loadSourceItems,
    loadSourceWorkspace,
    loadSources,
    pauseItems,
    refreshSources,
    renameItem,
    resumeItems,
    selectedItemUidsBySourceUid,
    setItemSelection,
    setSourceItemProgress,
    setSourceJobProgress,
    sourceRows,
    sources,
    syncWebCrawl,
    toggleItemSelection,
    updateSource,
    uploadItems,
  };
});

// 合并子项更新列表：已存在的替换，新增的追加到末尾
function mergeSourceItems(
  current: SourceItemRead[],
  updates: SourceItemRead[],
): SourceItemRead[] {
  const updateMap = new Map(updates.map((item) => [item.uid, item]));
  const merged = current.map((item) => updateMap.get(item.uid) ?? item);
  const currentUidSet = new Set(current.map((item) => item.uid));
  const appended = updates.filter((item) => !currentUidSet.has(item.uid));

  return [...merged, ...appended];
}

// 规范化进度值（0-100 整数），非法值返回 null
function normalizeProgress(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }

  return Math.min(100, Math.max(0, Math.round(value)));
}

// 从 unknown 错误中提取可读消息
function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
