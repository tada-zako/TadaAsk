<script setup lang="ts">
// 导入 Vue 核心 API
import { computed } from "vue";
// 导入 Lucide 图标
import { RefreshCw, Upload } from "@lucide/vue";

// 导入 UI 组件
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

// 导入设置抽屉组件
import SourceSettingsSheet from "./SourceSettingsSheet.vue";

// 定义组件属性
const props = defineProps<{
  sourceType: "local-file" | "web-crawl";
}>();

// 辅助计算属性：判断是否为网页爬取类型
const isWebCrawl = computed(() => props.sourceType === "web-crawl");
// 搜索框占位符文本
const searchValue = computed(() =>
  isWebCrawl.value ? "Search crawled pages" : "Search source items",
);
// 主操作按钮文本
const primaryActionLabel = computed(() =>
  isWebCrawl.value ? "Sync crawl" : "Upload files",
);
// 主操作按钮无障碍标签
const primaryActionAriaLabel = computed(() =>
  isWebCrawl.value ? "Sync crawl" : "Upload files",
);
</script>

<template>
  <div class="flex shrink-0 items-center gap-2 pb-0.5">
    <Input class="w-80 max-w-full" :value="searchValue" />
    <Button type="button" :aria-label="primaryActionAriaLabel" size="sm">
      <RefreshCw v-if="isWebCrawl" class="size-4" />
      <Upload v-else class="size-4" />
      {{ primaryActionLabel }}
    </Button>
    <SourceSettingsSheet :source-type="sourceType" />
  </div>
</template>
