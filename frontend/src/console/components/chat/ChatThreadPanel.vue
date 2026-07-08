<script setup lang="ts">
import { ChevronDown, Copy, LoaderCircle, Undo2, ArrowUp } from "@lucide/vue";

import ChatCitationsSheet from "./ChatCitationsSheet.vue";
import { Button } from "@/shared/components/ui/button";
import { Textarea } from "@/shared/components/ui/textarea";
</script>

<template>
  <!-- 聊天消息线程面板：展示对话消息列表与底部输入区域 -->
  <section class="relative flex min-h-0 min-w-0 flex-col overflow-hidden">
    <!-- 顶部标题栏 -->
    <header class="shrink-0 px-6 py-1.5">
      <div class="mx-auto flex h-9 w-[min(820px,calc(100%-2rem))] items-center">
        <h1 class="truncate text-[15px] font-semibold text-(--text-strong)">
          Widget embed question
        </h1>
      </div>
    </header>

    <div
      class="console-scrollbar min-h-0 flex-1 overflow-y-auto px-6 pt-5 pb-42"
    >
      <!-- 消息列表 -->
      <div class="mx-auto grid w-[min(820px,calc(100%-2rem))] gap-8">
        <!-- 用户消息：右对齐 -->
        <article class="group grid justify-items-end gap-2">
          <div
            class="max-w-[78%] rounded-[1.15rem] border border-(--line-soft) bg-[#1e2024] px-3 py-2 text-[14px] leading-6 text-(--text-strong)"
          >
            如何在静态文档站点中嵌入插件？
          </div>
          <div
            class="flex items-center gap-2 pr-1 text-[12px] text-(--text-faint) opacity-70 transition group-hover:opacity-100"
          >
            <span>OpenAI / gpt-4.1-mini · 17:09</span>
            <button
              type="button"
              aria-label="Restart from this message"
              class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
            >
              <Undo2 class="size-3.5" />
            </button>
            <button
              type="button"
              aria-label="Copy message content"
              class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
            >
              <Copy class="size-3.5" />
            </button>
          </div>
        </article>

        <!-- AI 回复消息：左对齐，含引用来源 -->
        <article class="grid max-w-[82%] gap-3">
          <div class="grid gap-3 text-[14px] leading-7 text-(--text-body)">
            <p>
              将插件脚本添加到宿主页面，并传入对应的项目标识符。静态站点里通常把
              script 放在 layout 或全局模板中，这样每个页面都能加载同一个
              TadaAsk widget。
            </p>
            <p>
              如果只想在文档页面启用，可以在 docs layout 内注入脚本，避免影响
              landing、auth 或其它管理页面。
            </p>
          </div>
          <div class="flex">
            <ChatCitationsSheet />
          </div>
        </article>

        <article class="group grid justify-items-end gap-2">
          <div
            class="max-w-[78%] rounded-[1.1rem] border border-(--line-soft) bg-[#1e2024] px-3 py-2 text-[14px] leading-6 text-(--text-strong)"
          >
            如果没有选择 source，会发生什么？
          </div>
          <div
            class="flex items-center gap-2 pr-1 text-[12px] text-(--text-faint) opacity-70 transition group-hover:opacity-100"
          >
            <span>OpenAI / gpt-4.1-mini · 17:12</span>
            <button
              type="button"
              aria-label="Restart from this message"
              class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
            >
              <Undo2 class="size-3.5" />
            </button>
            <button
              type="button"
              aria-label="Copy message content"
              class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
            >
              <Copy class="size-3.5" />
            </button>
          </div>
        </article>

        <article class="grid max-w-[82%] gap-3">
          <div class="grid gap-3 text-[14px] leading-7 text-(--text-body)">
            <p>
              不会走 RAG，会退化为普通 LLM chat。Global chat 只有前端显式传入
              sourceUids 时才会携带增强上下文。
            </p>
            <p>
              因此 UI 上可以把 sources
              看成可选增强能力，而不是每轮回答的必选项。
            </p>
          </div>
        </article>

        <!-- AI 思考中 loading 状态 -->
        <article class="grid max-w-[82%] gap-3">
          <div class="flex items-center gap-2 text-[13px] text-(--text-faint)">
            <LoaderCircle class="text-primary size-4 animate-spin" />
            TadaAsk is thinking
          </div>
        </article>
      </div>
    </div>

    <!-- 底部输入区域：消息输入框 + 模型/think 选择 + 发送按钮 -->
    <div
      class="pointer-events-none absolute inset-x-0 bottom-0 bg-linear-to-t from-(--surface-base) via-(--surface-base)/95 to-transparent px-6 pt-10 pb-5"
    >
      <div
        class="pointer-events-auto mx-auto w-[min(820px,calc(100%-2rem))] rounded-[1.35rem] border border-(--line-strong) bg-[#24262b] p-2 shadow-[0_22px_80px_rgba(0,0,0,0.42)]"
      >
        <Textarea
          class="min-h-14 border-0 bg-transparent px-2 pt-2 pb-1 text-[14px] shadow-none focus-visible:ring-0"
          placeholder="Ask anything..."
        />

        <div class="flex items-center gap-2 px-1 pt-2 pb-1">
          <button
            type="button"
            aria-label="Select provider and model"
            class="flex h-7 items-center gap-1.5 rounded-(--console-radius-md) px-1.5 text-[13px] text-(--text-body) hover:bg-white/[0.045] hover:text-(--text-strong)"
          >
            OpenAI / gpt-4.1-mini
            <ChevronDown class="size-3.5 text-(--text-faint)" />
          </button>

          <button
            type="button"
            aria-label="Select thinking level"
            class="flex h-7 items-center gap-1.5 rounded-(--console-radius-md) px-1.5 text-[13px] text-(--text-body) hover:bg-white/[0.045] hover:text-(--text-strong)"
          >
            5.5 中
            <ChevronDown class="size-3.5 text-(--text-faint)" />
          </button>

          <span
            class="ml-1 hidden text-[12px] text-(--text-faint) sm:inline-flex"
          >
            2 sources selected
          </span>

          <Button
            type="button"
            aria-label="Send message"
            size="icon"
            class="bg-primary text-primary-foreground hover:bg-primary/90 ml-auto size-8 rounded-full"
          >
            <ArrowUp class="size-4" />
          </Button>
        </div>
      </div>
    </div>
  </section>
</template>
