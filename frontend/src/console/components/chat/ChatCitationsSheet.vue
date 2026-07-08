<script setup lang="ts">
import { ExternalLink, FileText } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import type {
  ChatMessageViewModel,
  RAGSnapshotItem,
} from "@/console/services/chat";
import { Button } from "@/shared/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/shared/components/ui/sheet";

defineProps<{
  message: ChatMessageViewModel;
}>();

const { t } = useI18n();

// 引用条目标题：优先 title → filename → originUrl → 回退 ID
function citationTitle(item: RAGSnapshotItem): string {
  return (
    item.title ??
    item.filename ??
    item.originUrl ??
    t("chat.citations.fallbackTitle", { id: item.citationId })
  );
}

// 引用条目元信息：来源名 / 章节 / 页码 / 是否被上下文使用
function citationMeta(item: RAGSnapshotItem): string {
  return [
    item.sourceName,
    item.sectionHeader,
    item.pageNumber
      ? t("chat.citations.page", { page: item.pageNumber })
      : null,
    t("chat.citations.usedInContext", {
      value: String(item.usedInContext),
    }),
  ]
    .filter(Boolean)
    .join(" · ");
}

// 引用评分：优先 rerank score → RRF score
function citationScore(item: RAGSnapshotItem): string {
  const score = item.rerankScore ?? item.rrfScore;
  return typeof score === "number" ? score.toFixed(2) : "-";
}
</script>

<template>
  <Sheet>
    <!-- 触发按钮：显示引用数量 -->
    <SheetTrigger as-child>
      <Button
        type="button"
        :aria-label="t('chat.citations.openAria')"
        variant="ghost"
        class="h-7 gap-1.5 rounded-full bg-white/[0.045] px-2.5 text-[12px] font-medium text-(--text-muted) hover:bg-white/[0.07] hover:text-(--text-strong)"
      >
        <span
          class="bg-primary/15 text-primary grid size-4 place-items-center rounded-full text-[10px]"
        >
          {{ message.citationCount }}
        </span>
        {{ t("chat.citations.sourceItems") }}
      </Button>
    </SheetTrigger>

    <SheetContent
      class="!right-0 !w-[min(600px,100dvw)] !max-w-[100dvw] min-w-0 gap-0 overflow-hidden border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <SheetHeader class="border-b border-(--line-soft) px-5 py-4">
        <SheetTitle class="text-[15px]">{{
          t("chat.citations.title")
        }}</SheetTitle>
      </SheetHeader>

      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-4 overflow-y-auto px-5 py-4"
      >
        <!-- 当前消息元信息 -->
        <section class="grid gap-2 border-b border-(--line-soft) pb-4">
          <div class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-[12px]">
            <span class="text-(--text-faint)">
              {{ t("chat.citations.message") }}
            </span>
            <span class="truncate text-(--text-body)">
              {{ message.uid }}
            </span>
          </div>
          <div class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-[12px]">
            <span class="text-(--text-faint)">
              {{ t("chat.citations.query") }}
            </span>
            <span class="truncate text-(--text-body)">
              {{ message.rawMessage.ragSnapshot?.query ?? "-" }}
            </span>
          </div>
          <div class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-[12px]">
            <span class="text-(--text-faint)">
              {{ t("chat.citations.standalone") }}
            </span>
            <span class="truncate text-(--text-body)">
              {{ message.rawMessage.ragSnapshot?.standaloneQuery ?? "-" }}
            </span>
          </div>
        </section>

        <!-- 引用文档条目列表 -->
        <section class="grid gap-2">
          <article
            v-for="item in message.citationItems"
            :key="`${item.citationId}-${item.chunkId}`"
            class="grid gap-2 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2.5"
          >
            <div class="flex items-center gap-2">
              <span
                class="bg-primary/15 text-primary grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold"
              >
                {{ item.citationId }}
              </span>
              <h3
                class="min-w-0 flex-1 truncate text-[13px] font-semibold text-(--text-strong)"
              >
                {{ citationTitle(item) }}
              </h3>
              <span class="text-[11px] text-(--text-faint)">
                {{ citationScore(item) }}
              </span>
            </div>
            <div
              class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-(--text-faint)"
            >
              <span>{{ citationMeta(item) }}</span>
            </div>
            <p
              v-if="item.excerpt"
              class="line-clamp-2 text-[12px] leading-5 text-(--text-muted)"
            >
              {{ item.excerpt }}
            </p>
          </article>
        </section>

        <!-- 底部说明：数据来源 -->
        <div
          class="flex items-center gap-2 pt-1 text-[11px] text-(--text-faint)"
        >
          <FileText class="size-3.5" />
          <span>{{ t("chat.citations.snapshotNote") }}</span>
          <ExternalLink class="ml-auto size-3.5" />
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
