import type { Ref } from "vue";
import { translate as t } from "@/console/i18n";
import { getErrorMessage } from "@/console/lib/api-result";
import { normalizeProgress } from "@/console/lib/normalize";
import {
  streamRagJobEvents,
  type SourceJobViewModel,
} from "@/console/services/source-workspace";
import type {
  RAGJobCounters,
  RAGJobEvent,
  SourceItemProcessStatus,
  SourceItemRead,
  SourceRead,
} from "@/console/api/sources";

export interface SourceJobRuntimeContext {
  activeJobsBySourceUid: Ref<Record<string, SourceJobViewModel[]>>;
  itemProgressByUid: Ref<Record<string, number | null>>;
  jobProgressBySourceUid: Ref<Record<string, number | null>>;
  jobMessageBySourceUid: Ref<Record<string, string | null>>;
  jobErrorBySourceUid: Ref<Record<string, string | null>>;
  jobCountersBySourceUid: Ref<Record<string, RAGJobCounters | null>>;
  jobStreamControllersByUid: Ref<Record<string, AbortController>>;
  jobLastEventIdByUid: Ref<Record<string, string>>;
  patchSourceStatus: (sourceUid: string, status: SourceRead["status"]) => void;
  patchSourceItem: (sourceUid: string, item: SourceItemRead) => void;
  patchSourceItemStatus: (
    sourceUid: string,
    sourceItemUid: string,
    status: SourceItemProcessStatus,
  ) => void;
  refreshSourceWorkspaceInBackground: (sourceUid: string) => Promise<void>;
  reloadActiveJobs: () => Promise<SourceJobViewModel[]>;
}

