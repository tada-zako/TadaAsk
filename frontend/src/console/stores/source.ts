import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { translate as t } from "@/console/i18n";
import { getErrorMessage } from "@/console/lib/api-result";
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
import { createSourceEntityState } from "@/console/stores/sources/source-entity-state";
import { createSourceJobRuntime } from "@/console/stores/sources/source-job-runtime";
import { createSourceSelectionState } from "@/console/stores/sources/source-selection-state";
import type {
  IngestPausedResponse,
  RAGJobCounters,
  RAGJobStartResponse,
  SourceDeleteResponse,
  SourceItemDeleteResponse,
  SourceItemDownloadResponse,
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
  // SSE 事件流实时数据字段
  const jobMessageBySourceUid = ref<Record<string, string | null>>({});
  const jobErrorBySourceUid = ref<Record<string, string | null>>({});
  const jobCountersBySourceUid = ref<Record<string, RAGJobCounters | null>>({});
  // SSE 流控制：每个 job 一个 AbortController，支持断连与重连
  const jobStreamControllersByUid = ref<Record<string, AbortController>>({});
  // SSE Last-Event-ID，用于断线重连时续传
  const jobLastEventIdByUid = ref<Record<string, string>>({});
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

  const selectionState = createSourceSelectionState({
    selectedItemUidsBySourceUid,
  });
  const entityState = createSourceEntityState({
    currentSource,
    itemsBySourceUid,
    pruneItemSelection: selectionState.pruneItemSelection,
    sources,
  });
  const jobRuntime = createSourceJobRuntime({
    activeJobsBySourceUid,
    itemProgressByUid,
    jobCountersBySourceUid,
    jobErrorBySourceUid,
    jobLastEventIdByUid,
    jobMessageBySourceUid,
    jobProgressBySourceUid,
    jobStreamControllersByUid,
    patchSourceItem: entityState.patchSourceItem,
    patchSourceItemStatus: entityState.patchSourceItemStatus,
    patchSourceStatus: entityState.patchSourceStatus,
    refreshSourceWorkspaceInBackground,
    reloadActiveJobs: loadActiveJobs,
  });

  const { clearItemSelection, setItemSelection, toggleItemSelection } =
    selectionState;
  const {
    patchSourceItem,
    patchSourceItemStatus,
    patchSourceItems,
    patchSourceStatus,
    removeSourceFromState,
    removeSourceItemFromState,
    setSourceItems,
    syncCurrentSourceFromList,
    upsertSource,
  } = entityState;
  const {
    applyRagJobEvent,
    clearSourceItemProgress,
    connectJobStream,
    connectSourceJobStreams,
    disconnectAllJobStreams,
    disconnectJobStream,
    disconnectSourceJobStreams,
    setSourceItemProgress,
    setSourceJobProgress,
    upsertActiveJob,
  } = jobRuntime;

  // --- 异步动作 ---
  /** 加载并初始化所有知识库列表 */
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
      clearSourceRuntimeState(sourceUid);
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
      patchSourceItems(sourceUid, uploadedItems);
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

  // 触发 web_crawl 同步任务，写入活跃任务并连接 SSE 进度流
  async function syncWebCrawl(sourceUid: string): Promise<RAGJobStartResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const job = await syncWebCrawlSource(sourceUid);
      const jobView = toSourceJobViewModel(job);
      patchSourceStatus(sourceUid, "processing");
      setSourceJobProgress(sourceUid, 0);
      jobMessageBySourceUid.value = {
        ...jobMessageBySourceUid.value,
        [sourceUid]: t("sources.service.jobs.syncStarted"),
      };
      upsertActiveJob(jobView);
      void connectJobStream(jobView);
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

  // 对选中子项启动索引，写入活跃任务并连接 SSE 进度流
  async function indexItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<RAGJobStartResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const job = await indexSourceItemsRequest(sourceUid, sourceItemUids);
      const jobView = toSourceJobViewModel(job);
      markSourceItemsStatus(sourceUid, sourceItemUids, "processing", 0);
      patchSourceStatus(sourceUid, "processing");
      upsertActiveJob(jobView);
      void connectJobStream(jobView);
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

  // 暂停指定子项的索引处理，并立即将返回的处理状态 patch 到本地
  async function pauseItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<IngestPausedResponse[]> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      markSourceItemsStatus(sourceUid, sourceItemUids, "pause_requested");
      const pausedItems = await pauseSourceItemsRequest(
        sourceUid,
        sourceItemUids,
      );
      for (const item of pausedItems) {
        patchSourceItemStatus(
          sourceUid,
          item.sourceItemUid,
          item.processStatus,
        );
      }
      return pausedItems;
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

  // 恢复已暂停子项的索引，写入活跃任务并连接 SSE 进度流
  async function resumeItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<RAGJobStartResponse> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      const job = await resumeSourceItemsRequest(sourceUid, sourceItemUids);
      const jobView = toSourceJobViewModel(job);
      markSourceItemsStatus(sourceUid, sourceItemUids, "processing", 0);
      patchSourceStatus(sourceUid, "processing");
      upsertActiveJob(jobView);
      void connectJobStream(jobView);
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
      clearSourceItemProgress(sourceItemUid);
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

  function clearSourceRuntimeState(sourceUid: string): void {
    clearItemSelection(sourceUid);
    jobRuntime.clearSourceJobRuntimeState(sourceUid);
  }

  // SSE 流结束后静默刷新 workspace 数据，同步最新状态
  async function refreshSourceWorkspaceInBackground(
    sourceUid: string,
  ): Promise<void> {
    const workspace = await loadSourceWorkspaceRequest(sourceUid, {
      itemProgressByUid: itemProgressByUid.value,
    });

    upsertSource(workspace.source);
    if (currentSource.value?.uid === sourceUid) {
      currentSource.value = workspace.source;
    }
    setSourceItems(
      sourceUid,
      workspace.sourceItemRows.map((row) => row.sourceItem),
    );
  }

  function markSourceItemsStatus(
    sourceUid: string,
    sourceItemUids: string[],
    status: SourceItemRead["status"],
    progress?: number,
  ): void {
    entityState.markSourceItemsStatus(
      sourceUid,
      sourceItemUids,
      status,
      progress !== undefined
        ? (sourceItemUid) => setSourceItemProgress(sourceItemUid, progress)
        : undefined,
    );
  }

  return {
    activeJobsBySourceUid,
    applyRagJobEvent,
    clearItemSelection,
    clearSourceRuntimeState,
    connectJobStream,
    connectSourceJobStreams,
    createSource,
    currentSource,
    currentSourceItems,
    currentWorkspace,
    deleteItem,
    deleteSource,
    disconnectAllJobStreams,
    disconnectJobStream,
    disconnectSourceJobStreams,
    downloadItem,
    errorMessage,
    indexItems,
    isLoading,
    isMutating,
    itemProgressByUid,
    itemsBySourceUid,
    jobCountersBySourceUid,
    jobErrorBySourceUid,
    jobLastEventIdByUid,
    jobMessageBySourceUid,
    jobProgressBySourceUid,
    jobStreamControllersByUid,
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
