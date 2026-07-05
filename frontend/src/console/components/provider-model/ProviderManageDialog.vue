<!--
  管理 provider Dialog
  - 官方 provider：仅可修改 API key 和启用状态
  - 自定义 provider：可修改名称/Base URL/API key，含删除操作
-->
<script setup lang="ts">
import { ref, watch } from "vue";

import type {
  ProviderRowViewModel,
  UpdateProviderInput,
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
  provider: ProviderRowViewModel;
}>();

const emit = defineEmits<{
  (
    event: "updateProvider",
    providerUid: string,
    input: UpdateProviderInput,
  ): void;
  (event: "deleteProvider", providerUid: string): void;
}>();

const open = ref(false);
const providerName = ref("");
const baseUrl = ref("");
const apiKey = ref("");
const isEnabled = ref(false);
const localError = ref<string | null>(null);

// 每次打开/切换 provider 时重置表单
watch(open, (nextOpen) => {
  if (nextOpen) {
    resetForm();
  }
});

watch(
  () => props.provider,
  () => {
    if (open.value) {
      resetForm();
    }
  },
);

// 保存：自定义 provider 需校验名称/URL/key，官方仅校验 key
function handleSave(): void {
  const payload: UpdateProviderInput = {
    isEnabled: isEnabled.value,
  };
  const key = apiKey.value.trim();

  if (props.provider.isCustom) {
    // 只允许自定义模型设置 provider name + endpoint url
    const name = providerName.value.trim();
    const endpoint = baseUrl.value.trim();

    if (!name) {
      localError.value = "Provider name is required.";
      return;
    }

    if (isEnabled.value && !endpoint) {
      localError.value = "Base URL is required when enabled.";
      return;
    }

    if (isEnabled.value && !props.provider.hasApiKey && !key) {
      localError.value = "API key is required when enabled.";
      return;
    }

    payload.name = name;
    payload.baseUrl = endpoint;
  }

  if (key) {
    payload.apiKey = key;
  }

  localError.value = null;
  emit("updateProvider", props.provider.uid, payload);
  open.value = false;
}

// 删除（仅自定义 provider 可用）
function handleDelete(): void {
  emit("deleteProvider", props.provider.uid);
  open.value = false;
}

function resetForm(): void {
  providerName.value = props.provider.displayName;
  baseUrl.value = props.provider.baseUrl ?? "";
  apiKey.value = "";
  isEnabled.value = props.provider.isEnabled;
  localError.value = null;
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button
        type="button"
        :aria-label="`Manage ${provider.displayName} provider`"
        variant="outline"
        size="sm"
        class="border-(--line-soft) bg-(--surface-panel-soft)"
      >
        Manage
      </Button>
    </DialogTrigger>
    <DialogContent
      class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[34rem]"
    >
      <DialogHeader class="border-b border-(--line-soft) px-5 py-4 text-left">
        <DialogTitle>
          {{
            provider.isCustom
              ? "Manage provider"
              : `Manage ${provider.displayName}`
          }}
        </DialogTitle>
        <DialogDescription>
          Update the provider credential and availability.
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-4 px-5 py-5">
        <!-- 自定义 provider：可编辑名称和 Base URL -->
        <div v-if="provider.isCustom" class="grid gap-2">
          <Label for="manage-provider-name">Provider name</Label>
          <Input id="manage-provider-name" v-model="providerName" />
        </div>

        <div v-if="provider.isCustom" class="grid gap-2">
          <Label for="manage-provider-base-url">Base URL</Label>
          <Input id="manage-provider-base-url" v-model="baseUrl" />
        </div>

        <!-- API key（共通）：留空保留现有 key -->
        <div class="grid gap-2">
          <Label :for="`${provider.uid}-manage-api-key`">API key</Label>
          <Input
            :id="`${provider.uid}-manage-api-key`"
            v-model="apiKey"
            type="password"
            placeholder="Leave blank to keep existing key"
          />
          <p
            v-if="!provider.isCustom"
            class="text-xs leading-5 text-(--text-faint)"
          >
            Official providers keep their catalog name and base URL.
          </p>
        </div>

        <!-- 启用开关：自定义/官方文案不同 -->
        <div
          class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
        >
          <div>
            <p class="text-sm font-medium text-(--text-strong)">
              Enable provider
            </p>
            <p class="mt-1 text-xs text-(--text-faint)">
              {{
                provider.isCustom
                  ? "Custom providers require a base URL and API key."
                  : "Available for model selection after saving."
              }}
            </p>
          </div>
          <Switch
            :model-value="isEnabled"
            :aria-label="`Enable ${provider.displayName} provider`"
            @update:model-value="isEnabled = Boolean($event)"
          />
        </div>

        <!-- 删除操作（仅自定义 provider）：AlertDialog 二次确认 -->
        <div
          v-if="provider.isCustom"
          class="rounded-(--console-radius-md) border border-red-400/20 bg-red-400/10 p-3"
        >
          <p class="text-sm font-medium text-red-100">Delete provider</p>
          <p class="mt-1 text-xs leading-5 text-red-100/65">
            Removes this custom provider and its custom model profiles.
          </p>
          <AlertDialog>
            <AlertDialogTrigger as-child>
              <Button
                type="button"
                :aria-label="`Delete ${provider.displayName} provider`"
                variant="destructive"
                size="sm"
                class="mt-3"
                :disabled="isMutating"
              >
                Delete provider
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent
              class="border-(--line) bg-[#101113] shadow-[0_28px_90px_rgba(0,0,0,0.54)]"
            >
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this provider?</AlertDialogTitle>
                <AlertDialogDescription>
                  This removes the custom provider and its model profiles.
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
          aria-label="Cancel provider management"
          variant="outline"
          class="w-20"
          @click="open = false"
        >
          Cancel
        </Button>
        <Button
          type="button"
          :aria-label="`Save ${provider.displayName} provider`"
          class="w-20"
          :disabled="isMutating"
          @click="handleSave"
        >
          Save
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
