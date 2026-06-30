<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  createProject,
  createProjectWidget,
  deleteProjectWidget,
  importProjectSources,
  listProjectOptions,
  loadProjectWorkspace,
  resolveProjectUid,
  unbindProjectSource,
  updateProjectWidget,
  type CreateProjectInput,
  type ProjectOption,
  type ProjectWidgetCreate,
  type ProjectWidgetUpdate,
  type ProjectWorkspaceViewModel,
} from "@/console/services/project-workspace";

import ProjectCreateState from "./ProjectCreateState.vue";
import ProjectOverviewState from "./ProjectOverviewState.vue";

const route = useRoute();
const router = useRouter();

// 页面容器只持有响应式状态；API 聚合和展示清洗放在 service 层。
const projects = ref<ProjectOption[]>([]);
const selectedProjectUid = ref<string | null>(null);
const workspace = ref<ProjectWorkspaceViewModel | null>(null);
const isInitialLoading = ref(true);
const isWorkspaceLoading = ref(false);
const isMutating = ref(false);
const errorMessage = ref<string | null>(null);
const actionMessage = ref<string | null>(null);

const hasProjects = computed(() => projects.value.length > 0);

onMounted(async () => {
  // 页面挂在时初始化页面数据
  await initializeProjectPage(getProjectUidFromRoute());
});

watch(
  () => route.query.projectUid,
  async (projectUid) => {
    // URL query 是当前 project 的可刷新入口。
    const nextProjectUid = getProjectUidFromQuery(projectUid);

    if (!nextProjectUid || nextProjectUid === selectedProjectUid.value) {
      return;
    }

    await selectProject(nextProjectUid);
  },
);

/**
 * 基于当前选中的 projectUid 初始化页面数据。
 * @param preferredProjectUid
 */
async function initializeProjectPage(preferredProjectUid: string | null) {
  isInitialLoading.value = true;
  errorMessage.value = null;

  try {
    projects.value = await listProjectOptions();
    const nextProjectUid = resolveProjectUid(
      projects.value,
      preferredProjectUid,
    );

    if (!nextProjectUid) {
      // 无 project 时保留空状态，交给 create state 渲染。
      selectedProjectUid.value = null;
      workspace.value = null;
      await replaceProjectQuery(null);
      return;
    }

    selectedProjectUid.value = nextProjectUid;
    await replaceProjectQuery(nextProjectUid);
    await refreshWorkspace(nextProjectUid);
  } catch (error) {
    errorMessage.value = getErrorMessage(error, "Unable to load project page.");
  } finally {
    isInitialLoading.value = false;
  }
}

// 选择 project 行为内部逻辑
async function selectProject(projectUid: string) {
  const nextProjectUid = resolveProjectUid(projects.value, projectUid);

  if (!nextProjectUid) {
    await initializeProjectPage(projectUid);
    return;
  }

  selectedProjectUid.value = nextProjectUid;
  await replaceProjectQuery(nextProjectUid);
  await refreshWorkspace(nextProjectUid);
}

// 刷新当前 project workspace 数据
async function refreshWorkspace(projectUid = selectedProjectUid.value) {
  if (!projectUid) {
    return;
  }

  isWorkspaceLoading.value = true;
  errorMessage.value = null;

  try {
    workspace.value = await loadProjectWorkspace(projectUid);
  } catch (error) {
    errorMessage.value = getErrorMessage(error, "Unable to refresh project.");
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
    const project = await createProject(input);
    projects.value = await listProjectOptions();
    selectedProjectUid.value = project.uid;
    // 通知外层 sidebar 刷新 projects 列表
    window.dispatchEvent(new Event("tadaask:projects-updated"));
    await replaceProjectQuery(project.uid);
    await refreshWorkspace(project.uid);
  } catch (error) {
    actionMessage.value = getErrorMessage(error, "Unable to create project.");
  } finally {
    isMutating.value = false;
  }
}

async function handleImportSources(sourceUids: string[]) {
  if (!selectedProjectUid.value || sourceUids.length === 0) {
    return;
  }

  await runProjectMutation(async () => {
    await importProjectSources(selectedProjectUid.value as string, sourceUids);
  });
}

async function handleUnbindSource(sourceUid: string) {
  if (!selectedProjectUid.value) {
    return;
  }

  await runProjectMutation(async () => {
    await unbindProjectSource(selectedProjectUid.value as string, sourceUid);
  });
}

async function handleCreateWidget(input: ProjectWidgetCreate) {
  if (!selectedProjectUid.value) {
    return;
  }

  await runProjectMutation(async () => {
    await createProjectWidget(selectedProjectUid.value as string, input);
  });
}

async function handleUpdateWidget(input: {
  widgetUid: string;
  payload: ProjectWidgetUpdate;
}) {
  if (!selectedProjectUid.value) {
    return;
  }

  await runProjectMutation(async () => {
    await updateProjectWidget(
      selectedProjectUid.value as string,
      input.widgetUid,
      input.payload,
    );
  });
}

async function handleDeleteWidget(widgetUid: string) {
  if (!selectedProjectUid.value) {
    return;
  }

  const shouldDelete = window.confirm("Delete this widget deployment?");
  if (!shouldDelete) {
    return;
  }

  await runProjectMutation(async () => {
    await deleteProjectWidget(selectedProjectUid.value as string, widgetUid);
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

async function replaceProjectQuery(projectUid: string | null) {
  const nextQuery = { ...route.query };

  if (projectUid) {
    nextQuery.projectUid = projectUid;
  } else {
    delete nextQuery.projectUid;
  }

  await router.replace({ query: nextQuery });
}

function getProjectUidFromRoute(): string | null {
  return getProjectUidFromQuery(route.query.projectUid);
}

function getProjectUidFromQuery(value: unknown): string | null {
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

  <!-- Project 创建 view -->
  <ProjectCreateState
    v-else-if="!hasProjects"
    :error-message="actionMessage ?? errorMessage"
    :is-submitting="isMutating"
    @create="handleCreateProject"
  />

  <section v-else-if="workspace" class="grid gap-4">
    <div
      v-if="errorMessage || actionMessage"
      class="rounded-(--console-radius-md) border border-yellow-300/25 bg-yellow-300/10 px-4 py-3 text-sm text-yellow-100"
    >
      {{ actionMessage ?? errorMessage }}
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
