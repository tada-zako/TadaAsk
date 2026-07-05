<script setup lang="ts">
import { useI18n } from "vue-i18n";

import CustomProviderCreateDialog from "./CustomProviderCreateDialog.vue";
import ProviderConnectDialog from "./ProviderConnectDialog.vue";
import ProviderManageDialog from "./ProviderManageDialog.vue";
import type {
  AvailableProviderEntryViewModel,
  ConnectOfficialProviderInput,
  CreateCustomProviderInput,
  ProviderModelStatusTone,
  ProviderRowViewModel,
  UpdateProviderInput,
} from "@/console/services/provider-model";
import { Badge } from "@/shared/components/ui/badge";

defineProps<{
  availableProviders: AvailableProviderEntryViewModel[];
  isLoading?: boolean;
  isMutating?: boolean;
  savedProviders: ProviderRowViewModel[];
}>();

const emit = defineEmits<{
  (
    event: "connectProvider",
    providerUid: string,
    input: ConnectOfficialProviderInput,
  ): void;
  (event: "createProvider", input: CreateCustomProviderInput): void;
  (
    event: "updateProvider",
    providerUid: string,
    input: UpdateProviderInput,
  ): void;
  (event: "deleteProvider", providerUid: string): void;
}>();

const { t } = useI18n();

function statusBadgeClass(tone: ProviderModelStatusTone): string {
  if (tone === "success") {
    return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  }

  return "border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)";
}
</script>

<template>
  <section class="console-section">
    <div class="console-section-head">
      <div>
        <h2 class="console-section-title">
          {{ t("providerModel.providers.title") }}
        </h2>
        <p class="console-section-note">
          {{ t("providerModel.providers.note") }}
        </p>
      </div>
    </div>

    <div class="grid max-w-[56.25rem] gap-7">
      <!-- 已保存的 provider：管理已有凭证和端点配置 -->
      <section class="console-panel overflow-hidden">
        <div class="console-panel-header">
          <div>
            <h3 class="console-panel-title">
              {{ t("providerModel.providers.savedTitle") }}
            </h3>
            <p class="console-panel-note">
              {{ t("providerModel.providers.savedNote") }}
            </p>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="isLoading" class="px-4 py-5 text-sm text-(--text-muted)">
          {{ t("providerModel.providers.loadingSaved") }}
        </div>
        <!-- 空状态 -->
        <div
          v-else-if="!savedProviders.length"
          class="px-4 py-5 text-sm text-(--text-muted)"
        >
          {{ t("providerModel.providers.emptySaved") }}
        </div>

        <!-- provider 列表：v-for 遍历，ProviderManageDialog 管理操作 -->
        <div v-else class="grid gap-0">
          <article
            v-for="(provider, index) in savedProviders"
            :key="provider.uid"
            class="grid min-h-22 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3.5"
            :class="{
              'border-b border-(--line-soft)':
                index < savedProviders.length - 1,
            }"
          >
            <div
              class="grid size-10 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              {{ provider.initial }}
            </div>
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  {{ provider.displayName }}
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  {{ provider.badgeLabel }}
                </Badge>
                <Badge
                  variant="outline"
                  class="text-[11px]"
                  :class="statusBadgeClass(provider.statusTone)"
                >
                  {{ provider.statusLabel }}
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                {{ provider.description }}
              </p>
            </div>
            <ProviderManageDialog
              :is-mutating="isMutating"
              :provider="provider"
              @delete-provider="
                (providerUid) => emit('deleteProvider', providerUid)
              "
              @update-provider="
                (providerUid, input) =>
                  emit('updateProvider', providerUid, input)
              "
            />
          </article>
        </div>
      </section>

      <!-- 可连接的 provider：官方目录 + 自定义端点入口 -->
      <section class="console-panel overflow-hidden">
        <div class="console-panel-header">
          <div>
            <h3 class="console-panel-title">
              {{ t("providerModel.providers.availableTitle") }}
            </h3>
            <p class="console-panel-note">
              {{ t("providerModel.providers.availableNote") }}
            </p>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="isLoading" class="px-4 py-5 text-sm text-(--text-muted)">
          {{ t("providerModel.providers.loadingAvailable") }}
        </div>
        <!-- 列表：kind === 'provider' → ProviderConnectDialog，否则 → CustomProviderCreateDialog -->
        <div v-else class="grid gap-0">
          <article
            v-for="(entry, index) in availableProviders"
            :key="entry.kind === 'provider' ? entry.uid : entry.kind"
            class="grid min-h-18 grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3"
            :class="{
              'border-b border-(--line-soft)':
                index < availableProviders.length - 1,
            }"
          >
            <div
              class="grid size-9 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-raised)"
            >
              {{ entry.initial }}
            </div>
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-(--text-strong)">
                  {{ entry.displayName }}
                </h4>
                <Badge
                  variant="outline"
                  class="border-(--line-soft) bg-(--surface-panel-soft) text-[11px] text-(--text-muted)"
                >
                  {{ entry.badgeLabel }}
                </Badge>
                <Badge
                  v-if="entry.kind === 'provider'"
                  variant="outline"
                  class="text-[11px]"
                  :class="statusBadgeClass(entry.statusTone)"
                >
                  {{ entry.statusLabel }}
                </Badge>
              </div>
              <p class="mt-1 truncate text-xs text-(--text-faint)">
                {{ entry.description }}
              </p>
            </div>

            <ProviderConnectDialog
              v-if="entry.kind === 'provider'"
              :is-mutating="isMutating"
              :provider="entry"
              @connect-provider="
                (providerUid, input) =>
                  emit('connectProvider', providerUid, input)
              "
            />
            <CustomProviderCreateDialog
              v-else
              :is-mutating="isMutating"
              @create-provider="(input) => emit('createProvider', input)"
            />
          </article>
        </div>
      </section>
    </div>
  </section>
</template>
