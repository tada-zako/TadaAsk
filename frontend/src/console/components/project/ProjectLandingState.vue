<script setup lang="ts">
import { reactive } from "vue";
import { useI18n } from "vue-i18n";
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

const { t } = useI18n();

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
            {{ t("project.landing.createFirst") }}
          </h1>
          <p class="console-page-subtitle max-w-2xl">
            {{ t("project.landing.intro") }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button
            type="button"
            :aria-label="t('project.landing.createProject')"
            :disabled="isSubmitting"
            @click="submitCreate"
          >
            {{ t("project.landing.createProject") }}
          </Button>
          <Button
            type="button"
            :aria-label="t('project.sources.openGlobalSources')"
            variant="outline"
            @click="emit('openGlobalSources')"
          >
            {{ t("project.landing.globalSources") }}
          </Button>
        </div>
      </div>

      <!-- 有项目时的项目列表主页 -->
      <div v-else class="grid gap-5">
        <div class="grid gap-2">
          <p class="console-kicker">
            {{ t("project.landing.projectsKicker") }}
          </p>
          <h1 class="console-page-title">
            {{ t("project.landing.projectHome") }}
          </h1>
          <p class="console-page-subtitle">
            {{ t("project.landing.projectHomeNote") }}
          </p>
        </div>

        <!-- 项目列表滚动区域 -->
        <div
          class="console-scrollbar grid max-h-[min(28rem,48dvh)] gap-2 overflow-y-auto pr-1"
        >
          <button
            v-for="project in projects"
            :key="project.uid"
            type="button"
            class="grid gap-1 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel) p-4 text-left transition hover:border-(--line) hover:bg-(--surface-hover)"
            :aria-label="
              t('project.landing.openProject', { name: project.name })
            "
            @click="emit('selectProject', project.uid)"
          >
            <span class="flex items-center gap-2 text-sm font-semibold">
              <LayoutDashboard class="text-primary size-4" />
              {{ project.name }}
            </span>
            <span class="line-clamp-2 text-xs leading-5 text-(--text-faint)">
              {{ project.description ?? t("common.empty.noDescription") }}
            </span>
          </button>
        </div>
      </div>
    </article>

    <!-- 右侧项目详情配置面板 -->
    <aside class="console-panel grid gap-4 p-5">
      <div class="grid gap-1">
        <h2 class="console-panel-title">
          {{ t("project.landing.createTitle") }}
        </h2>
        <p class="console-panel-note">
          {{ t("project.landing.createNote") }}
        </p>
      </div>
      <!-- 项目名称输入 -->
      <div class="grid gap-2">
        <Label for="project-name">{{ t("project.landing.nameLabel") }}</Label>
        <Input
          id="project-name"
          v-model="form.name"
          :placeholder="t('project.landing.namePlaceholder')"
        />
        <p class="text-xs leading-5 text-(--text-faint)">
          {{ t("project.landing.nameHelp") }}
        </p>
      </div>
      <!-- 项目描述输入 -->
      <div class="grid gap-2">
        <Label for="project-description">
          {{ t("project.landing.descriptionLabel") }}
        </Label>
        <Textarea
          id="project-description"
          v-model="form.description"
          class="min-h-28"
          :placeholder="t('project.landing.descriptionPlaceholder')"
        />
        <p class="text-xs leading-5 text-(--text-faint)">
          {{ t("project.landing.descriptionHelp") }}
        </p>
      </div>
      <!-- 提示信息 -->
      <div
        class="border-primary/30 bg-primary/10 grid grid-cols-[24px_minmax(0,1fr)] gap-3 rounded-(--console-radius-lg) border p-3"
      >
        <span class="bg-primary mt-1 size-2 rounded-full"></span>
        <div>
          <strong class="text-sm text-(--text-strong)">
            {{ t("project.landing.setupLaterTitle") }}
          </strong>
          <p class="mt-1 text-xs leading-5 text-(--text-muted)">
            {{ t("project.landing.setupLaterBody") }}
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
          :aria-label="t('project.landing.cancelCreate')"
          variant="outline"
          :disabled="isSubmitting"
        >
          {{ t("common.actions.cancel") }}
        </Button>
        <Button
          type="button"
          :aria-label="t('project.landing.createFromDetails')"
          :disabled="isSubmitting"
          @click="submitCreate"
        >
          {{
            isSubmitting
              ? t("project.landing.creating")
              : t("common.actions.create")
          }}
        </Button>
      </div>
    </aside>
  </section>
</template>
