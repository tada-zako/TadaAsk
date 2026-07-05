<script setup lang="ts">
import { ref, watch } from "vue";

import type {
  CreateCustomModelInput,
  ModelRowViewModel,
  UpdateCustomModelInput,
} from "@/console/services/provider-model";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";

const props = defineProps<{
  isMutating?: boolean;
  mode: "create" | "edit";
  model?: ModelRowViewModel;
  providerDisplayName: string;
  providerUid: string;
}>();

const emit = defineEmits<{
  (
    event: "createModel",
    providerUid: string,
    input: CreateCustomModelInput,
  ): void;
  (
    event: "updateModel",
    providerUid: string,
    modelUid: string,
    input: UpdateCustomModelInput,
  ): void;
  (event: "deleteModel", providerUid: string, modelUid: string): void;
}>();

// 表单本地状态
const open = ref(false);
const modelName = ref("");
const contextWindowTokens = ref("");
const maxOutputTokens = ref("");
const isEnabled = ref(true);
const localError = ref<string | null>(null);

// 每次打开/切换 model 时重置表单
watch(open, (nextOpen) => {
  if (nextOpen) {
    resetForm();
  }
});

watch(
  () => props.model,
  () => {
    if (open.value) {
      resetForm();
    }
  },
);

// 提交：create 模式 emit createModel，edit 模式 emit updateModel
function handleSubmit(): void {
  const name = modelName.value.trim();

  if (!name) {
    localError.value = "Model name is required.";
    return;
  }

  localError.value = null;

  if (props.mode === "create") {
    emit("createModel", props.providerUid, {
      model: name,
      contextWindowTokens: parseTokenLimit(contextWindowTokens.value),
      maxOutputTokens: parseTokenLimit(maxOutputTokens.value),
      isEnabled: isEnabled.value,
    });
  } else if (props.model) {
    emit("updateModel", props.providerUid, props.model.uid, {
      model: name,
      contextWindowTokens: parseTokenLimit(contextWindowTokens.value),
      maxOutputTokens: parseTokenLimit(maxOutputTokens.value),
      isEnabled: isEnabled.value,
    });
  }

  open.value = false;
}

// 删除（仅 edit 模式可用）
function handleDelete(): void {
  if (!props.model) {
    return;
  }

  emit("deleteModel", props.providerUid, props.model.uid);
  open.value = false;
}

function resetForm(): void {
  modelName.value = props.model?.model ?? "";
  contextWindowTokens.value = props.model?.contextWindowTokens
    ? String(props.model.contextWindowTokens)
    : "";
  maxOutputTokens.value = props.model?.maxOutputTokens
    ? String(props.model.maxOutputTokens)
    : "";
  isEnabled.value = props.model?.isEnabled ?? true;
  localError.value = null;
}

// 将输入字符串解析为有效正整数或 null
function parseTokenLimit(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <slot />
    </DialogTrigger>
    <DialogContent
      class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[38.75rem]"
    >
      <DialogHeader class="border-b border-(--line-soft) px-5 py-4 text-left">
        <DialogTitle>
          {{ mode === "create" ? "Add custom model" : "Edit custom model" }}
        </DialogTitle>
        <DialogDescription>
          Set the model name, token limits, and availability.
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-4 px-5 py-5">
        <!-- 模型名称 -->
        <div class="grid gap-2">
          <Label :for="`${providerUid}-${mode}-custom-model-name`">Model</Label>
          <Input
            :id="`${providerUid}-${mode}-custom-model-name`"
            v-model="modelName"
            placeholder="qoder-reasoning"
          />
        </div>

        <!-- Token 限制：context window + max output -->
        <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
          <div class="grid gap-2">
            <Label :for="`${providerUid}-${mode}-custom-context`">
              Context window tokens
            </Label>
            <Input
              :id="`${providerUid}-${mode}-custom-context`"
              v-model="contextWindowTokens"
              type="number"
              placeholder="131072"
            />
          </div>
          <div class="grid gap-2">
            <Label :for="`${providerUid}-${mode}-custom-output`">
              Max output tokens
            </Label>
            <Input
              :id="`${providerUid}-${mode}-custom-output`"
              v-model="maxOutputTokens"
              type="number"
              placeholder="8192"
            />
          </div>
        </div>

        <!-- 启用开关 -->
        <div
          class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
        >
          <div>
            <p class="text-sm font-medium text-(--text-strong)">Enabled</p>
            <p class="mt-1 text-xs text-(--text-faint)">
              Make this model available in selection flows.
            </p>
          </div>
          <Switch
            :model-value="isEnabled"
            :aria-label="`Enable model for ${providerDisplayName}`"
            @update:model-value="isEnabled = Boolean($event)"
          />
        </div>

        <!-- 删除操作（仅 edit 模式）：AlertDialog 二次确认 -->
        <div
          v-if="mode === 'edit'"
          class="rounded-(--console-radius-md) border border-red-400/20 bg-red-400/10 p-3"
        >
          <AlertDialog>
            <AlertDialogTrigger as-child>
              <Button
                type="button"
                aria-label="Delete custom model"
                variant="destructive"
                size="sm"
                :disabled="isMutating"
              >
                Delete model
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent
              class="border-(--line) bg-[#101113] shadow-[0_28px_90px_rgba(0,0,0,0.54)]"
            >
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this model?</AlertDialogTitle>
                <AlertDialogDescription>
                  This removes the custom model profile from
                  {{ providerDisplayName }}.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  class="bg-red-500 text-white hover:bg-red-500/90"
                  @click="handleDelete"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>

        <p v-if="localError" class="text-xs leading-5 text-red-100">
          {{ localError }}
        </p>
      </div>

      <DialogFooter
        class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
      >
        <Button
          type="button"
          aria-label="Cancel custom model dialog"
          variant="outline"
          class="w-20"
          @click="open = false"
        >
          Cancel
        </Button>
        <Button
          type="button"
          aria-label="Save custom model"
          class="w-20"
          :disabled="isMutating"
          @click="handleSubmit"
        >
          {{ mode === "create" ? "Create" : "Save" }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
