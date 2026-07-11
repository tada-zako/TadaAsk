<script setup lang="ts">
import { ref } from "vue";
import { Check, Copy, LoaderCircle } from "@lucide/vue";

import type {
  ProjectGeneralSettingsForm,
  SettingsFieldErrors,
} from "@/console/services/project-settings";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";

const props = defineProps<{
  form: ProjectGeneralSettingsForm;
  projectUid: string;
  fieldErrors: SettingsFieldErrors;
  errorMessage: string | null;
  isDirty: boolean;
  isSaving: boolean;
}>();

const emit = defineEmits<{
  save: [];
  "update:form": [value: ProjectGeneralSettingsForm];
}>();

// 复制项目 ID 到剪贴板，1.6s 后恢复图标
const copied = ref(false);

// 通过 emit 向上传递局部修改，父级 store 负责合并到完整 draft
function updateForm(patch: Partial<ProjectGeneralSettingsForm>): void {
  emit("update:form", { ...props.form, ...patch });
}

async function copyProjectUid(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.projectUid);
    copied.value = true;
    window.setTimeout(() => (copied.value = false), 1600);
  } catch {
    copied.value = false;
  }
}
</script>

<template>
  <!-- 项目通用设置面板：名称、描述、项目 ID 复制 -->
  <section class="console-section">
    <header class="grid gap-1 px-0.5">
      <h2 class="text-xl leading-[1.35] font-bold text-(--text-strong)">
        General
      </h2>
      <p class="text-xs leading-5 text-(--text-faint)">
        Basic project information used throughout the console.
      </p>
    </header>

    <section class="console-panel overflow-hidden">
      <div class="grid gap-5 p-5">
        <div class="grid gap-2">
          <Label for="project-settings-name" class="text-[13px] font-semibold"
            >Project name</Label
          >
          <Input
            id="project-settings-name"
            :model-value="form.name"
            :aria-invalid="Boolean(fieldErrors.name)"
            :disabled="isSaving"
            class="h-10 border-(--line) bg-black/20 text-[13px] shadow-none"
            @update:model-value="updateForm({ name: String($event) })"
          />
          <p v-if="fieldErrors.name" class="text-xs text-red-300">
            {{ fieldErrors.name }}
          </p>
          <p v-else class="text-xs leading-5 text-(--text-faint)">
            Must be unique. This name appears in the project switcher.
          </p>
        </div>

        <div class="grid gap-2">
          <Label
            for="project-settings-description"
            class="text-[13px] font-semibold"
            >Description</Label
          >
          <Textarea
            id="project-settings-description"
            :model-value="form.description"
            :disabled="isSaving"
            class="min-h-22 border-(--line) bg-black/20 text-[13px] leading-6 shadow-none"
            @update:model-value="updateForm({ description: String($event) })"
          />
          <p class="text-xs leading-5 text-(--text-faint)">
            Optional context for admins. It is not included in visitor prompts.
          </p>
        </div>

        <div class="grid gap-2">
          <Label for="project-settings-id" class="text-[13px] font-semibold"
            >Project ID</Label
          >
          <div class="flex min-w-0">
            <Input
              id="project-settings-id"
              :model-value="projectUid"
              readonly
              class="h-10 min-w-0 rounded-r-none border-(--line) bg-black/20 font-mono text-xs text-(--text-muted) shadow-none"
            />
            <Button
              type="button"
              variant="outline"
              class="h-10 w-15 rounded-l-none border-l-0 border-(--line) bg-(--surface-raised) px-3 text-xs text-(--text-muted)"
              @click="copyProjectUid"
            >
              <Check v-if="copied" class="size-3.5 text-emerald-300" />
              <Copy v-else class="size-3.5" />
            </Button>
          </div>
          <p class="text-xs leading-5 text-(--text-faint)">
            Stable identifier used by project-scoped APIs and widgets.
          </p>
        </div>

        <!-- 保存失败时的错误信息，由 store 的 generalError 传入 -->
        <p
          v-if="errorMessage"
          class="rounded-(--console-radius-md) border border-red-400/20 bg-red-400/8 px-3 py-2 text-xs text-red-200"
        >
          {{ errorMessage }}
        </p>
      </div>

      <!-- 底部状态栏：脏标记（黄=有修改 / 绿=已同步）+ 保存按钮 -->
      <footer
        class="flex min-h-15 items-center justify-between gap-4 border-t border-(--line-soft) bg-black/10 px-4 py-3 pl-5 max-[560px]:flex-col max-[560px]:items-stretch"
      >
        <span class="flex items-center gap-2 text-xs text-(--text-faint)">
          <span
            class="size-1.5 rounded-full"
            :class="isDirty ? 'bg-yellow-300' : 'bg-emerald-300'"
          ></span>
          {{
            isDirty
              ? "Unsaved project changes"
              : "Project details are up to date"
          }}
        </span>
        <Button
          type="button"
          :disabled="!isDirty || isSaving"
          class="max-[560px]:w-full"
          @click="emit('save')"
        >
          <LoaderCircle v-if="isSaving" class="size-3.5 animate-spin" />
          {{ isSaving ? "Saving…" : "Save changes" }}
        </Button>
      </footer>
    </section>
  </section>
</template>
