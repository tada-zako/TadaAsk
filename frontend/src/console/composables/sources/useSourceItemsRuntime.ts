import { computed, ref, type ComputedRef } from "vue";

import { translate as t } from "@/console/i18n";
import { getErrorMessage } from "@/console/lib/api-result";
import { normalizeProgress } from "@/console/lib/normalize";
import {
  streamRagJobEvents,
  toSourceItemRow,
  toSourceRow,
  type SourceJobViewModel,
  type SourceTone,
} from "@/console/services/source-workspace";
import { useSourceStore } from "@/console/stores/source";
import type {
  RAGJobCounters,
  RAGJobEvent,
  RAGJobIngestStage,
  SourceUpdatePayload,
} from "@/console/api/sources";

type SourceItemsRuntimeOptions = {
  sourceUid: ComputedRef<string>;
};

const STREAM_HIDE_DELAY_MS = 1200;
const ITEM_PROGRESS_SETTLE_DELAY_MS = 1000;
const TERMINAL_STREAM_EVENTS = new Set<RAGJobEvent["event"]>([
  "sync_complete",
  "sync_failed",
  "sync_paused",
]);
const TERMINAL_ITEM_EVENTS = new Set<RAGJobEvent["event"]>([
  "item_completed",
  "item_failed",
  "item_paused",
  "item_skipped",
]);

/**
 * Source items 页面运行时。
 *
 * 这里集中处理页面临时态和 SSE 事件，避免 progress 穿过 store / workspace mapper。
 */
