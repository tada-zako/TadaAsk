<script setup lang="ts">
import { onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";

import SourceCreateSheet from "@/console/components/sources/SourceCreateSheet.vue";
import SourceListPanel from "@/console/components/sources/SourceListPanel.vue";
import { useSourceStore } from "@/console/stores/source";
import type {
  CreateSourceInput,
  SourceRow,
} from "@/console/services/source-workspace";
import type { SourceUpdatePayload } from "@/console/api/sources";

const router = useRouter();
const sourceStore = useSourceStore();
const { errorMessage, isLoading, isMutating, sourceRows } =
  storeToRefs(sourceStore);

onMounted(() => {
  void sourceStore.loadSources();
});

/** source 创建事件 */
async function handleCreateSource(input: CreateSourceInput): Promise<void> {
  await sourceStore.createSource(input);
  await sourceStore.loadSources();
}

/** source settings 更新 */
async function handleUpdateSource(
  sourceUid: string,
  input: SourceUpdatePayload,
): Promise<void> {
  await sourceStore.updateSource(sourceUid, input);
  await sourceStore.loadSources();
}

/** source 删除 */
async function handleDeleteSource(sourceUid: string): Promise<void> {
  await sourceStore.deleteSource(sourceUid);
  await sourceStore.loadSources();
}

/** 请求访问 source item 内容 */
async function handleOpenItems(source: SourceRow): Promise<void> {
  if (!source.itemsRouteName) {
    return;
  }

  await router.push({
    name: source.itemsRouteName,
    params: { sourceUid: source.uid },
  });
}
</script>

<template>
  <!-- 全局数据源管理视图 -->
  <section class="console-page">
    <!-- source view header -->
    <header
      class="flex items-end justify-between gap-5 max-[760px]:grid max-[760px]:gap-4"
    >
      <div class="console-page-head">
        <p class="console-kicker">Knowledge sources</p>
        <h1 class="console-page-title">Sources</h1>
        <p class="console-page-subtitle">
          Create source containers, review visibility, and open each source item
          workspace when upload, crawl, or indexing work is needed.
        </p>
      </div>

      <!-- source create sheet -->
      <div class="flex shrink-0 items-center gap-2 pb-0.5">
        <SourceCreateSheet
          :is-mutating="isMutating"
          @create-source="handleCreateSource"
        />
      </div>
    </header>

    <!-- 错误提示 -->
    <p
      v-if="errorMessage"
      class="rounded-(--console-radius-md) border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-100"
    >
      {{ errorMessage }}
    </p>

    <!-- source list table -->
    <SourceListPanel
      :is-loading="isLoading"
      :is-mutating="isMutating"
      :sources="sourceRows"
      @delete-source="handleDeleteSource"
      @open-items="handleOpenItems"
      @update-source="handleUpdateSource"
    />
  </section>
</template>
