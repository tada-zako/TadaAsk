<script setup lang="ts">
// 导入 Vue 核心 API
import { computed, ref } from "vue";
// 导入 Lucide 图标
import { RefreshCw, Settings, Upload } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import type { SourceRead, SourceUpdatePayload } from "@/console/api/sources";
// 导入 UI 组件
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

// 导入设置抽屉组件
import SourceSettingsSheet from "./SourceSettingsSheet.vue";

// 定义组件属性
const props = defineProps<{
  sourceType: "local-file" | "web-crawl";
  source?: SourceRead | null;
  isMutating?: boolean;
  searchQuery?: string;
}>();

const emit = defineEmits<{
  (event: "syncCrawl"): void;
  (event: "uploadFiles", files: File[]): void;
  (event: "update:searchQuery", value: string): void;
  (event: "updateSource", input: SourceUpdatePayload): void;
  (event: "deleteSource"): void;
}>();

const { t } = useI18n();

// 本地文件上传隐藏 input 引用，通过代码触发原生文件选择
const fileInput = ref<HTMLInputElement | null>(null);

// 辅助计算属性：判断是否为网页爬取类型
const isWebCrawl = computed(() => props.sourceType === "web-crawl");
// 搜索框占位符文本
const searchValue = computed(() =>
  isWebCrawl.value
    ? t("sources.toolbar.searchPages")
    : t("sources.toolbar.searchItems"),
);
// 主操作按钮文本
const primaryActionLabel = computed(() =>
  isWebCrawl.value
    ? t("sources.toolbar.syncCrawl")
    : t("sources.toolbar.uploadFiles"),
);
// 主操作按钮无障碍标签
const primaryActionAriaLabel = primaryActionLabel;

// 主操作按钮：web_crawl 触发同步，local_file 弹出文件选择
function handlePrimaryAction(): void {
  if (isWebCrawl.value) {
    emit("syncCrawl");
    return;
  }

  fileInput.value?.click();
}

// 本地文件选择回调：提取 File 对象并向上 emit
function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);

  if (files.length) {
    emit("uploadFiles", files);
  }

  input.value = "";
}
</script>

<template>
  <div class="flex shrink-0 items-center gap-2 pb-0.5">
    <Input
      class="w-80 max-w-full"
      :model-value="searchQuery"
      :placeholder="searchValue"
      @update:model-value="emit('update:searchQuery', String($event))"
    />
    <!-- 隐藏文件上传 input，由主按钮代码触发点击 -->
    <input
      v-if="!isWebCrawl"
      ref="fileInput"
      class="hidden"
      type="file"
      multiple
      @change="handleFileChange"
    />
    <Button
      type="button"
      :aria-label="primaryActionAriaLabel"
      size="sm"
      :disabled="!source || isMutating"
      @click="handlePrimaryAction"
    >
      <RefreshCw v-if="isWebCrawl" class="size-4" />
      <Upload v-else class="size-4" />
      {{ primaryActionLabel }}
    </Button>
    <SourceSettingsSheet
      v-if="source"
      :is-mutating="isMutating"
      :source="source"
      @delete-source="emit('deleteSource')"
      @update-source="emit('updateSource', $event)"
    />
    <Button
      v-else
      type="button"
      :aria-label="t('sources.toolbar.openSettingsAria')"
      variant="outline"
      size="sm"
      class="w-24 overflow-hidden"
      disabled
    >
      <Settings class="size-3.5" />
      {{ t("sources.common.actions.settings") }}
    </Button>
  </div>
</template>
