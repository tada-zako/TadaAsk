import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/api/projects", () => ({
  projectApi: {
    update: vi.fn(),
    updateSettings: vi.fn(),
  },
}));

import { projectApi } from "@/console/api/projects";
import {
  createGeneralSettingsForm,
  createVisitorSettingsForm,
  updateProjectGeneral,
  updateProjectVisitorSettings,
  validateGeneralSettings,
  validateVisitorSettings,
  type ProjectVisitorSettingsForm,
} from "@/console/services/project-settings";

function visitorForm(
  overrides: Partial<ProjectVisitorSettingsForm> = {},
): ProjectVisitorSettingsForm {
  return {
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
    ...overrides,
  };
}

describe("project settings service", () => {
  it("从 API 设置创建表单草稿并处理 off thinking", () => {
    expect(
      createGeneralSettingsForm({ name: "Demo", description: null } as never),
    ).toEqual({ name: "Demo", description: "" });
    expect(
      createVisitorSettingsForm({
        visitorDefaultProvider: { uid: "provider-1" },
        visitorDefaultModelProfile: { uid: "model-1" },
        visitorThinking: false,
        visitorSystemPrompt: null,
        visitorRagEnabled: true,
        ragMode: "adaptive",
        ragTopK: 8,
        ragRerankEnabled: true,
        ragStandaloneEnabled: false,
        visitorMaxOutputTokens: 1024,
        visitorTimeout: 30,
        visitorTemperature: 0.7,
        visitorTopP: 1,
        ragFtsK: 30,
        ragVectorK: 20,
        ragRerankK: 12,
        ragMaxAlternativeQueries: 2,
        ragMaxKeywords: 5,
      } as never),
    ).toMatchObject({
      providerUid: "provider-1",
      thinkingLevel: "off",
      ragTopK: "8",
    });
  });

  it("校验必填、整数和数值边界", () => {
    expect(
      validateGeneralSettings({ name: "  ", description: "x" }),
    ).toHaveProperty("name");
    const errors = validateVisitorSettings(
      visitorForm({
        maxOutputTokens: "1.5",
        timeout: "0",
        topP: "1.1",
        maxAlternativeQueries: "11",
        maxKeywords: "",
      }),
    );

    expect(errors).toMatchObject({
      maxOutputTokens: expect.any(String),
      timeout: expect.any(String),
      topP: expect.any(String),
      maxAlternativeQueries: expect.any(String),
      maxKeywords: expect.any(String),
    });
  });

  it("保存 general settings 时只提交规范化后的差异", async () => {
    vi.mocked(projectApi.update).mockResolvedValue({
      data: { uid: "project-1" },
      error: undefined,
    } as never);

    await updateProjectGeneral(
      "project-1",
      { name: "  New Name ", description: "  " },
      { name: "Old Name", description: "Existing" },
    );

    expect(projectApi.update).toHaveBeenCalledWith("project-1", {
      name: "New Name",
      description: null,
    });
  });

  it("保存 visitor settings 时转换数值且成对提交 provider/model 变化", async () => {
    vi.mocked(projectApi.updateSettings).mockResolvedValue({
      data: { projectUid: "project-1" },
      error: undefined,
    } as never);
    const baseline = visitorForm();
    const form = visitorForm({
      providerUid: "provider-2",
      modelUid: "model-2",
      thinkingLevel: "high",
      systemPrompt: "  Be concise  ",
      ragTopK: "12",
      temperature: "0.2",
    });

    await updateProjectVisitorSettings("project-1", form, baseline);

    expect(projectApi.updateSettings).toHaveBeenCalledWith("project-1", {
      visitorSystemPrompt: "Be concise",
      visitorThinking: "high",
      ragTopK: 12,
      visitorTemperature: 0.2,
      visitorDefaultProviderUid: "provider-2",
      visitorDefaultModelProfileUid: "model-2",
    });
  });
});
