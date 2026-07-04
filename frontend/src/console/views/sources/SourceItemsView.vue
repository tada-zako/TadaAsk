<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useRoute, useRouter } from "vue-router";

import { Badge } from "@/shared/components/ui/badge";
import { Progress } from "@/shared/components/ui/progress";

import SourceItemsTablePanel from "@/console/components/sources/SourceItemsTablePanel.vue";
import SourceItemsToolbar from "@/console/components/sources/SourceItemsToolbar.vue";
import { useSourceStore } from "@/console/stores/source";
import { getSourceItemsRouteName } from "@/console/services/source-workspace";
import type { SourceTone } from "@/console/services/source-workspace";
import type { SourceUpdatePayload } from "@/console/api/sources";

type SourceItemsToolbarType = "local-file" | "web-crawl";

// 统一 source item 工作区：页面差异由后端 sourceType 决定，而不是由路由拆分决定。
const route = useRoute();
const router = useRouter();
const sourceStore = useSourceStore();
const {
  activeJobsBySourceUid,
  currentWorkspace,
  errorMessage,
  isLoading,
  isMutating,
  jobCountersBySourceUid,
  jobErrorBySourceUid,
  jobMessageBySourceUid,
  jobProgressBySourceUid,
  jobStageBySourceUid,
  jobStreamTypeBySourceUid,
  jobStreamVisibleBySourceUid,
  selectedItemUidsBySourceUid,
} = storeToRefs(sourceStore);

const searchQuery = ref("");
const sourceUid = computed(() => String(route.params.sourceUid ?? ""));
const source = computed(() => currentWorkspace.value?.source ?? null);
const sourceRow = computed(() => currentWorkspace.value?.sourceRow ?? null);
const itemRows = computed(() => currentWorkspace.value?.sourceItemRows ?? []);
const isWebCrawl = computed(() => source.value?.sourceType === "web_crawl");
const toolbarSourceType = computed<SourceItemsToolbarType>(() =>
  isWebCrawl.value ? "web-crawl" : "local-file",
);
const selectedItemUids = computed(
  () => selectedItemUidsBySourceUid.value[sourceUid.value] ?? [],
);
const activeJobs = computed(
  () => activeJobsBySourceUid.value[sourceUid.value] ?? [],
);
const syncJob = computed(
  () =>
    activeJobs.value.find((job) => job.jobType === "web_crawl_sync") ?? null,
);
const syncStreamVisible = computed(
  () =>
    isWebCrawl.value &&
    (Boolean(syncJob.value) ||
      (jobStreamVisibleBySourceUid.value[sourceUid.value] === true &&
        jobStreamTypeBySourceUid.value[sourceUid.value] === "web_crawl_sync")),
);
const jobProgress = computed(
  () => jobProgressBySourceUid.value[sourceUid.value] ?? null,
);
const jobStage = computed(
  () => jobStageBySourceUid.value[sourceUid.value] ?? null,
);
const jobMessage = computed(
  () =>
    jobErrorBySourceUid.value[sourceUid.value] ??
    jobMessageBySourceUid.value[sourceUid.value] ??
    "Waiting for sync events.",
);
const jobCounters = computed(
  () => jobCountersBySourceUid.value[sourceUid.value] ?? null,
);
const syncBadgeLabel = computed(
  () => syncJob.value?.statusLabel ?? sourceRow.value?.statusLabel ?? "Idle",
);
const syncBadgeTone = computed<SourceTone>(
  () => syncJob.value?.statusTone ?? sourceRow.value?.statusTone ?? "muted",
);
const sourceKicker = computed(() => {
  if (isWebCrawl.value) {
    return "Web crawl source";
  }

  if (source.value?.sourceType === "local_file") {
    return "Local file source";
  }

  return "Source items";
});
const sourceSubtitle = computed(() =>
  isWebCrawl.value
    ? "Sync configured crawl targets to create source items, then index selected pages."
    : "Upload files, review generated source items, and index items when ready.",
);

const filteredRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();

  if (!query) {
    return itemRows.value;
  }

  return itemRows.value.filter((row) => {
    const values = isWebCrawl.value
      ? [row.title, row.originUrl, row.displayOrigin]
      : [row.title, row.filename, row.displayOrigin];

    return values.some((value) => value?.toLowerCase().includes(query));
  });
});

watch(
  sourceUid,
  (uid, oldUid) => {
    if (oldUid) {
      sourceStore.disconnectSourceJobStreams(oldUid);
    }

    void loadWorkspace(uid);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (sourceUid.value) {
    sourceStore.disconnectSourceJobStreams(sourceUid.value);
  }
});

async function loadWorkspace(uid: string): Promise<void> {
  if (!uid) {
    await router.replace({ name: "sources" });
    return;
  }

  const workspace = await sourceStore.loadSourceWorkspace(uid);

  if (!getSourceItemsRouteName(workspace.source.sourceType)) {
    await router.replace({ name: "sources" });
    return;
  }

  await sourceStore.loadActiveJobs();
  await sourceStore.connectSourceJobStreams(uid);
}

async function handleUpdateSource(input: SourceUpdatePayload): Promise<void> {
  if (!sourceUid.value) {
    return;
  }

  await sourceStore.updateSource(sourceUid.value, input);
}

