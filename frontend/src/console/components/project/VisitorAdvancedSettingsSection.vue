<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { ChevronRight } from "@lucide/vue";

import type {
  ProjectVisitorSettingsForm,
  SettingsFieldErrors,
} from "@/console/services/project-settings";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

const props = defineProps<{
  form: ProjectVisitorSettingsForm;
  fieldErrors: SettingsFieldErrors;
  disabled: boolean;
}>();
const { t } = useI18n();
const emit = defineEmits<{
  "update:form": [value: ProjectVisitorSettingsForm];
}>();

// 可折叠的高级设置区：响应生成 & 检索候选参数
// 通过 FieldDefinition 数组驱动渲染，避免重复编写 label/input/error 模板
type NumericField =
  | "maxOutputTokens"
  | "timeout"
  | "temperature"
  | "topP"
  | "ftsK"
  | "vectorK"
  | "rerankK"
  | "maxAlternativeQueries"
  | "maxKeywords";
interface FieldDefinition {
  key: NumericField;
  label: string;
  help: string;
  step?: string;
  suffix?: string;
}

// 响应生成参数（max tokens / timeout / temperature / topP）
const responseFields = computed<FieldDefinition[]>(() => [
  {
    key: "maxOutputTokens",
    label: t("project.settings.visitor.advanced.maxOutputTokens"),
    help: t("project.settings.visitor.advanced.maxOutputTokensHelp"),
  },
  {
    key: "timeout",
    label: t("project.settings.visitor.advanced.timeout"),
    help: t("project.settings.visitor.advanced.timeoutHelp"),
    suffix: t("project.settings.visitor.advanced.seconds"),
  },
  {
    key: "temperature",
    label: t("project.settings.visitor.advanced.temperature"),
    help: t("project.settings.visitor.advanced.temperatureHelp"),
    step: "0.1",
  },
  {
    key: "topP",
    label: t("project.settings.visitor.advanced.topP"),
    help: t("project.settings.visitor.advanced.topPHelp"),
    step: "0.1",
  },
]);
// 检索候选参数（全文/向量候选数、重排序数、查询扩展等）
const retrievalFields = computed<FieldDefinition[]>(() => [
  {
    key: "ftsK",
    label: t("project.settings.visitor.advanced.ftsK"),
    help: t("project.settings.visitor.advanced.ftsKHelp"),
  },
  {
    key: "vectorK",
    label: t("project.settings.visitor.advanced.vectorK"),
    help: t("project.settings.visitor.advanced.vectorKHelp"),
  },
  {
    key: "rerankK",
    label: t("project.settings.visitor.advanced.rerankK"),
    help: t("project.settings.visitor.advanced.rerankKHelp"),
  },
  {
    key: "maxAlternativeQueries",
    label: t("project.settings.visitor.advanced.maxAlternativeQueries"),
    help: t("project.settings.visitor.advanced.maxAlternativeQueriesHelp"),
  },
  {
    key: "maxKeywords",
    label: t("project.settings.visitor.advanced.maxKeywords"),
    help: t("project.settings.visitor.advanced.maxKeywordsHelp"),
  },
]);

function updateField(key: NumericField, value: string | number): void {
  emit("update:form", { ...props.form, [key]: String(value) });
}
</script>

<template>
  <Collapsible class="group border-t border-(--line-soft)">
    <CollapsibleTrigger
      type="button"
      class="grid w-full grid-cols-[minmax(0,1fr)_auto_1.25rem] items-center gap-3 px-5 py-4.5 text-left"
    >
      <strong class="text-base leading-[1.4] font-bold text-(--text-strong)">{{
        t("project.settings.visitor.advanced.title")
      }}</strong>
      <span class="text-[11px] text-(--text-faint)">{{
        t("project.settings.visitor.advanced.note")
      }}</span>
      <ChevronRight
        class="size-4 text-(--text-faint) transition-transform duration-150 group-data-[state=open]:rotate-90"
      />
    </CollapsibleTrigger>
    <CollapsibleContent
      class="data-[state=open]:animate-in data-[state=open]:fade-in-0 px-5 pb-5"
    >
      <div class="grid gap-6">
        <section class="grid gap-3.5">
          <h4
            class="text-[11px] font-bold tracking-[0.09em] text-(--text-muted) uppercase"
          >
            {{ t("project.settings.visitor.advanced.responseGeneration") }}
          </h4>
          <div class="grid grid-cols-2 gap-4 max-[620px]:grid-cols-1">
            <div
              v-for="field in responseFields"
              :key="field.key"
              class="grid gap-2"
            >
              <Label :for="`visitor-${field.key}`">{{ field.label }}</Label>
              <div class="relative">
                <Input
                  :id="`visitor-${field.key}`"
                  type="number"
                  :step="field.step"
                  :model-value="form[field.key]"
                  :aria-invalid="Boolean(fieldErrors[field.key])"
                  :disabled="disabled"
                  :class="[
                    'h-10 border-(--line) bg-black/20 text-[13px] shadow-none',
                    field.suffix ? 'pr-16' : '',
                  ]"
                  @update:model-value="updateField(field.key, $event)"
                />
                <span
                  v-if="field.suffix"
                  class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-[11px] text-(--text-faint)"
                  >{{ field.suffix }}</span
                >
              </div>
              <p v-if="fieldErrors[field.key]" class="text-xs text-red-300">
                {{ fieldErrors[field.key] }}
              </p>
              <p v-else class="text-xs leading-5 text-(--text-faint)">
                {{ field.help }}
              </p>
            </div>
          </div>
        </section>

        <section class="grid gap-3.5 border-t border-(--line-soft) pt-5">
          <h4
            class="text-[11px] font-bold tracking-[0.09em] text-(--text-muted) uppercase"
          >
            {{ t("project.settings.visitor.advanced.retrievalCandidates") }}
          </h4>
          <div class="grid grid-cols-2 gap-4 max-[620px]:grid-cols-1">
            <div
              v-for="field in retrievalFields"
              :key="field.key"
              class="grid gap-2"
            >
              <Label :for="`visitor-${field.key}`">{{ field.label }}</Label>
              <Input
                :id="`visitor-${field.key}`"
                type="number"
                :model-value="form[field.key]"
                :aria-invalid="Boolean(fieldErrors[field.key])"
                :disabled="disabled"
                class="h-10 border-(--line) bg-black/20 text-[13px] shadow-none"
                @update:model-value="updateField(field.key, $event)"
              />
              <p v-if="fieldErrors[field.key]" class="text-xs text-red-300">
                {{ fieldErrors[field.key] }}
              </p>
              <p v-else class="text-xs leading-5 text-(--text-faint)">
                {{ field.help }}
              </p>
            </div>
          </div>
        </section>
      </div>
    </CollapsibleContent>
  </Collapsible>
</template>
