<script setup lang="ts">
// 导入 Lucide 图标
import { CirclePlay, Database, Eye, Trash2, XCircle } from "@lucide/vue";

// 导入 UI 组件
import { Button } from "@/shared/components/ui/button";

// 定义组件属性
defineProps<{
  entityLabel: "files" | "pages"; // 实体标签（文件或页面）
  selectedLabel: string; // 选中状态文本
}>();
</script>

<template>
  <div
    class="flex min-h-13 items-center justify-between gap-4 border-b border-(--line-soft) bg-[#111215] px-4 max-[760px]:grid max-[760px]:py-3"
  >
    <div class="flex items-center gap-3">
      <strong class="text-[13px] text-(--text-strong)">
        {{ selectedLabel }}
      </strong>
      <span class="h-5 w-px bg-(--line)"></span>
      <span class="text-xs text-(--text-faint)">
        Batch operations apply to checked rows.
      </span>
    </div>
    <div class="flex flex-wrap justify-end gap-2">
      <Button
        type="button"
        :aria-label="`Enable selected ${entityLabel}`"
        variant="outline"
        size="sm"
      >
        <Eye class="size-4" />
        Enable
      </Button>
      <Button
        type="button"
        :aria-label="`Index selected ${entityLabel}`"
        variant="outline"
        size="sm"
      >
        <CirclePlay class="size-4" />
        Index
      </Button>
      <Button
        type="button"
        :aria-label="`Cancel selected ${entityLabel} indexing`"
        variant="outline"
        size="sm"
      >
        <XCircle class="size-4" />
        Cancel
      </Button>
      <Button
        type="button"
        :aria-label="`Edit selected ${entityLabel} metadata`"
        variant="outline"
        size="sm"
      >
        <Database class="size-4" />
        Meta
      </Button>
      <Button
        type="button"
        :aria-label="`Delete selected ${entityLabel}`"
        variant="outline"
        size="sm"
        class="border-red-400/35 text-red-100 hover:bg-red-400/10"
      >
        <Trash2 class="size-4" />
        Delete
      </Button>
    </div>
  </div>
</template>
