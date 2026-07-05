<script setup lang="ts">
import { ref, watch } from "vue";

import type {
  AvailableProviderViewModel,
  ConnectOfficialProviderInput,
} from "@/console/services/provider-model";
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
  provider: AvailableProviderViewModel;
}>();

const emit = defineEmits<{
  (
    event: "connectProvider",
    providerUid: string,
    input: ConnectOfficialProviderInput,
  ): void;
}>();

const open = ref(false);
const apiKey = ref("");
const localError = ref<string | null>(null);

// 每次打开重置输入
watch(open, (nextOpen) => {
  if (nextOpen) {
    apiKey.value = "";
    localError.value = null;
  }
});

function handleConnect(): void {
  const key = apiKey.value.trim();

  if (!key) {
    localError.value = "API key is required.";
    return;
  }

  localError.value = null;
  emit("connectProvider", props.provider.uid, { apiKey: key });
  open.value = false;
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button
        type="button"
        :aria-label="`Connect ${provider.displayName} provider`"
        variant="outline"
        size="sm"
        class="border-(--line-soft) bg-(--surface-panel-soft)"
      >
        Connect
      </Button>
    </DialogTrigger>
    <DialogContent
      class="overflow-hidden border-(--line) bg-[#101113] p-0 shadow-[0_28px_90px_rgba(0,0,0,0.54)] sm:max-w-[28rem]"
    >
      <DialogHeader class="border-b border-(--line-soft) px-5 py-4 text-left">
        <DialogTitle>Connect {{ provider.displayName }}</DialogTitle>
        <DialogDescription>
          Add an API key to enable this provider.
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-2 px-5 py-5">
        <Label :for="`${provider.uid}-api-key`">API key</Label>
        <Input
          :id="`${provider.uid}-api-key`"
          v-model="apiKey"
          type="password"
          placeholder="sk-..."
        />
        <p v-if="localError" class="text-xs leading-5 text-red-100">
          {{ localError }}
        </p>
      </div>

      <DialogFooter
        class="border-t border-(--line-soft) px-5 py-4 sm:justify-end"
      >
        <Button
          type="button"
          :aria-label="`Cancel ${provider.displayName} connection`"
          variant="outline"
          class="w-20"
          @click="open = false"
        >
          Cancel
        </Button>
        <Button
          type="button"
          :aria-label="`Connect ${provider.displayName} provider`"
          class="w-20"
          :disabled="isMutating"
          @click="handleConnect"
        >
          Connect
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