export function useSourceItemsRuntime(options: SourceItemsRuntimeOptions) {
  const sourceStore = useSourceStore();
  // ------ 响应式变量 ------
  const searchQuery = ref("");
  const selectedItemUids = ref<string[]>([]);
  const progressByItemUid = ref<Record<string, number>>({}); // source item uid -> progress number
  const syncProgressBySourceUid = ref<Record<string, number>>({});
  const syncMessageBySourceUid = ref<Record<string, string | null>>({});
  const syncErrorBySourceUid = ref<Record<string, string | null>>({});
  const syncCountersBySourceUid = ref<Record<string, RAGJobCounters | null>>(
    {},
  );
  const syncStageBySourceUid = ref<Record<string, RAGJobIngestStage | null>>(
    {},
  );
  const syncVisibleBySourceUid = ref<Record<string, boolean>>({});
  const syncJobTypeBySourceUid = ref<
    Record<string, SourceJobViewModel["jobType"] | null>
  >({});

  const controllersByJobUid = new Map<string, AbortController>();
  const jobSourceUidByJobUid = new Map<string, string>();
  const lastEventIdByJobUid = new Map<string, string>();
  const syncHideTimersBySourceUid = new Map<
    string,
    ReturnType<typeof setTimeout>
  >();
  const progressClearTimersByItemUid = new Map<
    string,
    ReturnType<typeof setTimeout>
  >();

  // ------ 计算属性 -----
  const source = computed(() => sourceStore.getSource(options.sourceUid.value));
  const sourceRow = computed(() =>
    source.value ? toSourceRow(source.value) : null,
  );
  const rawItems = computed(() =>
    sourceStore.getSourceItems(options.sourceUid.value),
  );
  const rows = computed(() => {
    const currentSource = source.value;

    if (!currentSource) {
      return [];
    }

    return rawItems.value.map((item) =>
      toSourceItemRow(
        item,
        currentSource.sourceType,
        progressByItemUid.value[item.uid] ?? null,
      ),
    );
  });

  const filteredRows = computed(() => {
    const query = searchQuery.value.trim().toLowerCase();

    if (!query) {
      return rows.value;
    }

    return rows.value.filter((row) => {
      const values =
        source.value?.sourceType === "web_crawl"
          ? [row.title, row.originUrl, row.displayOrigin]
          : [row.title, row.filename, row.displayOrigin];

      return values.some((value) => value?.toLowerCase().includes(query));
    });
  });
  const activeJobs = computed(
    () => sourceStore.activeJobsBySourceUid[options.sourceUid.value] ?? [],
  );
  const syncJob = computed(
    () =>
      activeJobs.value.find((job) => job.jobType === "web_crawl_sync") ?? null,
  );
  const syncVisible = computed(
    () =>
      source.value?.sourceType === "web_crawl" &&
      (Boolean(syncJob.value) ||
        (syncVisibleBySourceUid.value[options.sourceUid.value] === true &&
          syncJobTypeBySourceUid.value[options.sourceUid.value] ===
            "web_crawl_sync")),
  );
  const syncProgress = computed(
    () => syncProgressBySourceUid.value[options.sourceUid.value] ?? null,
  );
  const syncStage = computed(
    () => syncStageBySourceUid.value[options.sourceUid.value] ?? null,
  );
  const syncMessage = computed(
    () =>
      syncErrorBySourceUid.value[options.sourceUid.value] ??
      syncMessageBySourceUid.value[options.sourceUid.value] ??
      "Waiting for sync events.",
  );
  const syncCounters = computed(
    () => syncCountersBySourceUid.value[options.sourceUid.value] ?? null,
  );
  const syncBadgeLabel = computed(
    () => syncJob.value?.statusLabel ?? sourceRow.value?.statusLabel ?? "Idle",
  );
  const syncBadgeTone = computed<SourceTone>(
    () => syncJob.value?.statusTone ?? sourceRow.value?.statusTone ?? "muted",
  );

  async function loadWorkspace(): Promise<void> {
    await sourceStore.loadSourceWorkspace(options.sourceUid.value);
    await sourceStore.loadActiveJobs();
    connectActiveJobs();
  }

  async function updateSource(input: SourceUpdatePayload): Promise<void> {
    await sourceStore.updateSource(options.sourceUid.value, input);
  }

  async function deleteSource(): Promise<void> {
    clearSourceRuntimeState();
    await sourceStore.deleteSource(options.sourceUid.value);
  }

  async function uploadFiles(files: File[]): Promise<void> {
    await sourceStore.uploadItems(options.sourceUid.value, files);
    await sourceStore.loadSourceWorkspace(options.sourceUid.value);
  }

  async function syncCrawl(): Promise<void> {
    const job = await sourceStore.syncWebCrawl(options.sourceUid.value);
    connectJob(job);
  }

  /** 重点函数；文档 indexing 入口 */
  async function indexItems(itemUids: string[]): Promise<void> {
    for (const itemUid of itemUids) {
      // 设置 item progress 进度条对象
      setItemProgress(itemUid, 0);
    }

    // 首先请求后端创建 RAG job，并持有返回的 job 对象
    const job = await sourceStore.indexItems(options.sourceUid.value, itemUids);
    // 建立 SSE 观察接口长连接
    connectJob(job);
  }

  async function pauseItems(itemUids: string[]): Promise<void> {
    await sourceStore.pauseItems(options.sourceUid.value, itemUids);
  }

  async function resumeItems(itemUids: string[]): Promise<void> {
    for (const itemUid of itemUids) {
      setItemProgress(itemUid, 0);
    }

    const job = await sourceStore.resumeItems(
      options.sourceUid.value,
      itemUids,
    );
    connectJob(job);
  }

  async function renameItem(itemUid: string, title: string): Promise<void> {
    await sourceStore.renameItem(options.sourceUid.value, itemUid, title);
  }

  async function deleteItems(itemUids: string[]): Promise<void> {
    for (const itemUid of itemUids) {
      await sourceStore.deleteItem(options.sourceUid.value, itemUid);
      clearItemProgress(itemUid);
    }

    selectedItemUids.value = [];
  }

  async function downloadItem(itemUid: string): Promise<void> {
    await sourceStore.downloadItem(options.sourceUid.value, itemUid);
  }

  function setSelection(itemUids: string[]): void {
    selectedItemUids.value = itemUids;
  }

  function pruneSelection(): void {
    const validItemUids = new Set(rows.value.map((row) => row.uid));
    selectedItemUids.value = selectedItemUids.value.filter((uid) =>
      validItemUids.has(uid),
    );
  }

  function resetForSourceChange(sourceUid: string): void {
    clearSourceRuntimeState(sourceUid);
    selectedItemUids.value = [];
  }

  /**
   * 清空 source item workspace 当前相关的暂存数据，并断开 SSE 连接
   */
  function clearSourceRuntimeState(sourceUid = options.sourceUid.value): void {
    disconnectSourceJobs(sourceUid);
    clearSyncHideTimer(sourceUid);

    for (const item of sourceStore.getSourceItems(sourceUid)) {
      clearItemProgress(item.uid);
    }

    deleteRefKey(syncProgressBySourceUid, sourceUid);
    deleteRefKey(syncMessageBySourceUid, sourceUid);
    deleteRefKey(syncErrorBySourceUid, sourceUid);
    deleteRefKey(syncCountersBySourceUid, sourceUid);
    deleteRefKey(syncStageBySourceUid, sourceUid);
    deleteRefKey(syncVisibleBySourceUid, sourceUid);
    deleteRefKey(syncJobTypeBySourceUid, sourceUid);
  }

  function connectActiveJobs(): void {
    for (const job of activeJobs.value) {
      connectJob(job);
    }
  }

  function connectJob(job: SourceJobViewModel): void {
    // web crawl source view 展开 sync panel 展示
    showSyncPanel(job);

    if (controllersByJobUid.has(job.jobUid)) {
      return;
    }

    // 设置 SSE 流式中断器
    const controller = new AbortController();
    controllersByJobUid.set(job.jobUid, controller);
    jobSourceUidByJobUid.set(job.jobUid, job.sourceUid);

    // 消费 SSE 流式数据
    void consumeJobStream(job, controller);
  }

  function disconnectSourceJobs(sourceUid: string): void {
    for (const [jobUid, jobSourceUid] of jobSourceUidByJobUid.entries()) {
      if (jobSourceUid === sourceUid) {
        controllersByJobUid.get(jobUid)?.abort();
        controllersByJobUid.delete(jobUid);
        jobSourceUidByJobUid.delete(jobUid);
      }
    }

    hideSyncPanel(sourceUid);
  }

  /**
   * 实际消耗 SSE 流式函数
   */
  async function consumeJobStream(
    job: SourceJobViewModel,
    controller: AbortController,
  ): Promise<void> {
    try {
      // SSE API 建立连接
      const stream = await streamRagJobEvents(job.jobUid, {
        lastEventId: lastEventIdByJobUid.get(job.jobUid),
        signal: controller.signal,
      });

      for await (const event of stream) {
        if (controller.signal.aborted) {
          break;
        }

        if (event.sseId) {
          lastEventIdByJobUid.set(job.jobUid, event.sseId);
        }

        applyJobEvent(event, job);
      }

      if (!controller.signal.aborted) {
        // SSE 流消耗完毕，并且不是由于中断，刷新页面和相关数据
        await refreshAfterStream(job.sourceUid);
        scheduleHideSyncPanel(job.sourceUid);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setRefKey(
          syncErrorBySourceUid,
          job.sourceUid,
          getErrorMessage(error, t("sources.service.errors.streamJob")),
        );
        scheduleHideSyncPanel(job.sourceUid);
      }
    } finally {
      // 清除 job 相关残余数据
      controllersByJobUid.delete(job.jobUid);
      jobSourceUidByJobUid.delete(job.jobUid);
    }
  }

  /**
   * 基于 SSE 响应的 rag job event 更新响应式变量
   */
  function applyJobEvent(event: RAGJobEvent, job: SourceJobViewModel): void {
    const sourceUid = event.sourceUid;
    const itemUid = event.sourceItemUid ?? event.sourceItem?.uid ?? null;
    const itemStatus =
      event.sourceItemStatus ?? event.sourceItem?.status ?? null;

    if (!sourceUid) {
      return;
    }

    showSyncPanel(job);

    if (event.sourceStatus) {
      sourceStore.patchSourceStatus(sourceUid, event.sourceStatus);
    }

    if (event.message) {
      setRefKey(syncMessageBySourceUid, sourceUid, event.message);
    }

    if (event.error) {
      setRefKey(syncErrorBySourceUid, sourceUid, event.error);
    }

    if (event.ingestStage) {
      setRefKey(syncStageBySourceUid, sourceUid, event.ingestStage);
    }

    if (event.counters) {
      setRefKey(syncCountersBySourceUid, sourceUid, event.counters);
    }

    if (event.sourceItem) {
      sourceStore.patchSourceItem(sourceUid, event.sourceItem);
    }

    if (itemUid && itemStatus) {
      sourceStore.patchSourceItemStatus(sourceUid, itemUid, itemStatus);
    }

    if (itemUid && event.itemProgress != null) {
      // 更新 item progress 显示
      setItemProgress(itemUid, event.itemProgress);
    }

    if (event.syncProgress != null) {
      // 更新 sync progress 显示
      setSyncProgress(sourceUid, event.syncProgress);
    }

    if (itemUid && TERMINAL_ITEM_EVENTS.has(event.event)) {
      // sse 结束
      if (event.event === "item_completed" && event.itemProgress == null) {
        // item 解析完成，更新 progress
        setItemProgress(itemUid, 1);
      }

      // 设置 progress 清理计时器，避免进度条闪烁突变；
      // 即由于立即刷新导致进度条立即移除进度条渲染
      scheduleClearItemProgress(itemUid);
    }

    if (TERMINAL_STREAM_EVENTS.has(event.event)) {
      scheduleHideSyncPanel(sourceUid);
    }
  }

  function showSyncPanel(job: SourceJobViewModel): void {
    if (job.jobType !== "web_crawl_sync") {
      return;
    }

    clearSyncHideTimer(job.sourceUid);
    setRefKey(syncJobTypeBySourceUid, job.sourceUid, job.jobType);
    setRefKey(syncVisibleBySourceUid, job.sourceUid, true);

    if (syncProgressBySourceUid.value[job.sourceUid] === undefined) {
      setSyncProgress(job.sourceUid, 0);
    }

    if (!syncMessageBySourceUid.value[job.sourceUid]) {
      setRefKey(
        syncMessageBySourceUid,
        job.sourceUid,
        t("sources.service.jobs.syncStarted"),
      );
    }
  }

  function hideSyncPanel(sourceUid: string): void {
    clearSyncHideTimer(sourceUid);
    setRefKey(syncVisibleBySourceUid, sourceUid, false);
  }

  function scheduleHideSyncPanel(sourceUid: string): void {
    clearSyncHideTimer(sourceUid);

    syncHideTimersBySourceUid.set(
      sourceUid,
      setTimeout(() => {
        setRefKey(syncVisibleBySourceUid, sourceUid, false);
        syncHideTimersBySourceUid.delete(sourceUid);
      }, STREAM_HIDE_DELAY_MS),
    );
  }

  function setItemProgress(itemUid: string, progress: number | null): void {
    const value = normalizeProgress(progress);

    if (value === null) {
      clearItemProgress(itemUid);
      return;
    }

    clearItemProgressTimer(itemUid);
    setRefKey(progressByItemUid, itemUid, value);
  }

  function clearItemProgress(itemUid: string): void {
    clearItemProgressTimer(itemUid);
    deleteRefKey(progressByItemUid, itemUid);
  }

  /**
   * 设置 progress 清空计时器
   */
  function scheduleClearItemProgress(itemUid: string): void {
    clearItemProgressTimer(itemUid);

    progressClearTimersByItemUid.set(
      itemUid,
      setTimeout(() => {
        deleteRefKey(progressByItemUid, itemUid);
        progressClearTimersByItemUid.delete(itemUid);
      }, ITEM_PROGRESS_SETTLE_DELAY_MS),
    );
  }

  function setSyncProgress(sourceUid: string, progress: number | null): void {
    const value = normalizeProgress(progress);

    if (value === null) {
      deleteRefKey(syncProgressBySourceUid, sourceUid);
      return;
    }

    setRefKey(syncProgressBySourceUid, sourceUid, value);
  }

  function clearSyncHideTimer(sourceUid: string): void {
    const timer = syncHideTimersBySourceUid.get(sourceUid);

    if (timer) {
      clearTimeout(timer);
      syncHideTimersBySourceUid.delete(sourceUid);
    }
  }

  function clearItemProgressTimer(itemUid: string): void {
    const timer = progressClearTimersByItemUid.get(itemUid);

    if (timer) {
      clearTimeout(timer);
      progressClearTimersByItemUid.delete(itemUid);
    }
  }

  /**
   * 刷新 source item workspace 状态
   */
  async function refreshAfterStream(sourceUid: string): Promise<void> {
    await sourceStore.loadSourceWorkspace(sourceUid, { silent: true });
    await sourceStore.loadActiveJobs();
  }

  return {
    clearSourceRuntimeState,
    deleteItems,
    deleteSource,
    downloadItem,
    filteredRows,
    indexItems,
    loadWorkspace,
    pauseItems,
    pruneSelection,
    renameItem,
    resetForSourceChange,
    resumeItems,
    rows,
    searchQuery,
    selectedItemUids,
    setSelection,
    source,
    sourceRow,
    syncBadgeLabel,
    syncBadgeTone,
    syncCounters,
    syncCrawl,
    syncMessage,
    syncProgress,
    syncStage,
    syncVisible,
    updateSource,
    uploadFiles,
  };
}

function setRefKey<T>(
  target: { value: Record<string, T> },
  key: string,
  value: T,
): void {
  target.value = {
    ...target.value,
    [key]: value,
  };
}

function deleteRefKey<T>(
  target: { value: Record<string, T> },
  key: string,
): void {
  const next = { ...target.value };
  delete next[key];
  target.value = next;
}
