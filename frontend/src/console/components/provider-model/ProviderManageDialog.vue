<!--
  管理 provider Dialog
  - 官方 provider：仅可修改 API key 和启用状态
  - 自定义 provider：可修改名称/Base URL/API key，含删除操作
-->
<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

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
const { t } = useI18n();

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
      localError.value = t("providerModel.validation.providerNameRequired");
      return;
    }

    if (isEnabled.value && !endpoint) {
      localError.value = t(
        "providerModel.validation.baseUrlRequiredWhenEnabled",
      );
      return;
    }

    if (isEnabled.value && !props.provider.hasApiKey && !key) {
      localError.value = t(
        "providerModel.validation.apiKeyRequiredWhenEnabled",
      );
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
        :aria-label="
          t('providerModel.aria.manageProvider', {
            provider: provider.displayName,
          })
        "
        variant="outline"
        size="sm"
        class="border-(--line-soft) bg-(--surface-panel-soft)"
      >
        {{ t("providerModel.actions.manage") }}
      </Button>
    </DialogTrigger>
    <DialogContent
      class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[34rem]"
    >
      <DialogHeader class="border-b border-(--line-soft) px-5 py-4 text-left">
        <DialogTitle>
          {{
            provider.isCustom
              ? t("providerModel.dialogs.manageProviderTitle")
              : t("providerModel.dialogs.manageProviderNamedTitle", {
                  provider: provider.displayName,
                })
          }}
        </DialogTitle>
        <DialogDescription>
          {{ t("providerModel.dialogs.manageProviderDescription") }}
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-4 px-5 py-5">
        <!-- 自定义 provider：可编辑名称和 Base URL -->
        <div v-if="provider.isCustom" class="grid gap-2">
          <Label for="manage-provider-name">
            {{ t("providerModel.labels.providerName") }}
          </Label>
          <Input id="manage-provider-name" v-model="providerName" />
        </div>

        <div v-if="provider.isCustom" class="grid gap-2">
          <Label for="manage-provider-base-url">
            {{ t("providerModel.labels.baseUrl") }}
          </Label>
          <Input id="manage-provider-base-url" v-model="baseUrl" />
        </div>

        <!-- API key（共通）：留空保留现有 key -->
        <div class="grid gap-2">
          <Label :for="`${provider.uid}-manage-api-key`">
            {{ t("providerModel.labels.apiKey") }}
          </Label>
          <Input
            :id="`${provider.uid}-manage-api-key`"
            v-model="apiKey"
            type="password"
            :placeholder="t('providerModel.placeholders.keepExistingKey')"
          />
          <p
            v-if="!provider.isCustom"
            class="text-xs leading-5 text-(--text-faint)"
          >
            {{ t("providerModel.dialogs.officialProviderReadOnlyHelp") }}
          </p>
        </div>

        <!-- 启用开关：自定义/官方文案不同 -->
        <div
          class="flex items-center justify-between gap-4 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-3"
        >
          <div>
            <p class="text-sm font-medium text-(--text-strong)">
              {{ t("providerModel.dialogs.enableProvider") }}
            </p>
            <p class="mt-1 text-xs text-(--text-faint)">
              {{
                provider.isCustom
                  ? t("providerModel.dialogs.customProviderEnableHelp")
                  : t("providerModel.dialogs.officialProviderEnableHelp")
              }}
            </p>
          </div>
          <Switch
            :model-value="isEnabled"
            :aria-label="
              t('providerModel.aria.enableProvider', {
                provider: provider.displayName,
              })
            "
            @update:model-value="isEnabled = Boolean($event)"
          />
        </div>

        <!-- 删除操作（仅自定义 provider）：AlertDialog 二次确认 -->
        <div
          v-if="provider.isCustom"
          class="rounded-(--console-radius-md) border border-red-400/20 bg-red-400/10 p-3"
        >
          <p class="text-sm font-medium text-red-100">
            {{ t("providerModel.dialogs.deleteProvider") }}
          </p>
          <p class="mt-1 text-xs leading-5 text-red-100/65">
            {{ t("providerModel.dialogs.deleteProviderHelp") }}
          </p>
          <AlertDialog>
            <AlertDialogTrigger as-child>
              <Button
                type="button"
                :aria-label="
                  t('providerModel.aria.deleteProvider', {
                    provider: provider.displayName,
                  })
                "
                variant="destructive"
                size="sm"
                class="mt-3"
                :disabled="isMutating"
              >
                {{ t("providerModel.dialogs.deleteProvider") }}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent
              class="border-(--line) bg-[#101113] shadow-[0_28px_90px_rgba(0,0,0,0.54)]"
            >
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {{ t("providerModel.dialogs.deleteProviderConfirmTitle") }}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {{
                    t("providerModel.dialogs.deleteProviderConfirmDescription")
                  }}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{{
                  t("common.actions.cancel")
                }}</AlertDialogCancel>
                <AlertDialogAction
                  class="bg-red-500 text-white hover:bg-red-500/90"
                  @click="handleDelete"
                >
                  {{ t("common.actions.delete") }}
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
          :aria-label="t('providerModel.aria.cancelProviderManagement')"
          variant="outline"
          class="w-20"
          @click="open = false"
        >
          {{ t("common.actions.cancel") }}
        </Button>
        <Button
          type="button"
          :aria-label="
            t('providerModel.aria.saveProvider', {
              provider: provider.displayName,
            })
          "
          class="w-20"
          :disabled="isMutating"
          @click="handleSave"
        >
          {{ t("common.actions.save") }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
