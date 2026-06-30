<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import {
  createProjectWidget,
  deleteProjectWidget,
  importProjectSources,
  loadProjectWorkspace,
  unbindProjectSource,
  updateProjectWidget,
  type CreateProjectInput,
  type ProjectWidgetCreate,
  type ProjectWidgetUpdate,
  type ProjectWorkspaceViewModel,
} from "@/console/services/project-workspace";
import { useProjectStore } from "@/console/stores/project";

import ProjectLandingState from "./ProjectLandingState.vue";
import ProjectOverviewState from "./ProjectOverviewState.vue";

const route = useRoute();
const router = useRouter();
const projectStore = useProjectStore();
const {
  errorMessage: storeErrorMessage,
  isLoading,
  projects,
} = storeToRefs(projectStore);

// 页面容器只持有 workspace 状态；project 选择态由 Pinia 共享。
const workspace = ref<ProjectWorkspaceViewModel | null>(null);
const isInitialLoading = ref(true);
const isWorkspaceLoading = ref(false);
const isMutating = ref(false);
const pageErrorMessage = ref<string | null>(null);
const actionMessage = ref<string | null>(null);

const routeProjectUid = computed(() => getProjectUidFromRoute());
const routeErrorMessage = computed(() =>
  route.query.error === "project-not-found" ? "Project not found." : null,
);

onMounted(async () => {
  await handleProjectRoute(routeProjectUid.value);
});

watch(
  () => route.params.projectUid,
  async () => {
    await handleProjectRoute(routeProjectUid.value);
  },
);

/**
 * 根据 path param 决定渲染 landing 或 overview。
 */
async function handleProjectRoute(projectUid: string | null) {
  isInitialLoading.value = true;
  pageErrorMessage.value = null;
  actionMessage.value = null;

  try {
    await projectStore.loadProjects();

    if (!projectUid) {
      projectStore.clearSelection();
      workspace.value = null;
      return;
    }

    const exists = await projectStore.selectProject(projectUid);
    if (!exists) {
      await redirectToProjectLanding();
      return;
    }

    await refreshWorkspace(projectUid);
  } catch (error) {
    pageErrorMessage.value = getErrorMessage(
      error,
      "Unable to load project page.",
    );
  } finally {
    isInitialLoading.value = false;
  }
}

// 刷新当前 project workspace 数据
async function refreshWorkspace(projectUid = routeProjectUid.value) {
  if (!projectUid) {
    return;
  }

  isWorkspaceLoading.value = true;
  pageErrorMessage.value = null;

  try {
    workspace.value = await loadProjectWorkspace(projectUid);
  } catch (error) {
    await redirectToProjectLanding();
  } finally {
    isWorkspaceLoading.value = false;
  }
}

// 创建 project 操作
async function handleCreateProject(input: CreateProjectInput) {
  if (!input.name.trim()) {
    actionMessage.value = "Project name is required.";
    return;
  }

  isMutating.value = true;
  actionMessage.value = null;

  try {
    await projectStore.createProject(input);
  } catch (error) {
    actionMessage.value = getErrorMessage(error, "Unable to create project.");
  } finally {
    isMutating.value = false;
  }
}

async function handleImportSources(sourceUids: string[]) {
  if (!routeProjectUid.value || sourceUids.length === 0) {
    return;
  }

  await runProjectMutation(async () => {
    await importProjectSources(routeProjectUid.value as string, sourceUids);
  });
}

async function handleUnbindSource(sourceUid: string) {
  if (!routeProjectUid.value) {
    return;
  }

  await runProjectMutation(async () => {
    await unbindProjectSource(routeProjectUid.value as string, sourceUid);
  });
}

async function handleCreateWidget(input: ProjectWidgetCreate) {
  if (!routeProjectUid.value) {
    return;
  }

  await runProjectMutation(async () => {
    await createProjectWidget(routeProjectUid.value as string, input);
  });
}

