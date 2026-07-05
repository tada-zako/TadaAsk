<script setup lang="ts">
import { onMounted, ref } from "vue";
import { storeToRefs } from "pinia";

import ModelAvailabilitySection from "@/console/components/provider-model/ModelAvailabilitySection.vue";
import ProviderSettingsSection from "@/console/components/provider-model/ProviderSettingsSection.vue";
import { useProviderModelStore } from "@/console/stores/provider-model";
import type {
  ConnectOfficialProviderInput,
  CreateCustomModelInput,
  CreateCustomProviderInput,
  UpdateCustomModelInput,
  UpdateProviderInput,
} from "@/console/services/provider-model";

// 当前激活的子视图标签：providers → 凭证与端点管理，models → 模型可用性管理
const activeSection = ref<"providers" | "models">("providers");
const providerModelStore = useProviderModelStore();
// 从 store 解构响应式状态，通过 storeToRefs 保持响应性
const {
  availableProviders,
  customModelGroups,
  errorMessage,
  isLoading,
  isMutating,
  officialModelGroups,
  savedProviders,
} = storeToRefs(providerModelStore);

// 页面挂载时加载 workspace 数据
onMounted(() => {
  void providerModelStore.loadWorkspace();
});

async function handleConnectProvider(
  providerUid: string,
  input: ConnectOfficialProviderInput,
): Promise<void> {
  await providerModelStore.connectOfficialProvider(providerUid, input);
}

async function handleCreateProvider(
  input: CreateCustomProviderInput,
): Promise<void> {
  await providerModelStore.createCustomProvider(input);
}

async function handleUpdateProvider(
  providerUid: string,
  input: UpdateProviderInput,
): Promise<void> {
  await providerModelStore.updateProvider(providerUid, input);
}

async function handleDeleteProvider(providerUid: string): Promise<void> {
  await providerModelStore.deleteProvider(providerUid);
}

async function handleCreateModel(
  providerUid: string,
  input: CreateCustomModelInput,
): Promise<void> {
  await providerModelStore.createCustomModel(providerUid, input);
}

async function handleUpdateModel(
  providerUid: string,
  modelUid: string,
  input: UpdateCustomModelInput,
): Promise<void> {
  await providerModelStore.updateModel(providerUid, modelUid, input);
}

async function handleDeleteModel(
  providerUid: string,
  modelUid: string,
): Promise<void> {
  await providerModelStore.deleteModel(providerUid, modelUid);
}

async function handleToggleModel(
  providerUid: string,
  modelUid: string,
  isEnabled: boolean,
): Promise<void> {
  await providerModelStore.toggleModelEnabled(providerUid, modelUid, isEnabled);
}
</script>

<template>
  <section class="console-page">
    <!-- 页面 header：标题和副标题根据当前标签动态切换 -->
    <header class="console-page-head">
      <p class="console-kicker">Global configuration</p>
      <h1 class="console-page-title">
        {{ activeSection === "providers" ? "Providers" : "Models" }}
      </h1>
      <p class="console-page-subtitle">
        {{
          activeSection === "providers"
            ? "Connect providers and keep model availability simple. Project settings and chat will only use enabled providers and models."
            : "Choose which saved provider models can be selected by project settings and admin chat."
        }}
      </p>
    </header>

    <!-- Providers / Models 标签切换：选中项高亮，未选中项变色 -->
    <div
      class="inline-flex w-fit items-center gap-1 rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) p-1"
      aria-label="Provider model sections"
    >
      <button
        type="button"
        aria-label="Show providers"
        class="min-h-8 rounded-(--console-radius-sm) px-3 text-[13px] font-medium transition"
        :class="
          activeSection === 'providers'
            ? 'bg-(--surface-raised) text-(--text-strong)'
            : 'text-(--text-muted) hover:text-(--text-body)'
        "
        @click="activeSection = 'providers'"
      >
        Providers
      </button>
      <button
        type="button"
        aria-label="Show models"
        class="min-h-8 rounded-(--console-radius-sm) px-3 text-[13px] font-medium transition"
        :class="
          activeSection === 'models'
            ? 'bg-(--surface-raised) text-(--text-strong)'
            : 'text-(--text-muted) hover:text-(--text-body)'
        "
        @click="activeSection = 'models'"
      >
        Models
      </button>
    </div>

    <!-- 错误提示 -->
    <p
      v-if="errorMessage"
      class="max-w-[56.25rem] rounded-(--console-radius-md) border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-100"
    >
      {{ errorMessage }}
    </p>

    <!-- 根据当前标签条件渲染对应子视图 -->
    <ProviderSettingsSection
      v-if="activeSection === 'providers'"
      :available-providers="availableProviders"
      :is-loading="isLoading"
      :is-mutating="isMutating"
      :saved-providers="savedProviders"
      @connect-provider="handleConnectProvider"
      @create-provider="handleCreateProvider"
      @delete-provider="handleDeleteProvider"
      @update-provider="handleUpdateProvider"
    />
    <ModelAvailabilitySection
      v-else
      :custom-model-groups="customModelGroups"
      :is-loading="isLoading"
      :is-mutating="isMutating"
      :official-model-groups="officialModelGroups"
      @create-model="handleCreateModel"
      @delete-model="handleDeleteModel"
      @toggle-model="handleToggleModel"
      @update-model="handleUpdateModel"
    />
  </section>
</template>
