<script setup lang="ts">
import { BadgeCheck, CircleAlert } from "@lucide/vue";

import { Badge } from "@/shared/components/ui/badge";
import { Separator } from "@/shared/components/ui/separator";

import ProjectLinkedSourcesPanel from "./ProjectLinkedSourcesPanel.vue";
import ProjectWidgetsPanel from "./ProjectWidgetsPanel.vue";
</script>

<template>
  <!-- 项目概览状态视图 -->
  <section class="console-page">
    <!-- 页面头部 -->
    <header class="console-page-head">
      <p class="console-kicker">Docs Assistant</p>
      <h1 class="console-page-title">Project</h1>
      <p class="console-page-subtitle">
        Project workspace for deployed widgets, linked sources, and
        visitor-facing RAG configuration. Source creation and item indexing stay
        in the global Sources area.
      </p>
    </header>

    <!-- 指标卡片网格 -->
    <section
      class="grid grid-cols-4 gap-4 max-[1180px]:grid-cols-2 max-[680px]:grid-cols-1"
    >
      <!-- 关联数据源指标 -->
      <article class="console-metric-card grid gap-3">
        <p class="console-metric-label">Linked sources</p>
        <strong class="console-metric-value">4</strong>
        <span class="console-metric-foot mt-auto flex items-center gap-2">
          <span class="size-2 rounded-full bg-emerald-400"></span>
          3 public for visitor RAG
        </span>
      </article>
      <!-- Widget 部署指标 -->
      <article class="console-metric-card grid gap-3">
        <p class="console-metric-label">Widget deployments</p>
        <strong class="console-metric-value">2</strong>
        <span class="console-metric-foot mt-auto flex items-center gap-2">
          <span class="size-2 rounded-full bg-emerald-400"></span>
          1 enabled origin
        </span>
      </article>
      <!-- 模型提供商指标 -->
      <article class="console-metric-card grid gap-3">
        <p class="console-metric-label">Provider / model</p>
        <strong class="console-metric-value truncate text-[1.55rem]"
          >Gemini 2.5</strong
        >
        <span class="console-metric-foot mt-auto flex items-center gap-2">
          <span class="size-2 rounded-full bg-emerald-400"></span>
          Visitor default is set
        </span>
      </article>
      <!-- RAG 状态指标 -->
      <article class="console-metric-card grid gap-3">
        <p class="console-metric-label">RAG status</p>
        <strong class="console-metric-value text-[1.55rem]">Enabled</strong>
        <span class="console-metric-foot mt-auto flex items-center gap-2">
          <span class="size-2 rounded-full bg-primary"></span>
          Project sources are used by Ask
        </span>
      </article>
    </section>

    <!-- 项目健康状况面板 -->
    <section class="console-panel">
      <div class="console-panel-header">
        <div class="grid gap-1">
          <h2 class="console-panel-title">Project health</h2>
          <p class="console-panel-note">
            Current setup signals from available backend resources
          </p>
        </div>
        <Badge class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200">
          <BadgeCheck class="size-3" />
          Ready
        </Badge>
      </div>
      <Separator />
      <div class="grid">
        <!-- 健康检查项 1 -->
        <div
          class="grid min-h-16 grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-4 max-[680px]:grid-cols-[24px_minmax(0,1fr)]"
        >
          <span class="size-2 rounded-full bg-emerald-400"></span>
          <div>
            <strong class="block text-sm text-(--text-strong)"
              >Project scoped Ask is available</strong
            >
            <span class="mt-1 block text-xs text-(--text-faint)">
              It uses this project's linked sources by default.
            </span>
          </div>
          <Badge
            class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200 max-[680px]:col-start-2"
          >
            Configured
          </Badge>
        </div>
        <!-- 健康检查项 2 -->
        <div
          class="grid min-h-16 grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-4 max-[680px]:grid-cols-[24px_minmax(0,1fr)]"
        >
          <span class="size-2 rounded-full bg-emerald-400"></span>
          <div>
            <strong class="block text-sm text-(--text-strong)"
              >Widget origin is explicitly bound</strong
            >
            <span class="mt-1 block text-xs text-(--text-faint)">
              https://docs.example.com is enabled for this widget deployment.
            </span>
          </div>
          <Badge
            class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200 max-[680px]:col-start-2"
          >
            CORS ready
          </Badge>
        </div>
        <!-- 健康检查项 3 -->
        <div
          class="grid min-h-16 grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 px-4 max-[680px]:grid-cols-[24px_minmax(0,1fr)]"
        >
          <CircleAlert class="size-4 text-yellow-300" />
          <div>
            <strong class="block text-sm text-(--text-strong)"
              >One linked source is private</strong
            >
            <span class="mt-1 block text-xs text-(--text-faint)">
              Private sources are still visible to Admin testing but not visitor
              RAG.
            </span>
          </div>
          <Badge
            class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100 max-[680px]:col-start-2"
          >
            Review
          </Badge>
        </div>
      </div>
    </section>

    <!-- 关联数据源子面板 -->
    <section class="console-section">
      <div class="console-section-head">
        <div>
          <h2 class="console-section-title">Linked sources</h2>
          <p class="console-section-note">
            Bind existing global sources to this project.
          </p>
        </div>
      </div>
      <ProjectLinkedSourcesPanel />
    </section>

    <!-- Widget 部署子面板 -->
    <section class="console-section">
      <div class="console-section-head">
        <div>
          <h2 class="console-section-title">Widget deployments</h2>
          <p class="console-section-note">
            Manage widget origins used by visitor CORS checks.
          </p>
        </div>
      </div>
      <ProjectWidgetsPanel />
    </section>
  </section>
</template>
