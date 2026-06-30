import { computed, ref } from "vue";
import { defineStore } from "pinia";

import router from "@/console/router";
import {
  createProject as createProjectRequest,
  listProjectOptions,
  type CreateProjectInput,
  type ProjectOption,
} from "@/console/services/project-workspace";

/**
 * Project 共享状态。
 *
 * Store 只管理跨组件选择态；workspace 详情仍由 service + page view 加载。
 */
export const useProjectStore = defineStore("console-project", () => {
  // 状态定义
  const projects = ref<ProjectOption[]>([]);
  const selectedProjectUid = ref<string | null>(null);
  const isLoading = ref(false);
  const errorMessage = ref<string | null>(null);

  // 计算属性：当前选中的项目对象
  const selectedProject = computed(
    () =>
      projects.value.find(
        (project) => project.uid === selectedProjectUid.value,
      ) ?? null,
  );

  // 加载项目列表
  async function loadProjects(): Promise<ProjectOption[]> {
    isLoading.value = true;
    errorMessage.value = null;

    try {
      projects.value = await listProjectOptions();

      // 如果当前选中的项目已不存在，则清空选中态
      if (
        selectedProjectUid.value &&
        !projects.value.some(
          (project) => project.uid === selectedProjectUid.value,
        )
      ) {
        selectedProjectUid.value = null;
      }

      return projects.value;
    } catch (error) {
      errorMessage.value = getErrorMessage(error, "Unable to load projects.");
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

  // 刷新项目列表
  async function refreshProjects(): Promise<ProjectOption[]> {
    return await loadProjects();
  }

  // 选中指定项目
  async function selectProject(projectUid: string): Promise<boolean> {
    if (!projects.value.length) {
      await loadProjects();
    }

    const exists = projects.value.some((project) => project.uid === projectUid);

    if (!exists) {
      // 如果 projectUid 不存在情况
      selectedProjectUid.value = null;
      errorMessage.value = "Project not found.";
      return false;
    }

    selectedProjectUid.value = projectUid;
    errorMessage.value = null;
    return true;
  }

  // 清除项目选中态
  function clearSelection(message: string | null = null): void {
    selectedProjectUid.value = null;
    errorMessage.value = message;
  }

  // 创建新项目并自动选中，跳转
  async function createProject(
    input: CreateProjectInput,
  ): Promise<ProjectOption> {
    if (!input.name.trim()) {
      errorMessage.value = "Project name is required.";
      throw new Error(errorMessage.value);
    }

    isLoading.value = true;
    errorMessage.value = null;

    try {
      const project = await createProjectRequest(input);
      await refreshProjects();
      selectedProjectUid.value = project.uid;
      // 跳转到对应页面
      await router.push({
        name: "project-overview",
        params: { projectUid: project.uid },
      });

      return {
        description: project.description ?? null,
        name: project.name,
        uid: project.uid,
      };
    } catch (error) {
      errorMessage.value = getErrorMessage(error, "Unable to create project.");
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

  return {
    clearSelection,
    createProject,
    errorMessage,
    isLoading,
    loadProjects,
    projects,
    refreshProjects,
    selectProject,
    selectedProject,
    selectedProjectUid,
  };
});

// 提取错误信息
function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
