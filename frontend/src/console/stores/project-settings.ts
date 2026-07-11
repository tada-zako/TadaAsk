import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { translate as t } from "@/console/i18n";
import { getErrorMessage } from "@/console/lib/api-result";
import {
  createGeneralSettingsForm,
  createVisitorSettingsForm,
  deleteProject as deleteProjectRequest,
  loadProjectSettings,
  updateProjectGeneral,
  updateProjectVisitorSettings,
  validateGeneralSettings,
  validateVisitorSettings,
  type ProjectGeneralSettingsForm,
  type ProjectRead,
  type ProjectSettingsRead,
  type ProjectVisitorSettingsForm,
  type SettingsFieldErrors,
} from "@/console/services/project-settings";
import { useProjectStore } from "@/console/stores/project";
import { useProviderModelStore } from "@/console/stores/provider-model";

export const useProjectSettingsStore = defineStore(
  "console-project-settings",
  () => {
    const projectStore = useProjectStore();
    const providerModelStore = useProviderModelStore();

    // ---- 状态 ----
    const projectUid = ref<string | null>(null);
    const project = ref<ProjectRead | null>(null);
    const settings = ref<ProjectSettingsRead | null>(null);
    // draft=当前编辑中的表单，baseline=上次保存的快照，两者 JSON 比较得到 isDirty
    const generalDraft = ref<ProjectGeneralSettingsForm | null>(null);
    const generalBaseline = ref<ProjectGeneralSettingsForm | null>(null);
    const visitorDraft = ref<ProjectVisitorSettingsForm | null>(null);
    const visitorBaseline = ref<ProjectVisitorSettingsForm | null>(null);
    const generalFieldErrors = ref<SettingsFieldErrors>({});
    const visitorFieldErrors = ref<SettingsFieldErrors>({});
    const isInitialLoading = ref(false);
    const isSavingGeneral = ref(false);
    const isSavingVisitor = ref(false);
    const isDeleting = ref(false);
    const loadError = ref<string | null>(null);
    const generalError = ref<string | null>(null);
    const visitorError = ref<string | null>(null);
    const deleteError = ref<string | null>(null);
    // 递增序列号：load 时 ++，响应返回时比对，不匹配则丢弃旧结果
    let loadSequence = 0;

    // ---- 计算属性 ----
    const enabledProviders = computed(
      () => providerModelStore.enabledProviders,
    );
    const isGeneralDirty = computed(
      () => !sameForm(generalDraft.value, generalBaseline.value),
    );
    const isVisitorDirty = computed(
      () => !sameForm(visitorDraft.value, visitorBaseline.value),
    );

    // ---- 异步操作 ----
    // 加载项目设置 + 可用模型列表（并行）
    // 模型加载使用 silent 模式，失败不抛错——用户仍可编辑其他配置
    async function load(nextProjectUid: string): Promise<void> {
      const sequence = ++loadSequence;
      isInitialLoading.value = true;
      loadError.value = null;
      clearResource();
      projectUid.value = nextProjectUid;

      try {
        const [workspace] = await Promise.all([
          loadProjectSettings(nextProjectUid),
          providerModelStore
            .loadEnabledWorkspace({ silent: true })
            .catch(() => []),
        ]);
        // 竞态检查：如果在等待期间触发了新的 load，丢弃本次结果
        if (sequence !== loadSequence) return;
        project.value = workspace.project;
        settings.value = workspace.settings;
        generalDraft.value = createGeneralSettingsForm(workspace.project);
        generalBaseline.value = { ...generalDraft.value };
        visitorDraft.value = createVisitorSettingsForm(workspace.settings);
        visitorBaseline.value = { ...visitorDraft.value };
        // 同步到全局项目列表，确保侧栏即时反映名称变更
        projectStore.upsertProjectOption({
          uid: workspace.project.uid,
          name: workspace.project.name,
          description: workspace.project.description ?? null,
        });
        await projectStore.selectProject(nextProjectUid);
      } catch (error) {
        if (sequence === loadSequence) {
          loadError.value = getErrorMessage(
            error,
            t("project.service.errors.loadSettings"),
          );
        }
        throw error;
      } finally {
        if (sequence === loadSequence) isInitialLoading.value = false;
      }
    }

    // 子组件通过 emit 回传局部 patch，此处替换整个 draft 并清除旧的校验/错误状态
    function setGeneralDraft(form: ProjectGeneralSettingsForm): void {
      generalDraft.value = form;
      generalFieldErrors.value = {};
      generalError.value = null;
    }

    function setVisitorDraft(form: ProjectVisitorSettingsForm): void {
      visitorDraft.value = form;
      visitorFieldErrors.value = {};
      visitorError.value = null;
    }

    // 保存流程：校验 → 只发送变更字段 → 用 API 响应重建 draft+baseline
    async function saveGeneral(): Promise<boolean> {
      if (!projectUid.value || !generalDraft.value || !generalBaseline.value)
        return false;
      generalFieldErrors.value = validateGeneralSettings(generalDraft.value);
      if (Object.keys(generalFieldErrors.value).length) return false;
      isSavingGeneral.value = true;
      generalError.value = null;
      try {
        const updated = await updateProjectGeneral(
          projectUid.value,
          generalDraft.value,
          generalBaseline.value,
        );
        project.value = updated;
        generalDraft.value = createGeneralSettingsForm(updated);
        generalBaseline.value = { ...generalDraft.value };
        projectStore.upsertProjectOption({
          uid: updated.uid,
          name: updated.name,
          description: updated.description ?? null,
        });
        return true;
      } catch (error) {
        generalError.value = getErrorMessage(
          error,
          t("project.settings.errors.saveGeneral"),
        );
        return false;
      } finally {
        isSavingGeneral.value = false;
      }
    }

    async function saveVisitor(): Promise<boolean> {
      if (!projectUid.value || !visitorDraft.value || !visitorBaseline.value)
        return false;
      visitorFieldErrors.value = validateVisitorSettings(visitorDraft.value);
      if (Object.keys(visitorFieldErrors.value).length) return false;
      isSavingVisitor.value = true;
      visitorError.value = null;
      try {
        const updated = await updateProjectVisitorSettings(
          projectUid.value,
          visitorDraft.value,
          visitorBaseline.value,
        );
        settings.value = updated;
        visitorDraft.value = createVisitorSettingsForm(updated);
        visitorBaseline.value = { ...visitorDraft.value };
        return true;
      } catch (error) {
        visitorError.value = getErrorMessage(
          error,
          t("project.settings.errors.saveVisitor"),
        );
        return false;
      } finally {
        isSavingVisitor.value = false;
      }
    }

    async function deleteCurrentProject(): Promise<boolean> {
      if (!projectUid.value) return false;
      isDeleting.value = true;
      deleteError.value = null;
      try {
        const deletedUid = projectUid.value;
        await deleteProjectRequest(deletedUid);
        // 同步 sidebar 数据
        projectStore.removeProjectOption(deletedUid);
        clear();
        return true;
      } catch (error) {
        deleteError.value = getErrorMessage(
          error,
          t("project.settings.errors.deleteProject"),
        );
        return false;
      } finally {
        isDeleting.value = false;
      }
    }

    // clear 供页面卸载时调用：递增 sequence 让进行中的请求失效 → 清空资源
    function clear(): void {
      loadSequence += 1;
      projectUid.value = null;
      clearResource();
      isInitialLoading.value = false;
    }

    // load 开始时也调用 clearResource，确保切换项目时不会闪现旧数据
    function clearResource(): void {
      project.value = null;
      settings.value = null;
      generalDraft.value = null;
      generalBaseline.value = null;
      visitorDraft.value = null;
      visitorBaseline.value = null;
      generalFieldErrors.value = {};
      visitorFieldErrors.value = {};
      generalError.value = null;
      visitorError.value = null;
      deleteError.value = null;
    }

    return {
      clear,
      deleteCurrentProject,
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
      load,
      loadError,
      project,
      saveGeneral,
      saveVisitor,
      setGeneralDraft,
      setVisitorDraft,
      settings,
      visitorDraft,
      visitorError,
      visitorFieldErrors,
    };
  },
);

// JSON 序列化比较，用于判断 draft 是否相对 baseline 有修改（isDirty）
function sameForm<T>(left: T | null, right: T | null): boolean {
  return (
    left !== null &&
    right !== null &&
    JSON.stringify(left) === JSON.stringify(right)
  );
}
