<script setup lang="ts">
import { Archive, PanelLeft, MessageSquarePlus } from "@lucide/vue";

import ChatContextSettingsSheet from "./ChatContextSettingsSheet.vue";
import { Button } from "@/shared/components/ui/button";
</script>

<template>
  <!-- 会话列表面板：展示全局聊天会话列表，支持新建会话、归档及上下文设置 -->
  <aside
    class="flex min-h-0 flex-col border-r border-(--line-soft) bg-(--surface-shell)/72 px-3 py-3"
  >
    <!-- 顶部：标题与折叠按钮 -->
    <div class="flex items-center justify-between gap-2">
      <span class="text-[11px] font-semibold text-(--text-faint) uppercase">
        Global chat
      </span>
      <Button
        type="button"
        aria-label="Collapse sessions"
        variant="ghost"
        size="icon"
        class="size-8 text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
      >
        <PanelLeft class="size-4" />
      </Button>
    </div>

    <!-- 操作区：新建会话 + 上下文设置 -->
    <div class="mt-3 grid gap-2">
      <Button
        type="button"
        aria-label="Start new chat"
        class="h-9 justify-start gap-2 rounded-(--console-radius-lg) bg-(--surface-hover) text-[13px] font-semibold text-(--text-strong) hover:bg-[#24272d]"
      >
        <MessageSquarePlus class="size-4" />
        New chat
      </Button>
      <ChatContextSettingsSheet />
    </div>

    <div class="mt-6 flex items-center justify-between px-1">
      <span class="text-[11px] font-semibold text-(--text-disabled) uppercase">
        Chat
      </span>
      <span class="text-[11px] text-(--text-disabled)">12</span>
    </div>

    <!-- 会话历史列表 -->
    <nav
      class="console-scrollbar mt-2 grid min-h-0 flex-1 content-start gap-1 overflow-y-auto pr-1"
      aria-label="Chat sessions"
    >
      <button
        type="button"
        aria-label="Open session Widget embed question"
        class="group flex min-h-9 items-center gap-2 rounded-(--console-radius-md) bg-white/[0.055] px-2.5 text-left text-[13px] font-semibold text-(--text-strong)"
      >
        <span class="min-w-0 flex-1 truncate">Widget embed question</span>
        <Archive
          class="size-3.5 shrink-0 text-(--text-faint) opacity-70 group-hover:text-(--text-muted)"
        />
      </button>

      <button
        type="button"
        aria-label="Open session Plain model test"
        class="group flex min-h-9 items-center gap-2 rounded-(--console-radius-md) px-2.5 text-left text-[13px] font-medium text-(--text-muted) hover:bg-white/[0.035] hover:text-(--text-strong)"
      >
        <span class="min-w-0 flex-1 truncate">Plain model test</span>
        <Archive
          class="size-3.5 shrink-0 text-(--text-disabled) opacity-0 group-hover:opacity-70"
        />
      </button>

      <button
        type="button"
        aria-label="Open session Source indexing check"
        class="group flex min-h-9 items-center gap-2 rounded-(--console-radius-md) px-2.5 text-left text-[13px] font-medium text-(--text-muted) hover:bg-white/[0.035] hover:text-(--text-strong)"
      >
        <span class="min-w-0 flex-1 truncate">Source indexing check</span>
        <Archive
          class="size-3.5 shrink-0 text-(--text-disabled) opacity-0 group-hover:opacity-70"
        />
      </button>

      <button
        type="button"
        aria-label="Open session Admin prompt draft"
        class="group flex min-h-9 items-center gap-2 rounded-(--console-radius-md) px-2.5 text-left text-[13px] font-medium text-(--text-muted) hover:bg-white/[0.035] hover:text-(--text-strong)"
      >
        <span class="min-w-0 flex-1 truncate">Admin prompt draft</span>
        <Archive
          class="size-3.5 shrink-0 text-(--text-disabled) opacity-0 group-hover:opacity-70"
        />
      </button>

      <button
        type="button"
        aria-label="Open session Hybrid search compare"
        class="group flex min-h-9 items-center gap-2 rounded-(--console-radius-md) px-2.5 text-left text-[13px] font-medium text-(--text-muted) hover:bg-white/[0.035] hover:text-(--text-strong)"
      >
        <span class="min-w-0 flex-1 truncate">Hybrid search compare</span>
        <Archive
          class="size-3.5 shrink-0 text-(--text-disabled) opacity-0 group-hover:opacity-70"
        />
      </button>
    </nav>
  </aside>
</template>
