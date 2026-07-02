<script setup lang="ts">
// 导入 UI 组件
import { Badge } from "@/shared/components/ui/badge";

// 导入 source 复用组件
import SourceItemsTablePanel from "@/console/components/sources/SourceItemsTablePanel.vue";
import SourceItemsToolbar from "@/console/components/sources/SourceItemsToolbar.vue";
</script>

<template>
  <!-- 网页爬取数据源的页面项管理工作区 -->
  <section class="console-page">
    <!-- 页面头部：展示数据源名称、描述及同步/设置操作 -->
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">Web crawl source</p>
        <h1 class="console-page-title">Main website pages</h1>
        <p class="console-page-subtitle">
          Sync configured crawl targets to create source items, then index
          selected pages.
        </p>
      </div>
      <SourceItemsToolbar source-type="web-crawl" />
    </header>

    <!-- 爬取同步状态流（展示后端 SSE 实时事件） -->
    <section
      class="grid gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-4"
    >
      <div class="flex items-center justify-between gap-4 max-[760px]:grid">
        <div>
          <strong class="text-sm text-(--text-strong)">Sync stream</strong>
          <p class="mt-1 text-xs text-(--text-faint)">
            Detailed crawl events should mirror backend SSE payloads when wired.
          </p>
        </div>
        <Badge
          class="border-(--line-soft) bg-(--surface-panel) text-(--text-muted)"
        >
          Idle
        </Badge>
      </div>
    </section>

    <!-- 页面列表及批量操作面板 -->
    <SourceItemsTablePanel source-type="web-crawl" />
  </section>
</template>
