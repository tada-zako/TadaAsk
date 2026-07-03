<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useRoute, useRouter } from "vue-router";

import SourceItemsTablePanel from "@/console/components/sources/SourceItemsTablePanel.vue";
import SourceItemsToolbar from "@/console/components/sources/SourceItemsToolbar.vue";
import { useSourceStore } from "@/console/stores/source";
import { getSourceItemsRouteName } from "@/console/services/source-workspace";
import type { SourceUpdatePayload } from "@/console/api/sources";

// 路由与 Store 绑定
const route = useRoute();
const router = useRouter();
const sourceStore = useSourceStore();
const {
  currentWorkspace,
  errorMessage,
  isLoading,
  isMutating,
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
// 搜索过滤：匹配 title、filename、displayOrigin
const filteredRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();

  if (!query) {
    return itemRows.value;
  }

  return itemRows.value.filter((row) =>
    [row.title, row.filename, row.displayOrigin].some((value) =>
      value?.toLowerCase().includes(query),
    ),
  );
});

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

// 离开页面中断所有流式连接
onBeforeUnmount(() => {
  if (sourceUid.value) {
    sourceStore.disconnectSourceJobStreams(sourceUid.value);
  }
});

// 加载 workspace，若非 local_file 类型则重定向到正确的路由
async function loadWorkspace(uid: string): Promise<void> {
  if (!uid) {
    await router.replace({ name: "sources" });
    return;
  }

  const workspace = await sourceStore.loadSourceWorkspace(uid);

  if (workspace.source.sourceType !== "local_file") {
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

async function handleUploadFiles(files: File[]): Promise<void> {
  if (!sourceUid.value) {
    return;
  }

  await sourceStore.uploadItems(sourceUid.value, files);
  await sourceStore.loadSourceWorkspace(sourceUid.value);
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
  await sourceStore.downloadItem(sourceUid.value, itemUid);
}
</script>

<template>
  <!-- 本地文件数据源的文件项管理工作区 -->
  <section class="console-page">
    <!-- 页面头部：展示数据源名称、描述及上传/设置操作 -->
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">Local file source</p>
        <h1 class="console-page-title">
          {{ source?.sourceName ?? "Loading source" }}
        </h1>
        <p class="console-page-subtitle">
          Upload files, review generated source items, and index items when
          ready.
          <span v-if="sourceRow"
            >Updated {{ sourceRow.lastUpdatedLabel }}.</span
          >
        </p>
      </div>

      <SourceItemsToolbar
        v-model:search-query="searchQuery"
        :is-mutating="isMutating"
        :source="source"
        source-type="local-file"
        @delete-source="handleDeleteSource"
        @update-source="handleUpdateSource"
        @upload-files="handleUploadFiles"
      />
    </header>

    <!-- 错误消息条 -->
    <p
      v-if="errorMessage"
      class="rounded-(--console-radius-md) border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-100"
    >
      {{ errorMessage }}
    </p>

    <!-- 文件列表及批量操作面板 -->
    <SourceItemsTablePanel
      :is-loading="isLoading"
      :is-mutating="isMutating"
      :rows="filteredRows"
      :selected-item-uids="selectedItemUids"
      source-type="local-file"
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
