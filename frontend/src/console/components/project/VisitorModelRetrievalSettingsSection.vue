<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { ChevronRight, CircleAlert, X } from "@lucide/vue";

import type { ProviderWithModelsRead } from "@/console/api/provider-model";
import type {
  ProjectSettingsRead,
  ProjectVisitorSettingsForm,
  SettingsFieldErrors,
} from "@/console/services/project-settings";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";

const props = defineProps<{
  form: ProjectVisitorSettingsForm;
  settings: ProjectSettingsRead;
  enabledProviders: ProviderWithModelsRead[];
  fieldErrors: SettingsFieldErrors;
  disabled: boolean;
}>();
const { t } = useI18n();
const emit = defineEmits<{
  "update:form": [value: ProjectVisitorSettingsForm];
}>();

// 根据 form 中的 providerUid/modelUid 在 enabledProviders 列表中查找完整对象
// 用于在触发按钮上展示 provider 首字母图标、provider 名称和模型名称
const selectedProvider = computed(
  () =>
    props.enabledProviders.find(
      (item) => item.uid === props.form.providerUid,
    ) ?? null,
);
const selectedModel = computed(
  () =>
    selectedProvider.value?.modelProfiles?.find(
      (item) => item.uid === props.form.modelUid,
    ) ?? null,
);
// 名称展示有三级回退：当前选中 > 服务端默认 > null
const selectedProviderName = computed(() => {
  if (!hasSelection.value) return null;
  return (
    selectedProvider.value?.name ??
    props.settings.visitorDefaultProvider?.name ??
    null
  );
});
const selectedModelName = computed(() => {
  if (!hasSelection.value) return null;
  return (
    selectedModel.value?.model ??
    props.settings.visitorDefaultModelProfile?.model ??
    null
  );
});
// 用于控制触发按钮样式：未选时虚线边框，已选时实线+可清除
const hasSelection = computed(() =>
  Boolean(props.form.providerUid && props.form.modelUid),
);
const searchModes = computed(() => [
  {
    value: "fast",
    title: t("project.settings.visitor.retrieval.modes.fast"),
    detail: t("project.settings.visitor.retrieval.modes.fastHelp"),
  },
  {
    value: "adaptive",
    title: t("project.settings.visitor.retrieval.modes.adaptive"),
    detail: t("project.settings.visitor.retrieval.modes.adaptiveHelp"),
  },
  {
    value: "full",
    title: t("project.settings.visitor.retrieval.modes.full"),
    detail: t("project.settings.visitor.retrieval.modes.fullHelp"),
  },
]);

function updateForm(patch: Partial<ProjectVisitorSettingsForm>): void {
  emit("update:form", { ...props.form, ...patch });
}

// 下拉菜单选中模型时同时写入 providerUid + modelUid
function selectModel(providerUid: string, modelUid: string): void {
  updateForm({ providerUid, modelUid });
}
</script>

