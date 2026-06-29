<script setup lang="ts">
import { Plus } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
</script>

<template>
  <!-- 创建项目状态视图：左侧引导卡片，右侧项目详情配置表单 -->
  <section
    class="grid grid-cols-[minmax(0,0.95fr)_minmax(360px,0.75fr)] gap-5 max-[980px]:grid-cols-1"
  >
    <!-- 左侧引导卡片 -->
    <article
      class="grid min-h-[520px] content-center gap-5 rounded-[var(--console-radius-lg)] border border-dashed border-[var(--line)] bg-[var(--surface-panel-soft)] p-9"
    >
      <div
        class="grid size-12 place-items-center rounded-[var(--console-radius-lg)] border border-[var(--line-soft)] bg-[var(--surface-panel)] text-primary"
      >
        <Plus class="size-5" />
      </div>
      <div class="grid gap-3">
        <h1 class="console-page-title max-w-2xl">Create your first project</h1>
        <p class="console-page-subtitle max-w-2xl">
          A project is the working scope for linked sources, deployed widgets,
          visitor-facing model settings, and project-scoped RAG testing.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button type="button" aria-label="Create project">
          Create project
        </Button>
        <Button
          type="button"
          aria-label="Open global sources"
          variant="outline"
        >
          Global sources
        </Button>
      </div>
    </article>

    <!-- 右侧项目详情配置面板 -->
    <aside class="console-panel grid gap-4 p-5">
      <div class="grid gap-1">
        <h2 class="console-panel-title">Project details</h2>
        <p class="console-panel-note">Minimal fields for MVP creation</p>
      </div>
      <!-- 项目名称输入 -->
      <div class="grid gap-2">
        <Label for="project-name">Project name</Label>
        <Input id="project-name" default-value="Docs Assistant" />
        <p class="text-xs leading-5 text-[var(--text-faint)]">
          Must be unique. It appears in the sidebar project selector.
        </p>
      </div>
      <!-- 项目描述输入 -->
      <div class="grid gap-2">
        <Label for="project-description">Description</Label>
        <Textarea
          id="project-description"
          default-value="Answers questions from product documentation and release notes."
          class="min-h-28"
        />
        <p class="text-xs leading-5 text-[var(--text-faint)]">
          Optional. Keep it short enough to scan in project overview.
        </p>
      </div>
      <!-- 提示信息 -->
      <div
        class="grid grid-cols-[24px_minmax(0,1fr)] gap-3 rounded-[var(--console-radius-lg)] border border-primary/30 bg-primary/10 p-3"
      >
        <span class="mt-1 size-2 rounded-full bg-primary"></span>
        <div>
          <strong class="text-sm text-[var(--text-strong)]"
            >Provider and sources can be configured later</strong
          >
          <p class="mt-1 text-xs leading-5 text-[var(--text-muted)]">
            Project creation should not block on model provider, widget, or
            source setup.
          </p>
        </div>
      </div>
      <!-- 操作按钮 -->
      <div class="flex justify-end gap-2">
        <Button
          type="button"
          aria-label="Cancel project creation"
          variant="outline"
        >
          Cancel
        </Button>
        <Button type="button" aria-label="Create project from details">
          Create
        </Button>
      </div>
    </aside>
  </section>
</template>
