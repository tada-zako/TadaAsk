<script setup lang="ts">
import { computed, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";
import { RotateCw } from "@lucide/vue";

import ProjectDangerZonePanel from "@/console/components/project/ProjectDangerZonePanel.vue";
import ProjectGeneralSettingsPanel from "@/console/components/project/ProjectGeneralSettingsPanel.vue";
import ProjectVisitorSettingsPanel from "@/console/components/project/ProjectVisitorSettingsPanel.vue";
import { useProjectSettingsStore } from "@/console/stores/project-settings";
import { Button } from "@/shared/components/ui/button";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const settingsStore = useProjectSettingsStore();
// 将 store 中所有响应式状态解构为 ref，模板中直接使用而不需要通过 store.xxx
const {
  deleteError,
  enabledProviders,
  generalDraft,
  generalError,
  generalFieldErrors,
  isDeleting,
  isGeneralDirty,
  isInitialLoading,
  isSavingGeneral,
  isSavingVisitor,
  isVisitorDirty,
  loadError,
  project,
  settings,
  visitorDraft,
  visitorError,
  visitorFieldErrors,
} = storeToRefs(settingsStore);

// 从路由参数中提取 projectUid，兼容数组/字符串两种路由参数格式
const routeProjectUid = computed(() => {
  const value = route.params.projectUid;
  if (Array.isArray(value))
    return typeof value[0] === "string" ? value[0] : null;
  return typeof value === "string" && value ? value : null;
});

// 路由 projectUid 变化时重新加载数据；immediate 确保首屏即触发
// Store 内部通过 loadSequence 防止竞态，旧请求返回时直接丢弃
watch(
  routeProjectUid,
  async (projectUid) => {
    if (!projectUid) {
      await redirectToProjectLanding();
      return;
    }
    try {
      await settingsStore.load(projectUid);
    } catch {
      // load 已在 store 内设置了 loadError，此处仅需静默
    }
  },
  { immediate: true },
);

// 离开页面时清空 store，避免下次进入闪现旧数据
onUnmounted(() => settingsStore.clear());

async function retryLoad(): Promise<void> {
  if (!routeProjectUid.value) return;
  try {
    await settingsStore.load(routeProjectUid.value);
  } catch {
    // Store 已保存可展示的错误信息。
  }
}

async function handleDelete(): Promise<void> {
  if (await settingsStore.deleteCurrentProject())
    await redirectToProjectLanding();
}

async function redirectToProjectLanding(): Promise<void> {
  await router.replace({ name: "project-landing" });
}
</script>

<template>
  <section v-if="isInitialLoading" class="console-page max-w-[56.25rem]">
    <div class="grid gap-4">
      <div class="tadaask-skeleton h-4 w-28 rounded-md"></div>
      <div class="tadaask-skeleton h-10 w-72 rounded-md"></div>
      <div class="tadaask-skeleton h-16 w-full max-w-2xl rounded-md"></div>
      <div
        v-for="item in 3"
        :key="item"
        class="tadaask-skeleton h-64 rounded-(--console-radius-lg)"
      ></div>
    </div>
  </section>

  <!-- 错误提示 -->
  <section
    v-else-if="
      loadError || !project || !settings || !generalDraft || !visitorDraft
    "
    class="console-page max-w-[56.25rem]"
  >
    <section class="console-panel grid justify-items-start gap-3 p-6">
      <h1 class="console-panel-title">
        {{ t("project.settings.page.unavailableTitle") }}
      </h1>
      <p class="console-panel-note">
        {{ loadError ?? t("project.settings.page.unavailableBody") }}
      </p>
      <Button type="button" variant="outline" @click="retryLoad"
        ><RotateCw class="size-3.5" />{{
          t("project.settings.page.retry")
        }}</Button
      >
    </section>
  </section>

  <!-- settings header 区域 -->
  <section v-else class="console-page max-w-[56.25rem]">
    <header class="console-page-head">
      <p class="console-kicker">{{ project.name }}</p>
      <h1
        class="text-[clamp(1.95rem,2.7vw,2.25rem)] leading-[1.12] font-bold text-(--text-strong)"
      >
        {{ t("project.settings.page.title") }}
      </h1>
      <p class="console-page-subtitle max-w-[43.75rem]">
        {{ t("project.settings.page.subtitle") }}
      </p>
    </header>

    <ProjectGeneralSettingsPanel
      :form="generalDraft"
      :project-uid="project.uid"
      :field-errors="generalFieldErrors"
      :error-message="generalError"
      :is-dirty="isGeneralDirty"
      :is-saving="isSavingGeneral"
      @update:form="settingsStore.setGeneralDraft"
      @save="settingsStore.saveGeneral"
    />
    <ProjectVisitorSettingsPanel
      :form="visitorDraft"
      :settings="settings"
      :enabled-providers="enabledProviders"
      :field-errors="visitorFieldErrors"
      :error-message="visitorError"
      :is-dirty="isVisitorDirty"
      :is-saving="isSavingVisitor"
      @update:form="settingsStore.setVisitorDraft"
      @save="settingsStore.saveVisitor"
    />
    <ProjectDangerZonePanel
      :project-name="project.name"
      :is-deleting="isDeleting"
      :error-message="deleteError"
      @confirm="handleDelete"
    />
  </section>
</template>