async function handleUpdateWidget(input: {
  widgetUid: string;
  payload: ProjectWidgetUpdate;
}) {
  if (!routeProjectUid.value) {
    return;
  }

  await runProjectMutation(async () => {
    await updateProjectWidget(
      routeProjectUid.value as string,
      input.widgetUid,
      input.payload,
    );
  });
}

async function handleDeleteWidget(widgetUid: string) {
  if (!routeProjectUid.value) {
    return;
  }

  const shouldDelete = window.confirm("Delete this widget deployment?");
  if (!shouldDelete) {
    return;
  }

  await runProjectMutation(async () => {
    await deleteProjectWidget(routeProjectUid.value as string, widgetUid);
  });
}

async function handleOpenSource(sourceUid: string) {
  await router.push({
    path: "/sources",
    query: { sourceUid },
  });
}

async function handleOpenGlobalSources() {
  await router.push({ path: "/sources" });
}

async function handleSelectProject(projectUid: string) {
  await router.push({
    name: "project-overview",
    params: { projectUid },
  });
}

// project 相关操作入口函数
async function runProjectMutation(action: () => Promise<void>) {
  isMutating.value = true;
  actionMessage.value = null;

  try {
    await action();
    // 写操作后统一刷新，确保 metrics/health/table rows 同步。
    await refreshWorkspace();
  } catch (error) {
    actionMessage.value = getErrorMessage(error, "Project action failed.");
  } finally {
    isMutating.value = false;
  }
}

async function redirectToProjectLanding() {
  projectStore.clearSelection("Project not found.");
  workspace.value = null;
  await router.replace({
    name: "project-landing",
    query: { error: "project-not-found" },
  });
}

function getProjectUidFromRoute(): string | null {
  const value = route.params.projectUid;
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : null;
  }

  return typeof value === "string" && value ? value : null;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
</script>

<template>
  <!-- 加载骨架组件 -->
  <section v-if="isInitialLoading" class="console-page">
    <div class="grid gap-4">
      <div class="tadaask-skeleton h-8 w-48 rounded-md"></div>
      <div class="tadaask-skeleton h-20 w-full max-w-2xl rounded-md"></div>
      <div class="grid grid-cols-4 gap-4 max-[1180px]:grid-cols-2">
        <div
          v-for="item in 4"
          :key="item"
          class="tadaask-skeleton h-32 rounded-(--console-radius-lg)"
        ></div>
      </div>
    </div>
  </section>

  <ProjectLandingState
    v-else-if="!routeProjectUid"
    :error-message="
      actionMessage ??
      routeErrorMessage ??
      pageErrorMessage ??
      storeErrorMessage
    "
    :is-loading="isLoading"
    :is-submitting="isMutating || isLoading"
    :projects="projects"
    @create="handleCreateProject"
    @open-global-sources="handleOpenGlobalSources"
    @select-project="handleSelectProject"
  />

  <section v-else-if="workspace" class="grid gap-4">
    <div
      v-if="pageErrorMessage || actionMessage"
      class="rounded-(--console-radius-md) border border-yellow-300/25 bg-yellow-300/10 px-4 py-3 text-sm text-yellow-100"
    >
      {{ actionMessage ?? pageErrorMessage }}
    </div>

    <!-- Project 数据 overview view -->
    <ProjectOverviewState
      :workspace="workspace"
      :is-mutating="isMutating || isWorkspaceLoading"
      @create-widget="handleCreateWidget"
      @delete-widget="handleDeleteWidget"
      @import-sources="handleImportSources"
      @open-global-sources="handleOpenGlobalSources"
      @open-source="handleOpenSource"
      @unbind-source="handleUnbindSource"
      @update-widget="handleUpdateWidget"
    />
  </section>

  <section v-else class="console-panel grid gap-3 p-6">
    <h1 class="console-panel-title">Project unavailable</h1>
    <p class="console-panel-note">
      The selected project could not be loaded. Choose another project from the
      sidebar.
    </p>
  </section>
</template>
