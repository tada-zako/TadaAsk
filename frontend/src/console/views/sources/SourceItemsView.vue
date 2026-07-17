<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { Badge } from "@/shared/components/ui/badge";
import { Progress } from "@/shared/components/ui/progress";

import SourceItemsTablePanel from "@/console/components/sources/SourceItemsTablePanel.vue";
import SourceItemsToolbar from "@/console/components/sources/SourceItemsToolbar.vue";
import { useSourceItemsRuntime } from "@/console/composables/sources/useSourceItemsRuntime";
import { useSourceStore } from "@/console/stores/source";
import { getSourceItemsRouteName } from "@/console/services/source-workspace";
import type { SourceTone } from "@/console/services/source-workspace";
import type { SourceUpdatePayload } from "@/console/api/sources";

type SourceItemsToolbarType = "local-file" | "web-crawl";

// 统一 source item 工作区：页面差异由后端 sourceType 决定，而不是由路由拆分决定。
const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const sourceStore = useSourceStore();
const { errorMessage, isLoading, isMutating } = storeToRefs(sourceStore);
const sourceUid = computed(() => String(route.params.sourceUid ?? ""));
const {
  clearSourceRuntimeState,
  deleteItems,
  deleteSource,
  downloadItem,
  filteredRows, // source items table 中直接关联的响应式变量
  indexItems,
  loadWorkspace: loadSourceItemsWorkspace,
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
} = useSourceItemsRuntime({ sourceUid });
const isWebCrawl = computed(() => source.value?.sourceType === "web_crawl");
const toolbarSourceType = computed<SourceItemsToolbarType>(() =>
  isWebCrawl.value ? "web-crawl" : "local-file",
);
const sourceKicker = computed(() => {
  if (isWebCrawl.value) {
    return t("sources.workspace.webKicker");
  }

  if (source.value?.sourceType === "local_file") {
    return t("sources.workspace.localKicker");
  }

  return t("sources.workspace.fallbackKicker");
});
const sourceSubtitle = computed(() =>
  isWebCrawl.value
    ? t("sources.workspace.webDescription")
    : t("sources.workspace.localDescription"),
);

watch(
  sourceUid,
  (uid, oldUid) => {
    if (oldUid) {
      // 清空旧 source 中的残余 progress 设置和 SSE 连接
      resetForSourceChange(oldUid);
    }

    void loadWorkspace(uid);
  },
  { immediate: true },
);

watch(rows, () => {
  pruneSelection();
});

onBeforeUnmount(() => {
  if (sourceUid.value) {
    clearSourceRuntimeState(sourceUid.value);
  }
});

async function loadWorkspace(uid: string): Promise<void> {
  if (!uid) {
    await router.replace({ name: "sources" });
    return;
  }

  await loadSourceItemsWorkspace();

  if (!source.value || !getSourceItemsRouteName(source.value.sourceType)) {
    await router.replace({ name: "sources" });
  }
}

async function handleUpdateSource(input: SourceUpdatePayload): Promise<void> {
  if (!sourceUid.value) {
    return;
  }

  await updateSource(input);
}

async function handleDeleteSource(): Promise<void> {
  if (!sourceUid.value) {
    return;
  }

  await deleteSource();
  await router.push({ name: "sources" });
}

async function handleUploadFiles(files: File[]): Promise<void> {
  if (!sourceUid.value || isWebCrawl.value) {
    return;
  }

  await uploadFiles(files);
}

async function handleSyncCrawl(): Promise<void> {
  if (!sourceUid.value || !isWebCrawl.value) {
    return;
  }

  await syncCrawl();
}

function handleSelectionChange(itemUids: string[]): void {
  setSelection(itemUids);
}

async function handleIndexItems(itemUids: string[]): Promise<void> {
  await indexItems(itemUids);
}

async function handlePauseItems(itemUids: string[]): Promise<void> {
  await pauseItems(itemUids);
}

async function handleResumeItems(itemUids: string[]): Promise<void> {
  await resumeItems(itemUids);
}

async function handleRenameItem(itemUid: string, title: string): Promise<void> {
  await renameItem(itemUid, title);
}

async function handleDeleteItems(itemUids: string[]): Promise<void> {
  await deleteItems(itemUids);
}

async function handleDownloadItem(itemUid: string): Promise<void> {
  if (isWebCrawl.value) {
    return;
  }

  await downloadItem(itemUid);
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
          {{ source?.sourceName ?? t("sources.workspace.loadingSource") }}
        </h1>
        <p class="console-page-subtitle">
          {{ sourceSubtitle }}
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
      v-if="syncVisible"
      class="grid gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-4"
    >
      <div class="flex items-center justify-between gap-4 max-[760px]:grid">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <strong class="text-sm text-(--text-strong)">
              {{ t("sources.workspace.syncStream") }}
            </strong>
            <span
              v-if="syncStage"
              class="rounded-(--console-radius-xs) border border-(--line-soft) px-1.5 py-0.5 text-[11px] text-(--text-faint)"
            >
              {{ syncStage }}
            </span>
          </div>
          <p class="mt-1 text-xs text-(--text-faint)">
            {{ syncMessage }}
          </p>
        </div>
        <Badge :class="badgeClass(syncBadgeTone)">
          {{ syncBadgeLabel }}
        </Badge>
      </div>

      <div v-if="syncProgress !== null" class="flex items-center gap-3">
        <Progress
          class="h-1.5 bg-(--surface-panel)"
          :model-value="syncProgress"
        />
        <span class="w-10 text-right text-xs text-(--text-faint)">
          {{ syncProgress }}%
        </span>
      </div>

      <div
        v-if="syncCounters"
        class="grid grid-cols-4 gap-2 text-xs text-(--text-faint) max-[760px]:grid-cols-2"
      >
        <span>
          {{
            t("sources.workspace.discovered", {
              count: syncCounters.discovered,
            })
          }}
        </span>
        <span>
          {{ t("sources.workspace.fetched", { count: syncCounters.fetched }) }}
        </span>
        <span>
          {{
            t("sources.workspace.completed", {
              count: syncCounters.completed,
            })
          }}
        </span>
        <span>
          {{ t("sources.workspace.failed", { count: syncCounters.failed }) }}
        </span>
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
