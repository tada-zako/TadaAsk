<script setup lang="ts">
import { Send } from "@lucide/vue";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Textarea } from "@/shared/components/ui/textarea";
</script>

<template>
  <!-- 全局聊天视图：左侧聊天区域，右侧引用来源(Citations) -->
  <section
    class="grid min-h-[calc(100vh-8rem)] grid-cols-[minmax(0,1fr)_320px] gap-4 max-[980px]:grid-cols-1"
  >
    <!-- 聊天主面板 -->
    <div class="grid rounded-lg border border-border bg-card/80">
      <!-- 面板头部 -->
      <div class="border-b border-border/70 px-4 py-4">
        <h1 class="text-2xl font-bold tracking-normal">Global chat</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          Admin scoped RAG conversation across global sources.
        </p>
      </div>
      <!-- 聊天消息历史区域 -->
      <div class="grid content-end gap-4 p-4">
        <!-- 用户消息 -->
        <div
          class="justify-self-end rounded-lg border border-border bg-accent/60 p-4 text-sm leading-6"
        >
          How should I embed the widget on a static documentation site?
        </div>
        <!-- AI 消息 -->
        <div
          class="max-w-3xl rounded-lg border border-border bg-card p-4 text-sm leading-6 text-muted-foreground"
        >
          Add the widget script to the host page and pass the project identifier
          through the public widget API.
        </div>
      </div>
      <!-- 消息输入区域 -->
      <div class="border-t border-border/70 p-4">
        <div class="grid gap-2">
          <Textarea
            class="min-h-24"
            placeholder="Ask across global sources..."
          />
          <div class="flex justify-end">
            <Button type="button" aria-label="Send global chat message">
              <Send class="size-4" />
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
    <!-- 右侧引用来源面板 -->
    <aside class="rounded-lg border border-border bg-card/80 p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-sm font-semibold">Citations</h2>
        <Badge variant="outline">Admin detail</Badge>
      </div>
      <!-- 引用卡片 -->
      <div class="rounded-lg border border-border bg-background/50 p-3">
        <div class="flex items-center justify-between gap-3">
          <strong class="text-sm">frontend-ui-scope-constraints.md</strong>
          <span class="text-xs font-semibold text-primary">0.92</span>
        </div>
        <p class="mt-3 text-xs leading-5 text-muted-foreground">
          Widget public API is not finalized. MVP style customization is limited
          to CSS tokens.
        </p>
      </div>
    </aside>
  </section>
</template>
