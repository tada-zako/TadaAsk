<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import { Button } from "@/shared/components/ui/button";
import { useProjectStore } from "@/console/stores/project";

const route = useRoute();
const router = useRouter();
const projectStore = useProjectStore();
const { selectedProject } = storeToRefs(projectStore);

// 获取路由参数中的项目 UID
const projectUid = computed(() => String(route.params.projectUid ?? ""));
// 根据路由名称计算页面标签
const pageLabel = computed(() =>
  route.name === "project-settings" ? "Settings" : "Ask",
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
    <p class="console-kicker">{{ selectedProject?.name ?? "Project" }}</p>
    <h1 class="console-panel-title">Project {{ pageLabel }}</h1>
    <p class="console-panel-note">
      This route is reserved for the project-scoped {{ pageLabel }} page.
    </p>
    <div>
      <Button
        type="button"
        aria-label="Back to project overview"
        variant="outline"
        @click="
          router.push({
            name: 'project-overview',
            params: { projectUid },
          })
        "
      >
        Overview
      </Button>
    </div>
  </section>
</template>
