import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { translate as t } from "@/console/i18n";
import { getErrorMessage } from "@/console/lib/api-result";
import {
  createSource as createSourceRequest,
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
  SourceDeleteResponse,
  SourceItemDeleteResponse,
  SourceItemDownloadResponse,
  SourceItemProcessStatus,
  SourceItemRead,
  SourceRead,
  SourceUpdatePayload,
} from "@/console/api/sources";

type SourceItemsByUid = Record<string, SourceItemRead[]>;
type SourceJobsByUid = Record<string, SourceJobViewModel[]>;
type LoadOptions = {
  silent?: boolean;
};

/**
 * Source 共享实体缓存。
 *
 * Store 只负责跨页面需要复用的 source / item / active job 数据，以及薄请求动作。
 * 页面选择态、SSE 连接、进度条和 stream 展示状态放到 view/composable 内管理。
 */
export const useSourceStore = defineStore("console-source", () => {
  const sources = ref<SourceRead[]>([]);
  const itemsBySourceUid = ref<SourceItemsByUid>({});
  const activeJobsBySourceUid = ref<SourceJobsByUid>({});
  const isLoading = ref(false);
  const isMutating = ref(false);
  const errorMessage = ref<string | null>(null);

  const sourceRows = computed(() => sources.value.map(toSourceRow));

  async function loadSources(): Promise<SourceRead[]> {
    return await withLoading(
      t("sources.service.errors.loadSources"),
      async () => {
        const workspace = await loadSourcesWorkspace();
        sources.value = workspace.sources;
        return workspace.sources;
      },
    );
  }

  async function loadSourceWorkspace(
    sourceUid: string,
    options: LoadOptions = {},
  ): Promise<SourceWorkspaceViewModel> {
    return await withLoading(
      t("sources.service.errors.loadSource"),
      async () => {
        const workspace = await loadSourceWorkspaceRequest(sourceUid);
        upsertSource(workspace.source);
        setSourceItems(
          sourceUid,
          workspace.sourceItemRows.map((row) => row.sourceItem),
        );
        return workspace;
      },
      options,
    );
  }

  async function loadSourceItems(sourceUid: string): Promise<SourceItemRead[]> {
    return await withLoading(
      t("sources.service.errors.loadItems"),
      async () => {
        const items = await loadSourceItemsRequest(sourceUid);
        setSourceItems(sourceUid, items);
        return items;
      },
    );
  }

  async function createSource(input: CreateSourceInput): Promise<SourceRead> {
    return await withMutation(
      t("sources.service.errors.createSource"),
      async () => {
        const source = await createSourceRequest(input);
        upsertSource(source);
        return source;
      },
    );
  }

  async function updateSource(
    sourceUid: string,
    input: SourceUpdatePayload,
  ): Promise<SourceRead> {
    return await withMutation(
      t("sources.service.errors.updateSource"),
      async () => {
        const source = await updateSourceRequest(sourceUid, input);
        upsertSource(source);
        return source;
      },
    );
  }

  async function deleteSource(
    sourceUid: string,
  ): Promise<SourceDeleteResponse> {
    return await withMutation(
      t("sources.service.errors.deleteSource"),
      async () => {
        const response = await deleteSourceRequest(sourceUid);
        removeSourceFromState(sourceUid);
        return response;
      },
    );
  }

  async function uploadItems(
    sourceUid: string,
    files: File[],
  ): Promise<SourceItemRead[]> {
    return await withMutation(
      t("sources.service.errors.uploadItems"),
      async () => {
        const uploadedItems = await uploadLocalSourceItems(sourceUid, files);
        patchSourceItems(sourceUid, uploadedItems);
        return uploadedItems;
      },
    );
  }

  async function syncWebCrawl(sourceUid: string): Promise<SourceJobViewModel> {
    return await withMutation(
      t("sources.service.errors.syncWebCrawl"),
      async () => {
        const response = await syncWebCrawlSource(sourceUid);
        const job = toSourceJobViewModel(response);
        patchSourceStatus(sourceUid, "processing");
        upsertActiveJob(job);
        return job;
      },
    );
  }

  async function indexItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<SourceJobViewModel> {
    return await withMutation(
      t("sources.service.errors.indexItems"),
      async () => {
        const response = await indexSourceItemsRequest(
          sourceUid,
          sourceItemUids,
        );
        const job = toSourceJobViewModel(response);
        markSourceItemsStatus(sourceUid, sourceItemUids, "processing");
        patchSourceStatus(sourceUid, "processing");
        upsertActiveJob(job);
        return job;
      },
    );
  }

  async function pauseItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<IngestPausedResponse[]> {
    return await withMutation(
      t("sources.service.errors.pauseItems"),
      async () => {
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
      },
    );
  }

  async function resumeItems(
    sourceUid: string,
    sourceItemUids: string[],
  ): Promise<SourceJobViewModel> {
    return await withMutation(
      t("sources.service.errors.resumeItems"),
      async () => {
        const response = await resumeSourceItemsRequest(
          sourceUid,
          sourceItemUids,
        );
        const job = toSourceJobViewModel(response);
        markSourceItemsStatus(sourceUid, sourceItemUids, "processing");
        patchSourceStatus(sourceUid, "processing");
        upsertActiveJob(job);
        return job;
      },
    );
  }

  async function renameItem(
    sourceUid: string,
    sourceItemUid: string,
    title: string,
  ): Promise<SourceItemRead> {
    return await withMutation(
      t("sources.service.errors.renameItem"),
      async () => {
        const item = await renameSourceItemRequest(
          sourceUid,
          sourceItemUid,
          title,
        );
        patchSourceItem(sourceUid, item);
        return item;
      },
    );
  }

  async function deleteItem(
    sourceUid: string,
    sourceItemUid: string,
  ): Promise<SourceItemDeleteResponse> {
    return await withMutation(
      t("sources.service.errors.deleteItem"),
      async () => {
        const response = await deleteSourceItemRequest(
          sourceUid,
          sourceItemUid,
        );
        removeSourceItemFromState(sourceUid, sourceItemUid);
        return response;
      },
    );
  }

  async function downloadItem(
    sourceUid: string,
    sourceItemUid: string,
  ): Promise<SourceItemDownloadResponse> {
    return await withMutation(
      t("sources.service.errors.downloadItem"),
      async () => await downloadSourceItemRequest(sourceUid, sourceItemUid),
    );
  }

  async function loadActiveJobs(): Promise<SourceJobViewModel[]> {
    errorMessage.value = null;

    try {
      const jobs = await listActiveSourceJobs();
      activeJobsBySourceUid.value = groupJobsBySourceUid(jobs);
      return jobs;
    } catch (error) {
      errorMessage.value = getErrorMessage(
        error,
        t("sources.service.errors.loadJobs"),
      );
      throw error;
    }
  }

  function getSource(sourceUid: string): SourceRead | null {
    return sources.value.find((source) => source.uid === sourceUid) ?? null;
  }

  function getSourceItems(sourceUid: string): SourceItemRead[] {
    return itemsBySourceUid.value[sourceUid] ?? [];
  }

  function upsertSource(source: SourceRead): void {
    const exists = sources.value.some((item) => item.uid === source.uid);

    sources.value = exists
      ? sources.value.map((item) => (item.uid === source.uid ? source : item))
      : [source, ...sources.value];
  }

  function removeSourceFromState(sourceUid: string): void {
    sources.value = sources.value.filter((source) => source.uid !== sourceUid);

    const nextItems = { ...itemsBySourceUid.value };
    delete nextItems[sourceUid];
    itemsBySourceUid.value = nextItems;

    const nextJobs = { ...activeJobsBySourceUid.value };
    delete nextJobs[sourceUid];
    activeJobsBySourceUid.value = nextJobs;
  }

  function setSourceItems(sourceUid: string, items: SourceItemRead[]): void {
    itemsBySourceUid.value = {
      ...itemsBySourceUid.value,
      [sourceUid]: items,
    };
  }

  function patchSourceStatus(
    sourceUid: string,
    status: SourceRead["status"],
  ): void {
    sources.value = sources.value.map((source) =>
      source.uid === sourceUid ? { ...source, status } : source,
    );
  }

  function patchSourceItem(sourceUid: string, item: SourceItemRead): void {
    patchSourceItems(sourceUid, [item]);
  }

  function patchSourceItems(sourceUid: string, items: SourceItemRead[]): void {
    setSourceItems(
      sourceUid,
      mergeSourceItems(itemsBySourceUid.value[sourceUid] ?? [], items),
    );
  }

  function patchSourceItemStatus(
    sourceUid: string,
    sourceItemUid: string,
    status: SourceItemProcessStatus,
  ): void {
    setSourceItems(
      sourceUid,
      getSourceItems(sourceUid).map((item) =>
        item.uid === sourceItemUid ? { ...item, status } : item,
      ),
    );
  }

  function removeSourceItemFromState(
    sourceUid: string,
    sourceItemUid: string,
  ): void {
    setSourceItems(
      sourceUid,
      getSourceItems(sourceUid).filter((item) => item.uid !== sourceItemUid),
    );
  }

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

  function removeActiveJob(sourceUid: string, jobUid: string): void {
    const nextJobs = (activeJobsBySourceUid.value[sourceUid] ?? []).filter(
      (job) => job.jobUid !== jobUid,
    );
    const next = { ...activeJobsBySourceUid.value };

    if (nextJobs.length) {
      next[sourceUid] = nextJobs;
    } else {
      delete next[sourceUid];
    }

    activeJobsBySourceUid.value = next;
  }

  function markSourceItemsStatus(
    sourceUid: string,
    sourceItemUids: string[],
    status: SourceItemProcessStatus,
  ): void {
    const targetUids = new Set(sourceItemUids);

    setSourceItems(
      sourceUid,
      getSourceItems(sourceUid).map((item) =>
        targetUids.has(item.uid) ? { ...item, status } : item,
      ),
    );
  }

  async function withLoading<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
    options: LoadOptions = {},
  ): Promise<T> {
    if (!options.silent) {
      isLoading.value = true;
    }
    errorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      errorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      if (!options.silent) {
        isLoading.value = false;
      }
    }
  }

  async function withMutation<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
  ): Promise<T> {
    isMutating.value = true;
    errorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      errorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  return {
    activeJobsBySourceUid,
    createSource,
    deleteItem,
    deleteSource,
    downloadItem,
    errorMessage,
    getSource,
    getSourceItems,
    indexItems,
    isLoading,
    isMutating,
    itemsBySourceUid,
    loadActiveJobs,
    loadSourceItems,
    loadSourceWorkspace,
    loadSources,
    patchSourceItem,
    patchSourceItemStatus,
    patchSourceItems,
    patchSourceStatus,
    pauseItems,
    removeActiveJob,
    renameItem,
    resumeItems,
    setSourceItems,
    sourceRows,
    sources,
    syncWebCrawl,
    updateSource,
    uploadItems,
    upsertActiveJob,
    upsertSource,
  };
});

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

function groupJobsBySourceUid(
  jobs: SourceJobViewModel[],
): Record<string, SourceJobViewModel[]> {
  return jobs.reduce<Record<string, SourceJobViewModel[]>>((result, job) => {
    result[job.sourceUid] = [...(result[job.sourceUid] ?? []), job];
    return result;
  }, {});
}
