<script setup lang="ts">
import { ExternalLink, FileText } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/shared/components/ui/sheet";
</script>

<template>
  <Sheet>
    <!-- 触发按钮：显示引用数量 -->
    <SheetTrigger as-child>
      <Button
        type="button"
        aria-label="Open citations for this assistant message"
        variant="ghost"
        class="h-7 gap-1.5 rounded-full bg-white/[0.045] px-2.5 text-[12px] font-medium text-(--text-muted) hover:bg-white/[0.07] hover:text-(--text-strong)"
      >
        <span
          class="bg-primary/15 text-primary grid size-4 place-items-center rounded-full text-[10px]"
        >
          3
        </span>
        source items
      </Button>
    </SheetTrigger>

    <SheetContent
      class="!right-0 !w-[min(600px,100dvw)] !max-w-[100dvw] min-w-0 gap-0 overflow-hidden border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <SheetHeader class="border-b border-(--line-soft) px-5 py-4">
        <SheetTitle class="text-[15px]">Citations</SheetTitle>
      </SheetHeader>

      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-4 overflow-y-auto px-5 py-4"
      >
        <!-- 当前消息元信息 -->
        <section class="grid gap-2 border-b border-(--line-soft) pb-4">
          <div class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-[12px]">
            <span class="text-(--text-faint)">Message</span>
            <span class="truncate text-(--text-body)">
              selected assistant answer
            </span>
          </div>
          <div class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-[12px]">
            <span class="text-(--text-faint)">Query</span>
            <span class="truncate text-(--text-body)">
              如何在静态文档站点中嵌入插件？
            </span>
          </div>
          <div class="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 text-[12px]">
            <span class="text-(--text-faint)">Standalone</span>
            <span class="truncate text-(--text-body)">
              如何嵌入 TadaAsk widget?
            </span>
          </div>
        </section>

        <!-- 引用文档条目列表 -->
        <section class="grid gap-2">
          <article
            class="grid gap-2 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2.5"
          >
            <div class="flex items-center gap-2">
              <span
                class="bg-primary/15 text-primary grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold"
              >
                1
              </span>
              <h3
                class="min-w-0 flex-1 truncate text-[13px] font-semibold text-(--text-strong)"
              >
                frontend-ui-scope-constraints.md
              </h3>
              <span class="text-[11px] text-(--text-faint)">0.92</span>
            </div>
            <div
              class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-(--text-faint)"
            >
              <span>Frontend notes</span>
              <span>Widget UI boundary</span>
              <span>usedInContext: true</span>
            </div>
            <p class="line-clamp-2 text-[12px] leading-5 text-(--text-muted)">
              Widget public API 尚未最终确定。MVP 阶段样式自定义主要通过 CSS
              tokens 完成。
            </p>
          </article>

          <article
            class="grid gap-2 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2.5"
          >
            <div class="flex items-center gap-2">
              <span
                class="bg-primary/15 text-primary grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold"
              >
                2
              </span>
              <h3
                class="min-w-0 flex-1 truncate text-[13px] font-semibold text-(--text-strong)"
              >
                widget-install.md
              </h3>
              <span class="text-[11px] text-(--text-faint)">0.87</span>
            </div>
            <div
              class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-(--text-faint)"
            >
              <span>Product docs</span>
              <span>URL: /docs/widget-install</span>
              <span>usedInContext: true</span>
            </div>
            <p class="line-clamp-2 text-[12px] leading-5 text-(--text-muted)">
              Embed the script on the host page and pass the project identifier.
            </p>
          </article>

          <article
            class="grid gap-2 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2.5"
          >
            <div class="flex items-center gap-2">
              <span
                class="bg-primary/15 text-primary grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold"
              >
                3
              </span>
              <h3
                class="min-w-0 flex-1 truncate text-[13px] font-semibold text-(--text-strong)"
              >
                admin-console-routing.md
              </h3>
              <span class="text-[11px] text-(--text-faint)">0.81</span>
            </div>
            <div
              class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-(--text-faint)"
            >
              <span>Frontend notes</span>
              <span>Page 4</span>
              <span>usedInContext: false</span>
            </div>
            <p class="line-clamp-2 text-[12px] leading-5 text-(--text-muted)">
              Admin console keeps project chat and global chat as separate entry
              points.
            </p>
          </article>
        </section>

        <!-- 底部说明：数据来源 -->
        <div
          class="flex items-center gap-2 pt-1 text-[11px] text-(--text-faint)"
        >
          <FileText class="size-3.5" />
          <span>RAG snapshot is loaded from assistant message metadata.</span>
          <ExternalLink class="ml-auto size-3.5" />
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
