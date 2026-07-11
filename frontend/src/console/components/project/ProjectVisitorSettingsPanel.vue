<script setup lang="ts">
import { LoaderCircle } from "@lucide/vue";

import type { ProviderWithModelsRead } from "@/console/api/provider-model";
import type {
  ProjectSettingsRead,
  ProjectVisitorSettingsForm,
  SettingsFieldErrors,
} from "@/console/services/project-settings";
import { Button } from "@/shared/components/ui/button";
import VisitorAdvancedSettingsSection from "./VisitorAdvancedSettingsSection.vue";
import VisitorModelRetrievalSettingsSection from "./VisitorModelRetrievalSettingsSection.vue";

const props = defineProps<{
  form: ProjectVisitorSettingsForm;
  settings: ProjectSettingsRead;
  enabledProviders: ProviderWithModelsRead[];
  fieldErrors: SettingsFieldErrors;
  errorMessage: string | null;
  isDirty: boolean;
  isSaving: boolean;
}>();

const emit = defineEmits<{
  save: [];
  "update:form": [value: ProjectVisitorSettingsForm];
}>();
</script>

<template>
  <!-- 访客助手设置面板：组合两个子组件 + 全局 error + 保存 footer -->
  <section class="console-section">
    <header class="grid gap-1 px-0.5">
      <h2 class="text-xl leading-[1.35] font-bold text-(--text-strong)">
        Visitor assistant
      </h2>
      <p class="text-xs leading-5 text-(--text-faint)">
        Default response and retrieval behavior for visitor chat.
      </p>
    </header>

    <section
      class="console-panel overflow-hidden [&_[data-slot=label]]:text-[12.5px] [&_[data-slot=label]]:font-semibold [&_[data-slot=label]]:text-(--text-body)"
    >
      <VisitorModelRetrievalSettingsSection
        :form="form"
        :settings="settings"
        :enabled-providers="enabledProviders"
        :field-errors="fieldErrors"
        :disabled="isSaving"
        @update:form="emit('update:form', $event)"
      />
      <VisitorAdvancedSettingsSection
        :form="form"
        :field-errors="fieldErrors"
        :disabled="isSaving"
        @update:form="emit('update:form', $event)"
      />

      <p
        v-if="errorMessage"
        class="mx-5 mb-4 rounded-(--console-radius-md) border border-red-400/20 bg-red-400/8 px-3 py-2 text-xs text-red-200"
      >
        {{ errorMessage }}
      </p>

      <!-- 底部状态栏：同 General 面板的 dirty/saving 模式 -->
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
              ? "Unsaved visitor changes"
              : "Visitor settings are up to date"
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
