<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";

import { Button } from "@/shared/components/ui/button";
import { useProjectStore } from "@/console/stores/project";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const projectStore = useProjectStore();
const { selectedProject } = storeToRefs(projectStore);

// 获取路由参数中的项目 UID
const projectUid = computed(() => String(route.params.projectUid ?? ""));
// 根据路由名称计算页面标签
const pageLabel = computed(() =>
  route.name === "project-settings"
    ? t("project.reserved.settings")
    : t("project.reserved.ask"),
);

// 监听项目 UID 变化，自动选中对应项目，若不存在则重定向至 landing 页
watch(
  projectUid,
  async (uid) => {
    if (!uid) {
      return;
    }

    const exists = await projectStore.selectProject(uid);
    if (!exists) {
      await router.replace({
        name: "project-landing",
        query: { error: "project-not-found" },
      });
    }
  },
  { immediate: true },
);
</script>

<template>
  <!-- 预留页面视图（用于 Ask 或 Settings 占位） -->
  <section class="console-panel grid gap-3 p-6">
    <p class="console-kicker">
      {{ selectedProject?.name ?? t("shell.breadcrumb.project") }}
    </p>
    <h1 class="console-panel-title">
      {{ t("project.reserved.title", { label: pageLabel }) }}
    </h1>
    <p class="console-panel-note">
      {{ t("project.reserved.description", { label: pageLabel }) }}
    </p>
    <div>
      <Button
        type="button"
        :aria-label="t('project.reserved.backToOverview')"
        variant="outline"
        @click="
          router.push({
            name: 'project-overview',
            params: { projectUid },
          })
        "
      >
        {{ t("common.actions.overview") }}
      </Button>
    </div>
  </section>
</template>
