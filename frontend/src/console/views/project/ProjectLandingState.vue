<script setup lang="ts">
import { reactive } from "vue";
import { LayoutDashboard, Plus } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";

import type {
  CreateProjectInput,
  ProjectOption,
} from "@/console/services/project-workspace";

// 定义组件属性
defineProps<{
  errorMessage?: string | null;
  isLoading?: boolean;
  isSubmitting?: boolean;
  projects: ProjectOption[];
}>();

// 定义组件事件
const emit = defineEmits<{
  create: [input: CreateProjectInput];
  openGlobalSources: [];
  selectProject: [projectUid: string];
}>();

// Project 创建表单数据
const form = reactive({
  description: "", // 默认描述为空，由 placeholder 提示
  name: "", // 默认名称为空，由 placeholder 提示
});

// 提交创建项目
function submitCreate() {
  emit("create", {
    description: form.description,
    name: form.name,
  });
}
</script>

<template>
  <!-- Project landing：左侧展示入口，右侧创建新 project。 -->
  <section
    class="grid grid-cols-[minmax(0,0.95fr)_minmax(360px,0.75fr)] gap-5 max-[980px]:grid-cols-1"
  >
    <article
      class="grid min-h-130 content-start gap-5 rounded-(--console-radius-lg) border border-dashed border-(--line) bg-(--surface-panel-soft) p-9"
    >
      <!-- 无项目时的引导界面 -->
      <div v-if="projects.length === 0" class="grid content-center gap-5">
        <div
          class="text-primary grid size-12 place-items-center rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel)"
        >
          <Plus class="size-5" />
        </div>
        <div class="grid gap-3">
          <h1 class="console-page-title max-w-2xl">
            Create your first project
          </h1>
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
            @click="emit('openGlobalSources')"
          >
            Global sources
          </Button>
        </div>
      </div>

      <!-- 有项目时的项目列表主页 -->
      <div v-else class="grid gap-5">
        <div class="grid gap-2">
          <p class="console-kicker">Projects</p>
          <h1 class="console-page-title">Project home</h1>
          <p class="console-page-subtitle">
            Choose an existing project or create a new workspace.
          </p>
        </div>

        <!-- 项目列表滚动区域 -->
        <div class="console-scrollbar grid max-h-112 gap-2 overflow-y-auto">
          <button
            v-for="project in projects"
            :key="project.uid"
            type="button"
            class="grid gap-1 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel) p-4 text-left transition hover:border-(--line) hover:bg-(--surface-hover)"
            :aria-label="`Open ${project.name}`"
            @click="emit('selectProject', project.uid)"
          >
            <span class="flex items-center gap-2 text-sm font-semibold">
              <LayoutDashboard class="text-primary size-4" />
              {{ project.name }}
            </span>
            <span class="line-clamp-2 text-xs leading-5 text-(--text-faint)">
              {{ project.description ?? "No description yet." }}
            </span>
          </button>
        </div>
      </div>
    </article>

    <!-- 右侧项目详情配置面板 -->
    <aside class="console-panel grid gap-4 p-5">
      <div class="grid gap-1">
        <h2 class="console-panel-title">Project Create</h2>
        <p class="console-panel-note">Minimal fields for MVP creation</p>
      </div>
      <!-- 项目名称输入 -->
      <div class="grid gap-2">
        <Label for="project-name">Project name</Label>
        <Input
          id="project-name"
          v-model="form.name"
          class="placeholder:text-(--text-faint)"
          placeholder="Docs Assistant"
        />
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
          class="min-h-28 resize-none placeholder:text-(--text-faint)"
          placeholder="Answers questions from product documentation and release notes."
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
          <strong class="text-sm text-(--text-strong)">
            Provider and sources can be configured later
          </strong>
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
      <div class="flex justify-end gap-2">
        <Button
          type="button"
          aria-label="Cancel project creation"
          variant="outline"
          :disabled="isSubmitting"
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
