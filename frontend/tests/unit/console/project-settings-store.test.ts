import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/services/project-settings", () => ({
  createGeneralSettingsForm: vi.fn((project) => ({
    name: project.name,
    description: project.description ?? "",
  })),
  createVisitorSettingsForm: vi.fn((settings) => settings.form),
  deleteProject: vi.fn(),
  loadProjectSettings: vi.fn(),
  updateProjectGeneral: vi.fn(),
  updateProjectVisitorSettings: vi.fn(),
  validateGeneralSettings: vi.fn(() => ({})),
  validateVisitorSettings: vi.fn(() => ({})),
}));
vi.mock("@/console/stores/provider-model", () => ({
  useProviderModelStore: () => ({
    enabledProviders: [],
    loadEnabledWorkspace: vi.fn().mockResolvedValue([]),
  }),
}));

import {
  loadProjectSettings,
  updateProjectGeneral,
  updateProjectVisitorSettings,
  validateGeneralSettings,
} from "@/console/services/project-settings";
import { useProjectSettingsStore } from "@/console/stores/project-settings";

const visitorForm = {
  providerUid: "provider-1",
  modelUid: "model-1",
  thinkingLevel: "off",
  systemPrompt: "",
  ragEnabled: true,
  ragMode: "adaptive",
  ragTopK: "8",
  rerankEnabled: true,
  standaloneEnabled: false,
  maxOutputTokens: "1024",
  timeout: "30",
  temperature: "0.7",
  topP: "1",
  ftsK: "30",
  vectorK: "20",
  rerankK: "12",
  maxAlternativeQueries: "2",
  maxKeywords: "5",
};

function workspace(uid: string, name: string) {
  return {
    project: { uid, name, description: null },
    settings: { form: { ...visitorForm } },
  };
}

describe("project settings store", () => {
  it("加载后建立 draft/baseline，编辑后正确计算 dirty", async () => {
    vi.mocked(loadProjectSettings).mockResolvedValue(
      workspace("project-1", "Demo") as never,
    );
    const store = useProjectSettingsStore();

    await store.load("project-1");
    expect(store).toMatchObject({
      project: { uid: "project-1", name: "Demo" },
      generalDraft: { name: "Demo", description: "" },
      isGeneralDirty: false,
      isVisitorDirty: false,
      isInitialLoading: false,
    });

    store.setGeneralDraft({ name: "Changed", description: "" });
    store.setVisitorDraft({ ...visitorForm, ragTopK: "12" } as never);
    expect(store.isGeneralDirty).toBe(true);
    expect(store.isVisitorDirty).toBe(true);
  });

  it("校验失败不保存；成功保存后用响应更新 baseline", async () => {
    vi.mocked(loadProjectSettings).mockResolvedValue(
      workspace("project-1", "Demo") as never,
    );
    const store = useProjectSettingsStore();
    await store.load("project-1");
    store.setGeneralDraft({ name: "", description: "" });
    vi.mocked(validateGeneralSettings).mockReturnValue({ name: "Required" });

    await expect(store.saveGeneral()).resolves.toBe(false);
    expect(updateProjectGeneral).not.toHaveBeenCalled();
    expect(store.generalFieldErrors).toEqual({ name: "Required" });

    vi.mocked(validateGeneralSettings).mockReturnValue({});
    store.setGeneralDraft({ name: "Saved", description: "Description" });
    vi.mocked(updateProjectGeneral).mockResolvedValue({
      uid: "project-1",
      name: "Saved",
      description: "Description",
    } as never);
    await expect(store.saveGeneral()).resolves.toBe(true);

    expect(updateProjectGeneral).toHaveBeenCalledWith(
      "project-1",
      { name: "Saved", description: "Description" },
      { name: "Demo", description: "" },
    );
    expect(store.generalDraft).toEqual({
      name: "Saved",
      description: "Description",
    });
    expect(store.isGeneralDirty).toBe(false);
  });

  it("保存 visitor 设置后同步 draft/baseline", async () => {
    vi.mocked(loadProjectSettings).mockResolvedValue(
      workspace("project-1", "Demo") as never,
    );
    vi.mocked(updateProjectVisitorSettings).mockResolvedValue({
      form: { ...visitorForm, ragTopK: "12" },
    } as never);
    const store = useProjectSettingsStore();
    await store.load("project-1");
    store.setVisitorDraft({ ...visitorForm, ragTopK: "12" } as never);

    await expect(store.saveVisitor()).resolves.toBe(true);
    expect(updateProjectVisitorSettings).toHaveBeenCalledWith(
      "project-1",
      { ...visitorForm, ragTopK: "12" },
      visitorForm,
    );
    expect(store.visitorDraft).toMatchObject({ ragTopK: "12" });
    expect(store.isVisitorDirty).toBe(false);
  });

  it("忽略过期 load 响应，避免旧项目覆盖当前状态", async () => {
    let resolveOld!: (value: unknown) => void;
    let resolveNew!: (value: unknown) => void;
    vi.mocked(loadProjectSettings).mockImplementation(
      (uid) =>
        new Promise((resolve) => {
          if (uid === "old") resolveOld = resolve;
          else resolveNew = resolve;
        }) as never,
    );
    const store = useProjectSettingsStore();

    const oldLoad = store.load("old");
    const newLoad = store.load("new");
    resolveNew(workspace("new", "New"));
    await newLoad;
    resolveOld(workspace("old", "Old"));
    await oldLoad;

    expect(store.project).toMatchObject({ uid: "new", name: "New" });
    expect(store.isInitialLoading).toBe(false);
  });
});
