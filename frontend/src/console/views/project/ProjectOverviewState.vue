<script setup lang="ts">
import { computed } from "vue";
import { BadgeCheck, CircleAlert } from "@lucide/vue";

import { Badge } from "@/shared/components/ui/badge";
import { Separator } from "@/shared/components/ui/separator";
import type {
  ProjectHealthItem,
  ProjectMetric,
  ProjectWidgetCreate,
  ProjectWidgetUpdate,
  ProjectWorkspaceViewModel,
} from "@/console/services/project-workspace";

import ProjectLinkedSourcesPanel from "./ProjectLinkedSourcesPanel.vue";
import ProjectWidgetsPanel from "./ProjectWidgetsPanel.vue";

const props = defineProps<{
  isMutating?: boolean;
  workspace: ProjectWorkspaceViewModel;
}>();

defineEmits<{
  createWidget: [input: ProjectWidgetCreate];
  deleteWidget: [widgetUid: string];
  importSources: [sourceUids: string[]];
  openGlobalSources: [];
  openSource: [sourceUid: string];
  unbindSource: [sourceUid: string];
  updateWidget: [input: { widgetUid: string; payload: ProjectWidgetUpdate }];
}>();

const healthBadge = computed(() => {
  const hasWarning = props.workspace.healthItems.some(
    (item) => item.tone === "warning",
  );

  return hasWarning
    ? { label: "Review", tone: "warning" as const }
    : { label: "Ready", tone: "success" as const };
});

// metric 提示 dot 样式定义
function metricDotClass(metric: ProjectMetric): string {
  const classes: Record<ProjectMetric["tone"], string> = {
    muted: "bg-(--text-faint)",
    primary: "bg-primary",
    success: "bg-emerald-400",
    warning: "bg-yellow-300/80",
  };

  return classes[metric.tone];
}

// project health 提示 dot 样式定义
function healthDotClass(item: ProjectHealthItem): string {
  const classes: Record<ProjectHealthItem["tone"], string> = {
    muted: "bg-(--text-faint)",
    success: "bg-emerald-400",
    warning: "bg-yellow-300/80",
  };

  return classes[item.tone];
}

// 提示 badge 样式定义
function badgeToneClass(tone: ProjectHealthItem["tone"]): string {
  const classes: Record<ProjectHealthItem["tone"], string> = {
    muted: "border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)",
    success: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
    warning: "border-yellow-300/25 bg-yellow-300/10 text-yellow-100",
  };

  return classes[tone];
}
</script>

<template>
  <!-- 项目概览状态视图 -->
  <section class="console-page">
    <!-- 页面头部 -->
    <header class="console-page-head">
      <p class="console-kicker">{{ workspace.project.name }}</p>
      <h1 class="console-page-title">Project</h1>
      <p class="console-page-subtitle">
        {{
          workspace.project.description ??
          "Project workspace for deployed widgets, linked sources, and visitor-facing RAG configuration."
        }}
      </p>
    </header>

    <!-- 指标卡片网格 -->
    <section
      class="grid grid-cols-4 gap-4 max-[1180px]:grid-cols-2 max-[680px]:grid-cols-1"
    >
      <article
        v-for="metric in workspace.metrics"
        :key="metric.key"
        class="console-metric-card grid gap-3"
      >
        <p class="console-metric-label">{{ metric.label }}</p>
        <strong class="console-metric-value truncate text-[1.55rem]">
          {{ metric.value }}
        </strong>
        <span class="console-metric-foot mt-auto flex items-center gap-2">
          <span
            class="size-2 rounded-full"
            :class="metricDotClass(metric)"
          ></span>
          {{ metric.foot }}
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
        <Badge :class="badgeToneClass(healthBadge.tone)">
          <BadgeCheck v-if="healthBadge.tone === 'success'" class="size-3" />
          <CircleAlert v-else class="size-3" />
          {{ healthBadge.label }}
        </Badge>
      </div>
      <Separator />
      <div class="grid">
        <div
          v-for="(item, index) in workspace.healthItems"
          :key="item.key"
          class="grid min-h-16 grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-4 max-[680px]:grid-cols-[24px_minmax(0,1fr)]"
          :class="{ 'border-b-0': index === workspace.healthItems.length - 1 }"
        >
          <!-- <CircleAlert
            v-if="item.tone === 'warning'"
            class="size-4 rounded-full"
            :class="healthDotClass(item)"
          /> -->
          <span
            class="size-2 rounded-full"
            :class="healthDotClass(item)"
          ></span>
          <div>
            <strong class="block text-sm text-(--text-strong)">
              {{ item.title }}
            </strong>
            <span class="mt-1 block text-xs text-(--text-faint)">
              {{ item.detail }}
            </span>
          </div>
          <Badge
            class="max-[680px]:col-start-2"
            :class="badgeToneClass(item.tone)"
          >
            {{ item.status }}
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
      <ProjectLinkedSourcesPanel
        :available-sources="workspace.availableSources"
        :is-mutating="isMutating"
        :sources="workspace.sourceRows"
        @import-sources="$emit('importSources', $event)"
        @open-global-sources="$emit('openGlobalSources')"
        @open-source="$emit('openSource', $event)"
        @unbind-source="$emit('unbindSource', $event)"
      />
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
      <ProjectWidgetsPanel
        :is-mutating="isMutating"
        :widgets="workspace.widgetRows"
        @create-widget="$emit('createWidget', $event)"
        @delete-widget="$emit('deleteWidget', $event)"
        @update-widget="$emit('updateWidget', $event)"
      />
    </section>
  </section>
</template>
