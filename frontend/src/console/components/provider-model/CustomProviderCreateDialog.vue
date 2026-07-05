<script setup lang="ts">
import { ref, watch } from "vue";
import { X } from "@lucide/vue";

import type { CreateCustomProviderInput } from "@/console/services/provider-model";
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

const props = defineProps<{
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "createProvider", input: CreateCustomProviderInput): void;
}>();

const open = ref(false);
const providerName = ref("");
const baseUrl = ref("");
const apiKey = ref("");
// 初始模型名列表，至少保留一行
const modelNames = ref([""]);
const localError = ref<string | null>(null);

// 每次打开重置
watch(open, (nextOpen) => {
  if (nextOpen) {
    resetForm();
  }
});

function addModelRow(): void {
  modelNames.value = [...modelNames.value, ""];
}

function removeModelRow(index: number): void {
  modelNames.value =
    modelNames.value.length > 1
      ? modelNames.value.filter((_, itemIndex) => itemIndex !== index)
      : [""];
}

// 创建：校验名称/URL/key 必填
function handleCreate(): void {
  const name = providerName.value.trim();
  const endpoint = baseUrl.value.trim();
  const key = apiKey.value.trim();

  if (!name) {
    localError.value = "Provider name is required.";
    return;
  }

  if (!endpoint) {
    localError.value = "Base URL is required.";
    return;
  }

  if (!key) {
    localError.value = "API key is required.";
    return;
  }

  localError.value = null;
  emit("createProvider", {
    name,
    baseUrl: endpoint,
    apiKey: key,
    modelNames: modelNames.value,
  });
  open.value = false;
}

function resetForm(): void {
  providerName.value = "";
  baseUrl.value = "";
  apiKey.value = "";
  modelNames.value = [""];
  localError.value = null;
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button
        type="button"
        aria-label="Create custom provider"
        variant="outline"
        size="sm"
        class="border-(--line-soft) bg-(--surface-panel-soft)"
      >
        Connect
      </Button>
    </DialogTrigger>
    <DialogContent
      class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[36rem]"
    >
      <DialogHeader class="border-b border-(--line-soft) px-5 py-4 text-left">
        <DialogTitle>Create custom provider</DialogTitle>
        <DialogDescription>
          Define the endpoint, credential, and initial model names.
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-4 px-5 py-5">
        <!-- Provider 名称 -->
        <div class="grid gap-2">
          <Label for="custom-provider-name">Provider name</Label>
          <Input
            id="custom-provider-name"
            v-model="providerName"
            placeholder="Qoder gateway"
          />
        </div>

        <!-- Base URL -->
        <div class="grid gap-2">
          <Label for="custom-provider-base-url">Base URL</Label>
          <Input
            id="custom-provider-base-url"
            v-model="baseUrl"
            placeholder="https://api.example.com/v1"
          />
        </div>

        <!-- API key -->
        <div class="grid gap-2">
          <Label for="custom-provider-key">API key</Label>
          <Input
            id="custom-provider-key"
            v-model="apiKey"
            type="password"
            placeholder="sk-..."
          />
        </div>

        <!-- 初始模型名列表：动态行，每行带删除按钮 -->
        <div class="grid gap-2">
          <Label>Models</Label>
          <div class="grid gap-2">
            <div
              v-for="(_, index) in modelNames"
              :key="index"
              class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2"
            >
              <Input
                v-model="modelNames[index]"
                :placeholder="index === 0 ? 'qoder-coder' : 'qoder-lite'"
              />
              <Button
                type="button"
                :aria-label="`Remove custom model row ${index + 1}`"
                variant="ghost"
                size="icon-sm"
                @click="removeModelRow(index)"
              >
                <X class="size-4" />
              </Button>
            </div>
          </div>
          <Button
            type="button"
            aria-label="Add another custom provider model"
            variant="ghost"
            size="sm"
            class="text-primary hover:text-primary h-auto w-fit border-0 bg-transparent p-0 text-[13px] font-semibold hover:bg-transparent"
            @click="addModelRow"
          >
            + Add model
          </Button>
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
          aria-label="Cancel custom provider creation"
          variant="outline"
          class="w-20"
          @click="open = false"
        >
          Cancel
        </Button>
        <Button
          type="button"
          aria-label="Create custom provider"
          class="w-20"
          :disabled="props.isMutating"
          @click="handleCreate"
        >
          Create
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