<template>
  <!-- 模型选择 & 知识检索配置区 -->
  <section>
    <header class="px-5 pt-5">
      <h3 class="text-base leading-[1.4] font-bold text-(--text-strong)">
        {{ t("project.settings.visitor.model.title") }}
      </h3>
    </header>
    <div class="grid gap-5 p-5 pt-4">
      <!-- Provider / Model 下拉选择器：分组展示已启用的 provider 及其模型列表
           虚线边框=未选择，实线=已选；hover 时右侧出现 X 按钮可清除选择 -->
      <div
        class="grid gap-2.5 rounded-(--console-radius-lg) border p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]"
      >
        <div class="flex items-center justify-between gap-3">
          <Label>{{ t("project.settings.visitor.model.defaultModel") }}</Label>
          <span
            class="text-primary/80 text-[10px] font-semibold tracking-[0.08em] uppercase"
            >{{ t("project.settings.visitor.model.runtime") }}</span
          >
        </div>
        <div class="group/model relative">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <button
                type="button"
                :disabled="disabled"
                class="hover:border-primary/40 focus-visible:border-primary/50 focus-visible:ring-primary/15 flex min-h-14 w-full items-center gap-3 rounded-(--console-radius-md) border bg-(--surface-raised) px-2.5 py-2 pr-12 text-left shadow-[0_8px_24px_rgba(0,0,0,0.16)] transition-colors hover:bg-(--surface-hover) focus-visible:ring-3 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                :class="
                  hasSelection
                    ? 'border-primary/25'
                    : 'border-primary/30 border-dashed'
                "
              >
                <span
                  class="text-primary grid size-9 shrink-0 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-black/20 text-sm font-bold"
                  >{{ selectedProviderName?.charAt(0) ?? "+" }}</span
                >
                <span class="grid min-w-0 flex-1 gap-0.5">
                  <strong
                    class="truncate text-sm font-semibold text-(--text-strong)"
                    >{{
                      selectedModelName ??
                      t("project.settings.visitor.model.notConfigured")
                    }}</strong
                  >
                  <span class="truncate text-xs text-(--text-faint)">{{
                    hasSelection
                      ? t("project.settings.visitor.model.enabledModel", {
                          provider:
                            selectedProviderName ??
                            t("project.settings.visitor.model.unknownProvider"),
                        })
                      : t("project.settings.visitor.model.selectPrompt")
                  }}</span>
                </span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              class="max-h-82 w-[var(--reka-dropdown-menu-trigger-width)] min-w-72 [scrollbar-width:none] overflow-y-auto rounded-(--console-radius-lg) border-(--line) bg-(--surface-shell) p-1.5 [&::-webkit-scrollbar]:hidden"
            >
              <template
                v-for="provider in enabledProviders"
                :key="provider.uid"
              >
                <DropdownMenuLabel
                  class="px-2 pt-2 pb-1 text-[11px] font-semibold text-(--text-faint) uppercase"
                  >{{ provider.name }}</DropdownMenuLabel
                >
                <DropdownMenuItem
                  v-for="model in provider.modelProfiles ?? []"
                  :key="model.uid"
                  class="min-h-9 rounded-(--console-radius-md) px-2.5 text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                  :class="
                    form.modelUid === model.uid
                      ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                      : ''
                  "
                  @select="selectModel(provider.uid, model.uid)"
                  >{{ model.model }}</DropdownMenuItem
                >
              </template>
              <DropdownMenuItem
                v-if="enabledProviders.length === 0"
                disabled
                class="px-2.5 py-2 text-xs text-(--text-faint)"
                >{{
                  t("project.settings.visitor.model.noModels")
                }}</DropdownMenuItem
              >
            </DropdownMenuContent>
          </DropdownMenu>
          <span
            class="pointer-events-none absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center"
            :class="hasSelection ? 'group-hover/model:hidden' : ''"
            ><ChevronRight class="size-4 rotate-90 text-(--text-faint)"
          /></span>
          <!-- 已选时 hover 出现的清除按钮，将 provider 和 model 同时置 null -->
          <button
            v-if="hasSelection"
            type="button"
            :disabled="disabled"
            class="absolute top-1/2 right-2 hidden size-8 -translate-y-1/2 place-items-center rounded-(--console-radius-md) text-(--text-faint) group-hover/model:grid hover:bg-red-400/10 hover:text-red-300"
            @click.stop.prevent="
              updateForm({ providerUid: null, modelUid: null })
            "
          >
            <X class="size-4" />
          </button>
        </div>
        <p class="text-xs leading-5 text-(--text-faint)">
          {{ t("project.settings.visitor.model.help") }}
        </p>
      </div>

      <!-- Thinking Level："off" 传给 API 时转为 false，其余透传 -->
      <div
        class="grid grid-cols-[minmax(0,1fr)_11.5rem] items-center gap-5 max-[620px]:grid-cols-1 max-[620px]:gap-2"
      >
        <div class="grid gap-1">
          <Label>{{ t("project.settings.visitor.model.thinking") }}</Label>
          <p class="text-xs leading-5 text-(--text-faint)">
            {{ t("project.settings.visitor.model.thinkingHelp") }}
          </p>
        </div>
        <Select
          :model-value="form.thinkingLevel"
          :disabled="disabled"
          @update:model-value="
            updateForm({
              thinkingLevel: String(
                $event,
              ) as ProjectVisitorSettingsForm['thinkingLevel'],
            })
          "
        >
          <SelectTrigger
            class="h-10 w-full border-(--line) bg-black/20 shadow-none"
            ><SelectValue
          /></SelectTrigger>
          <SelectContent
            ><SelectItem value="off">{{
              t("project.settings.visitor.model.thinkingOff")
            }}</SelectItem
            ><SelectItem value="low">{{
              t("project.settings.visitor.model.thinkingLow")
            }}</SelectItem
            ><SelectItem value="medium">{{
              t("project.settings.visitor.model.thinkingMedium")
            }}</SelectItem
            ><SelectItem value="high">{{
              t("project.settings.visitor.model.thinkingHigh")
            }}</SelectItem></SelectContent
          >
        </Select>
      </div>

      <div class="grid gap-2">
        <Label for="visitor-system-instructions">{{
          t("project.settings.visitor.model.systemInstructions")
        }}</Label>
        <Textarea
          id="visitor-system-instructions"
          :model-value="form.systemPrompt"
          :disabled="disabled"
          class="min-h-29 border-(--line) bg-black/20 text-[13px] leading-6 shadow-none"
          :placeholder="t('project.settings.visitor.model.systemPlaceholder')"
          @update:model-value="updateForm({ systemPrompt: String($event) })"
        />
        <p class="text-xs leading-5 text-(--text-faint)">
          {{ t("project.settings.visitor.model.systemHelp") }}
        </p>
      </div>
    </div>
  </section>

  <!-- RAG 知识检索配置：开关 → 搜索模式 → 返回数量 → 重排序 → 追问重写 -->
  <section class="border-t border-(--line-soft)">
    <header class="px-5 pt-5">
      <h3 class="text-base leading-[1.4] font-bold text-(--text-strong)">
        {{ t("project.settings.visitor.retrieval.title") }}
      </h3>
    </header>
    <div class="grid gap-5 p-5 pt-4">
      <div class="flex items-center justify-between gap-6">
        <div class="grid gap-1">
          <Label>{{ t("project.settings.visitor.retrieval.enabled") }}</Label>
          <p class="text-xs leading-5 text-(--text-faint)">
            {{ t("project.settings.visitor.retrieval.enabledHelp") }}
          </p>
        </div>
        <Switch
          :model-value="form.ragEnabled"
          :disabled="disabled"
          @update:model-value="updateForm({ ragEnabled: Boolean($event) })"
        />
      </div>

      <!-- RAG 搜索模式：Fast(原词检索) / Adaptive(按需扩展) / Full(始终扩展) -->
      <fieldset class="grid gap-2.5" :disabled="disabled">
        <legend class="text-[13px] font-semibold text-(--text-strong)">
          {{ t("project.settings.visitor.retrieval.searchMode") }}
        </legend>
        <p class="-mt-1 text-xs leading-5 text-(--text-faint)">
          {{ t("project.settings.visitor.retrieval.searchModeHelp") }}
        </p>
        <RadioGroup
          :model-value="form.ragMode"
          class="gap-2"
          @update:model-value="
            updateForm({
              ragMode: $event as ProjectVisitorSettingsForm['ragMode'],
            })
          "
        >
          <Label
            v-for="mode in searchModes"
            :key="mode.value"
            :for="`search-mode-${mode.value}`"
            class="has-[[data-state=checked]]:border-primary/40 has-[[data-state=checked]]:bg-primary/[0.075] grid min-h-17 cursor-default grid-cols-[minmax(0,1fr)_1rem] items-center gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-black/10 px-3.5 py-3 transition-colors"
          >
            <RadioGroupItem
              :id="`search-mode-${mode.value}`"
              :value="mode.value"
              class="peer col-start-2 row-start-1 border-(--line-strong) bg-transparent shadow-none"
            />
            <span class="col-start-1 row-start-1 grid gap-1"
              ><strong
                class="peer-data-[state=checked]:text-primary text-[13px] font-semibold text-(--text-strong)"
                >{{ mode.title }}</strong
              ><span
                class="text-xs leading-5 font-normal text-(--text-faint)"
                >{{ mode.detail }}</span
              ></span
            >
          </Label>
        </RadioGroup>
      </fieldset>

      <div class="flex items-center justify-between gap-6">
        <div class="grid gap-1">
          <Label for="visitor-results-limit">{{
            t("project.settings.visitor.retrieval.results")
          }}</Label>
          <p class="text-xs leading-5 text-(--text-faint)">
            {{ t("project.settings.visitor.retrieval.resultsHelp") }}
          </p>
        </div>
        <div class="grid justify-items-end gap-1">
          <Input
            id="visitor-results-limit"
            type="number"
            :model-value="form.ragTopK"
            :aria-invalid="Boolean(fieldErrors.ragTopK)"
            :disabled="disabled"
            class="h-10 w-27 border-(--line) bg-black/20 text-right text-[13px] shadow-none"
            @update:model-value="updateForm({ ragTopK: String($event) })"
          /><span v-if="fieldErrors.ragTopK" class="text-[11px] text-red-300">{{
            fieldErrors.ragTopK
          }}</span>
        </div>
      </div>
      <div class="flex items-center justify-between gap-6">
        <div class="grid gap-1">
          <Label>{{ t("project.settings.visitor.retrieval.rerank") }}</Label>
          <p class="text-xs leading-5 text-(--text-faint)">
            {{ t("project.settings.visitor.retrieval.rerankHelp") }}
          </p>
        </div>
        <Switch
          :model-value="form.rerankEnabled"
          :disabled="disabled"
          @update:model-value="updateForm({ rerankEnabled: Boolean($event) })"
        />
      </div>
      <div class="flex items-center justify-between gap-6">
        <div class="grid gap-1">
          <Label>{{ t("project.settings.visitor.retrieval.rewrite") }}</Label>
          <p class="text-xs leading-5 text-(--text-faint)">
            {{ t("project.settings.visitor.retrieval.rewriteHelp") }}
          </p>
        </div>
        <Switch
          :model-value="form.standaloneEnabled"
          :disabled="disabled"
          @update:model-value="
            updateForm({ standaloneEnabled: Boolean($event) })
          "
        />
      </div>
      <!-- RAG 前置条件提示：至少需要一个已完成的公开知识源 -->
      <div
        class="grid grid-cols-[1rem_minmax(0,1fr)] gap-2 rounded-(--console-radius-md) border border-yellow-300/20 bg-yellow-300/[0.065] px-3 py-2.5 text-xs leading-5 text-yellow-100/85"
      >
        <CircleAlert class="mt-0.5 size-3.5" /><span>{{
          t("project.settings.visitor.retrieval.requirement")
        }}</span>
      </div>
    </div>
  </section>
</template>
