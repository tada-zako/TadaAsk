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

// 路由与 Store 绑定（含 SSE 实时流字段）
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
  selectedItemUidsBySourceUid,
} = storeToRefs(sourceStore);

const searchQuery = ref("");
const sourceUid = computed(() => String(route.params.sourceUid ?? ""));
const source = computed(() => currentWorkspace.value?.source ?? null);
const sourceRow = computed(() => currentWorkspace.value?.sourceRow ?? null);
const itemRows = computed(() => currentWorkspace.value?.sourceItemRows ?? []);
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
const jobProgress = computed(
  () => jobProgressBySourceUid.value[sourceUid.value] ?? null,
);
// SSE 消息展示优先级：error > message > 默认文案
const jobMessage = computed(
  () =>
    jobErrorBySourceUid.value[sourceUid.value] ??
    jobMessageBySourceUid.value[sourceUid.value] ??
    "No active crawl or indexing job.",
);
// 爬取计数器（discovered / fetched / completed / failed）
const jobCounters = computed(
  () => jobCountersBySourceUid.value[sourceUid.value] ?? null,
);
// 搜索过滤：匹配 title、originUrl、displayOrigin
const filteredRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();

  if (!query) {
    return itemRows.value;
  }

  return itemRows.value.filter((row) =>
    [row.title, row.originUrl, row.displayOrigin].some((value) =>
      value?.toLowerCase().includes(query),
    ),
  );
});
// 同步状态徽标：优先展示活跃 job 状态，其次 source 状态，兜底 Idle
const syncBadgeLabel = computed(
  () => syncJob.value?.statusLabel ?? sourceRow.value?.statusLabel ?? "Idle",
);
const syncBadgeTone = computed<SourceTone>(
  () => syncJob.value?.statusTone ?? sourceRow.value?.statusTone ?? "muted",
);

// 监听路由参数变化，切换知识库时断开旧连接并加载新数据
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

// 组件卸载时断开该知识库的 SSE 连接
onBeforeUnmount(() => {
  if (sourceUid.value) {
    sourceStore.disconnectSourceJobStreams(sourceUid.value);
  }
});

// 加载 workspace，若非 web_crawl 类型则重定向到正确的路由
async function loadWorkspace(uid: string): Promise<void> {
  if (!uid) {
    await router.replace({ name: "sources" });
    return;
  }

  const workspace = await sourceStore.loadSourceWorkspace(uid);

  if (workspace.source.sourceType !== "web_crawl") {
    const routeName = getSourceItemsRouteName(workspace.source.sourceType);
    await router.replace(
      routeName
        ? { name: routeName, params: { sourceUid: uid } }
        : { name: "sources" },
    );
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

async function handleSyncCrawl(): Promise<void> {
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

// 状态徽标色调映射
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
  <!-- 网页爬取数据源的页面项管理工作区 -->
  <section class="console-page">
    <!-- 页面头部：展示数据源名称、描述及同步/设置操作 -->
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">Web crawl source</p>
        <h1 class="console-page-title">
          {{ source?.sourceName ?? "Loading source" }}
        </h1>
        <p class="console-page-subtitle">
          Sync configured crawl targets to create source items, then index
          selected pages.
          <span v-if="sourceRow"
            >Updated {{ sourceRow.lastUpdatedLabel }}.</span
          >
        </p>
      </div>
      <SourceItemsToolbar
        v-model:search-query="searchQuery"
        :is-mutating="isMutating"
        :source="source"
        source-type="web-crawl"
        @delete-source="handleDeleteSource"
        @sync-crawl="handleSyncCrawl"
        @update-source="handleUpdateSource"
      />
    </header>

    <!-- 错误消息条 -->
    <p
      v-if="errorMessage"
      class="rounded-(--console-radius-md) border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-100"
    >
      {{ errorMessage }}
    </p>

    <!-- 爬取同步状态流（展示后端 SSE 实时事件） -->
    <section
      v-if="syncJob"
      class="grid gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-4"
    >
      <div class="flex items-center justify-between gap-4 max-[760px]:grid">
        <div>
          <strong class="text-sm text-(--text-strong)">Sync stream</strong>
          <p class="mt-1 text-xs text-(--text-faint)">
            {{ jobMessage }}
          </p>
        </div>
        <Badge :class="badgeClass(syncBadgeTone)">
          {{ syncBadgeLabel }}
        </Badge>
      </div>
      <!-- 同步任务进度条 -->
      <div v-if="jobProgress !== null" class="flex items-center gap-3">
        <Progress
          class="h-1.5 bg-(--surface-panel)"
          :model-value="jobProgress"
        />
        <span class="w-10 text-right text-xs text-(--text-faint)">
          {{ jobProgress }}%
        </span>
      </div>
      <!-- 爬取计数器 -->
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

    <!-- 页面列表及批量操作面板 -->
    <SourceItemsTablePanel
      :is-loading="isLoading"
      :is-mutating="isMutating"
      :rows="filteredRows"
      :selected-item-uids="selectedItemUids"
      source-type="web-crawl"
      @delete-items="handleDeleteItems"
      @index-items="handleIndexItems"
      @pause-items="handlePauseItems"
      @rename-item="handleRenameItem"
      @resume-items="handleResumeItems"
      @update-selection="handleSelectionChange"
    />
  </section>
</template>