async function handleDeleteSource(): Promise<void> {
  if (!sourceUid.value) {
    return;
  }

  await sourceStore.deleteSource(sourceUid.value);
  await router.push({ name: "sources" });
}

async function handleUploadFiles(files: File[]): Promise<void> {
  if (!sourceUid.value || isWebCrawl.value) {
    return;
  }

  await sourceStore.uploadItems(sourceUid.value, files);
  await sourceStore.loadSourceWorkspace(sourceUid.value);
}

async function handleSyncCrawl(): Promise<void> {
  if (!sourceUid.value || !isWebCrawl.value) {
    return;
  }

  await sourceStore.syncWebCrawl(sourceUid.value);
}

function handleSelectionChange(itemUids: string[]): void {
  sourceStore.setItemSelection(sourceUid.value, itemUids);
}

async function handleIndexItems(itemUids: string[]): Promise<void> {
  await sourceStore.indexItems(sourceUid.value, itemUids);
}

async function handlePauseItems(itemUids: string[]): Promise<void> {
  await sourceStore.pauseItems(sourceUid.value, itemUids);
}

async function handleResumeItems(itemUids: string[]): Promise<void> {
  await sourceStore.resumeItems(sourceUid.value, itemUids);
}

async function handleRenameItem(itemUid: string, title: string): Promise<void> {
  await sourceStore.renameItem(sourceUid.value, itemUid, title);
}

async function handleDeleteItems(itemUids: string[]): Promise<void> {
  for (const itemUid of itemUids) {
    await sourceStore.deleteItem(sourceUid.value, itemUid);
  }

  sourceStore.clearItemSelection(sourceUid.value);
}

async function handleDownloadItem(itemUid: string): Promise<void> {
  if (isWebCrawl.value) {
    return;
  }

  await sourceStore.downloadItem(sourceUid.value, itemUid);
}

function badgeClass(tone: SourceTone): string {
  if (tone === "success") {
    return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  }

  if (tone === "warning") {
    return "border-yellow-300/25 bg-yellow-300/10 text-yellow-100";
  }

  if (tone === "danger") {
    return "border-red-400/25 bg-red-400/10 text-red-100";
  }

  return "border-(--line-soft) bg-(--surface-panel) text-(--text-muted)";
}
</script>

<template>
  <section class="console-page">
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">{{ sourceKicker }}</p>
        <h1 class="console-page-title">
          {{ source?.sourceName ?? "Loading source" }}
        </h1>
        <p class="console-page-subtitle">
          {{ sourceSubtitle }}
          <span v-if="sourceRow">
            Updated {{ sourceRow.lastUpdatedLabel }}.
          </span>
        </p>
      </div>

      <!-- search + source items 创建按钮 -->
      <SourceItemsToolbar
        v-model:search-query="searchQuery"
        :is-mutating="isMutating"
        :source="source"
        :source-type="toolbarSourceType"
        @delete-source="handleDeleteSource"
        @sync-crawl="handleSyncCrawl"
        @update-source="handleUpdateSource"
        @upload-files="handleUploadFiles"
      />
    </header>

    <!-- 错误展示 -->
    <p
      v-if="errorMessage"
      class="rounded-(--console-radius-md) border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-100"
    >
      {{ errorMessage }}
    </p>

    <!-- web crawl 进度展示 -->
    <section
      v-if="syncStreamVisible"
      class="grid gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-4"
    >
      <div class="flex items-center justify-between gap-4 max-[760px]:grid">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <strong class="text-sm text-(--text-strong)">Sync stream</strong>
            <span
              v-if="jobStage"
              class="rounded-(--console-radius-xs) border border-(--line-soft) px-1.5 py-0.5 text-[11px] text-(--text-faint)"
            >
              {{ jobStage }}
            </span>
          </div>
          <p class="mt-1 text-xs text-(--text-faint)">
            {{ jobMessage }}
          </p>
        </div>
        <Badge :class="badgeClass(syncBadgeTone)">
          {{ syncBadgeLabel }}
        </Badge>
      </div>

      <div v-if="jobProgress !== null" class="flex items-center gap-3">
        <Progress
          class="h-1.5 bg-(--surface-panel)"
          :model-value="jobProgress"
        />
        <span class="w-10 text-right text-xs text-(--text-faint)">
          {{ jobProgress }}%
        </span>
      </div>

      <div
        v-if="jobCounters"
        class="grid grid-cols-4 gap-2 text-xs text-(--text-faint) max-[760px]:grid-cols-2"
      >
        <span>Discovered {{ jobCounters.discovered }}</span>
        <span>Fetched {{ jobCounters.fetched }}</span>
        <span>Completed {{ jobCounters.completed }}</span>
        <span>Failed {{ jobCounters.failed }}</span>
      </div>
    </section>

    <!-- source item 列表 -->
    <SourceItemsTablePanel
      :is-loading="isLoading"
      :is-mutating="isMutating"
      :rows="filteredRows"
      :selected-item-uids="selectedItemUids"
      :source-type="toolbarSourceType"
      @delete-items="handleDeleteItems"
      @download-item="handleDownloadItem"
      @index-items="handleIndexItems"
      @pause-items="handlePauseItems"
      @rename-item="handleRenameItem"
      @resume-items="handleResumeItems"
      @update-selection="handleSelectionChange"
    />
  </section>
</template>
