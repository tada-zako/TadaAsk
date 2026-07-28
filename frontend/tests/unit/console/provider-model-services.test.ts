import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/api/provider-model", () => ({
  providerModelApi: {
    createProvider: vi.fn(),
    updateModel: vi.fn(),
  },
}));

import { providerModelApi } from "@/console/api/provider-model";
import {
  createCustomProvider,
  createProviderModelWorkspace,
  updateModel,
} from "@/console/services/provider-model";

describe("provider/model service", () => {
  it("创建自定义 provider 时去重 model 名称并建立默认 model 能力", async () => {
    vi.mocked(providerModelApi.createProvider).mockResolvedValue({
      data: { uid: "provider-1" },
      error: undefined,
    } as never);

    await createCustomProvider({
      name: "  Internal Gateway ",
      baseUrl: "  https://models.example.com  ",
      apiKey: "  key-1  ",
      modelNames: [" gpt-4 ", "", "gpt-4", "claude"],
    });

    expect(providerModelApi.createProvider).toHaveBeenCalledWith({
      name: "Internal Gateway",
      baseUrl: "https://models.example.com",
      apiKey: "key-1",
      isEnabled: true,
      isCustom: true,
      modelProfiles: [
        {
          model: "gpt-4",
          contextWindowTokens: null,
          maxOutputTokens: null,
          supportsStream: true,
          supportsStructured: true,
          isEnabled: true,
        },
        {
          model: "claude",
          contextWindowTokens: null,
          maxOutputTokens: null,
          supportsStream: true,
          supportsStructured: true,
          isEnabled: true,
        },
      ],
    });
  });

  it("更新 model 时将无效 token 限制转换为 null", async () => {
    vi.mocked(providerModelApi.updateModel).mockResolvedValue({
      data: { uid: "model-1" },
      error: undefined,
    } as never);

    await updateModel("provider-1", "model-1", {
      model: "  gpt-next ",
      contextWindowTokens: -1,
      maxOutputTokens: 2048.9,
      isEnabled: false,
    });

    expect(providerModelApi.updateModel).toHaveBeenCalledWith(
      "provider-1",
      "model-1",
      {
        model: "gpt-next",
        contextWindowTokens: null,
        maxOutputTokens: 2048,
        isEnabled: false,
      },
    );
  });

  it("按已保存状态与 provider 类型构建 workspace", () => {
    const workspace = createProviderModelWorkspace([
      {
        uid: "catalog-only",
        name: "openai",
        isCustom: false,
        isEnabled: true,
        encryptedApiKey: null,
        baseUrl: null,
        modelProfiles: [],
      },
      {
        uid: "official-saved",
        name: "deepseek",
        isCustom: false,
        isEnabled: true,
        encryptedApiKey: "encrypted",
        baseUrl: null,
        modelProfiles: [],
      },
      {
        uid: "custom",
        name: "team_gateway",
        isCustom: true,
        isEnabled: false,
        encryptedApiKey: null,
        baseUrl: "https://models.example.com",
        modelProfiles: [],
      },
    ] as never);

    expect(workspace.savedProviders.map((item) => item.uid)).toEqual([
      "official-saved",
      "custom",
    ]);
    expect(workspace.availableProviders).toHaveLength(2);
    expect(workspace.officialModelGroups).toHaveLength(1);
    expect(workspace.customModelGroups).toHaveLength(1);
  });
});
