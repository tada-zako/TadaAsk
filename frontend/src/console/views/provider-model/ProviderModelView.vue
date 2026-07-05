<script setup lang="ts">
import { ref } from "vue";

import ModelAvailabilitySection from "@/console/components/provider-model/ModelAvailabilitySection.vue";
import ProviderSettingsSection from "@/console/components/provider-model/ProviderSettingsSection.vue";

// 当前激活的子视图标签：providers → 凭证与端点管理，models → 模型可用性管理
const activeSection = ref<"providers" | "models">("providers");
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

    <!-- 根据当前标签条件渲染对应子视图 -->
    <ProviderSettingsSection v-if="activeSection === 'providers'" />
    <ModelAvailabilitySection v-else />
  </section>
</template>
