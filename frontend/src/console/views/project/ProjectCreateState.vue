<script setup lang="ts">
import { reactive } from "vue";
import { Plus } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";

import type { CreateProjectInput } from "@/console/services/project-workspace";

defineProps<{
  errorMessage?: string | null;
  isSubmitting?: boolean;
}>();

const emit = defineEmits<{
  create: [input: CreateProjectInput];
}>();

// Project 创建表单数据
const form = reactive({
  description:
    "Answers questions from product documentation and release notes.",
  name: "Docs Assistant",
});

function submitCreate() {
  emit("create", {
    description: form.description,
    name: form.name,
  });
}
</script>

<template>
  <!-- 创建项目状态视图：左侧引导卡片，右侧项目详情配置表单 -->
  <section
    class="grid grid-cols-[minmax(0,0.95fr)_minmax(360px,0.75fr)] gap-5 max-[980px]:grid-cols-1"
  >
    <!-- 左侧引导卡片 -->
    <article
      class="grid min-h-130 content-center gap-5 rounded-(--console-radius-lg) border border-dashed border-(--line) bg-(--surface-panel-soft) p-9"
    >
      <div
        class="text-primary grid size-12 place-items-center rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
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
        <Button
          type="button"
          aria-label="Create project"
          :disabled="isSubmitting"
          @click="submitCreate"
        >
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
        <Input id="project-name" v-model="form.name" />
        <p class="text-xs leading-5 text-(--text-faint)">
          Must be unique. It appears in the sidebar project selector.
        </p>
      </div>
      <!-- 项目描述输入 -->
      <div class="grid gap-2">
        <Label for="project-description">Description</Label>
        <Textarea
          id="project-description"
          v-model="form.description"
          class="min-h-28"
        />
        <p class="text-xs leading-5 text-(--text-faint)">
          Optional. Keep it short enough to scan in project overview.
        </p>
      </div>
      <!-- 提示信息 -->
      <div
        class="border-primary/30 bg-primary/10 grid grid-cols-[24px_minmax(0,1fr)] gap-3 rounded-(--console-radius-lg) border p-3"
      >
        <span class="bg-primary mt-1 size-2 rounded-full"></span>
        <div>
          <strong class="text-sm text-(--text-strong)"
            >Provider and sources can be configured later</strong
          >
          <p class="mt-1 text-xs leading-5 text-(--text-muted)">
            Project creation should not block on model provider, widget, or
            source setup.
          </p>
        </div>
      </div>
      <p
        v-if="errorMessage"
        class="rounded-(--console-radius-md) border border-yellow-300/25 bg-yellow-300/10 px-3 py-2 text-xs leading-5 text-yellow-100"
      >
        {{ errorMessage }}
      </p>
      <!-- 操作按钮 -->
      <div class="flex justify-end gap-2">
        <Button
          type="button"
          aria-label="Cancel project creation"
          variant="outline"
        >
          Cancel
        </Button>
        <Button
          type="button"
          aria-label="Create project from details"
          :disabled="isSubmitting"
          @click="submitCreate"
        >
          {{ isSubmitting ? "Creating" : "Create" }}
        </Button>
      </div>
    </aside>
  </section>
</template>