// RAG Job SSE 运行时管理：流连接、进度追踪、事件应用与清理
export function createSourceJobRuntime(context: SourceJobRuntimeContext) {
  const {
    activeJobsBySourceUid,
    itemProgressByUid,
    jobCountersBySourceUid,
    jobErrorBySourceUid,
    jobLastEventIdByUid,
    jobMessageBySourceUid,
    jobProgressBySourceUid,
    jobStreamControllersByUid,
    patchSourceItem,
    patchSourceItemStatus,
    patchSourceStatus,
    refreshSourceWorkspaceInBackground,
    reloadActiveJobs,
  } = context;

  async function connectSourceJobStreams(sourceUid: string): Promise<void> {
    const jobs = activeJobsBySourceUid.value[sourceUid] ?? [];

    for (const job of jobs) {
      void connectJobStream(job);
    }
  }

  async function connectJobStream(job: SourceJobViewModel): Promise<void> {
    if (jobStreamControllersByUid.value[job.jobUid]) {
      return;
    }

    const controller = new AbortController();
    jobStreamControllersByUid.value = {
      ...jobStreamControllersByUid.value,
      [job.jobUid]: controller,
    };

    try {
      const stream = await streamRagJobEvents(job.jobUid, {
        lastEventId: jobLastEventIdByUid.value[job.jobUid],
        signal: controller.signal,
      });

      for await (const event of stream) {
        if (controller.signal.aborted) {
          break;
        }

        if (event.sseId) {
          jobLastEventIdByUid.value = {
            ...jobLastEventIdByUid.value,
            [job.jobUid]: event.sseId,
          };
        }

        applyRagJobEvent(event);
      }

      if (!controller.signal.aborted) {
        await refreshSourceWorkspaceInBackground(job.sourceUid);
        await reloadActiveJobs();
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        jobErrorBySourceUid.value = {
          ...jobErrorBySourceUid.value,
          [job.sourceUid]: getErrorMessage(
            error,
            t("sources.service.errors.streamJob"),
          ),
        };
      }
    } finally {
      const nextControllers = { ...jobStreamControllersByUid.value };
      delete nextControllers[job.jobUid];
      jobStreamControllersByUid.value = nextControllers;
    }
  }

  function disconnectJobStream(jobUid: string): void {
    jobStreamControllersByUid.value[jobUid]?.abort();

    const nextControllers = { ...jobStreamControllersByUid.value };
    delete nextControllers[jobUid];
    jobStreamControllersByUid.value = nextControllers;
  }

  function disconnectSourceJobStreams(sourceUid: string): void {
    for (const job of activeJobsBySourceUid.value[sourceUid] ?? []) {
      disconnectJobStream(job.jobUid);
    }
  }

  function disconnectAllJobStreams(): void {
    for (const jobUid of Object.keys(jobStreamControllersByUid.value)) {
      disconnectJobStream(jobUid);
    }
  }

  // 将单条 SSE 事件增量应用到 source / item 的本地状态
  function applyRagJobEvent(event: RAGJobEvent): void {
    const sourceUid = event.sourceUid;
    const sourceItemUid = event.sourceItemUid ?? event.sourceItem?.uid ?? null;
    const sourceItemStatus =
      event.sourceItemStatus ?? event.sourceItem?.status ?? null;

    if (!sourceUid) {
      return;
    }

    if (event.sourceStatus) {
      patchSourceStatus(sourceUid, event.sourceStatus);
    }

    if (event.message) {
      jobMessageBySourceUid.value = {
        ...jobMessageBySourceUid.value,
        [sourceUid]: event.message,
      };
    }

    if (event.error) {
      jobErrorBySourceUid.value = {
        ...jobErrorBySourceUid.value,
        [sourceUid]: event.error,
      };
    }

    if (event.counters) {
      jobCountersBySourceUid.value = {
        ...jobCountersBySourceUid.value,
        [sourceUid]: event.counters,
      };
    }

    if (event.sourceItem) {
      patchSourceItem(sourceUid, event.sourceItem);
    }

    if (sourceItemUid && sourceItemStatus) {
      patchSourceItemStatus(sourceUid, sourceItemUid, sourceItemStatus);
    }

    if (
      sourceItemUid &&
      event.itemProgress !== null &&
      event.itemProgress !== undefined
    ) {
      setSourceItemProgress(sourceItemUid, event.itemProgress);
    }

    if (event.syncProgress !== null && event.syncProgress !== undefined) {
      setSourceJobProgress(sourceUid, event.syncProgress);
    }
  }

  function setSourceItemProgress(
    sourceItemUid: string,
    progress: number | null,
  ): void {
    itemProgressByUid.value = {
      ...itemProgressByUid.value,
      [sourceItemUid]: normalizeProgress(progress),
    };
  }

  function setSourceJobProgress(
    sourceUid: string,
    progress: number | null,
  ): void {
    jobProgressBySourceUid.value = {
      ...jobProgressBySourceUid.value,
      [sourceUid]: normalizeProgress(progress),
    };
  }

  function clearSourceItemProgress(sourceItemUid: string): void {
    const nextProgress = { ...itemProgressByUid.value };
    delete nextProgress[sourceItemUid];
    itemProgressByUid.value = nextProgress;
  }

  function clearSourceJobRuntimeState(sourceUid: string): void {
    disconnectSourceJobStreams(sourceUid);

    const nextJobs = { ...activeJobsBySourceUid.value };
    delete nextJobs[sourceUid];
    activeJobsBySourceUid.value = nextJobs;

    const nextJobProgress = { ...jobProgressBySourceUid.value };
    delete nextJobProgress[sourceUid];
    jobProgressBySourceUid.value = nextJobProgress;

    const nextMessages = { ...jobMessageBySourceUid.value };
    delete nextMessages[sourceUid];
    jobMessageBySourceUid.value = nextMessages;

    const nextErrors = { ...jobErrorBySourceUid.value };
    delete nextErrors[sourceUid];
    jobErrorBySourceUid.value = nextErrors;

    const nextCounters = { ...jobCountersBySourceUid.value };
    delete nextCounters[sourceUid];
    jobCountersBySourceUid.value = nextCounters;
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

  return {
    applyRagJobEvent,
    clearSourceItemProgress,
    clearSourceJobRuntimeState,
    connectJobStream,
    connectSourceJobStreams,
    disconnectAllJobStreams,
    disconnectJobStream,
    disconnectSourceJobStreams,
    setSourceItemProgress,
    setSourceJobProgress,
    upsertActiveJob,
  };
}
