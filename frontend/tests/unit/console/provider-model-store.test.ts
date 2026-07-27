import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/services/provider-model", () => ({
  connectOfficialProvider: vi.fn(),
  createCustomModel: vi.fn(),
  createCustomProvider: vi.fn(),
  createProviderModelWorkspace: vi.fn((providers) => ({
    savedProviders: providers,
    availableProviders: [],
    officialModelGroups: [],
    customModelGroups: [],
  })),
  deleteModel: vi.fn(),
  deleteProvider: vi.fn(),
  listEnabledProvidersWithModels: vi.fn(),
  listProvidersWithModels: vi.fn(),
  providerModelError: vi.fn((key) => key),
  updateModel: vi.fn(),
  updateProvider: vi.fn(),
}));

import {
  listEnabledProvidersWithModels,
  listProvidersWithModels,
  updateModel,
  updateProvider,
} from "@/console/services/provider-model";
import { useProviderModelStore } from "@/console/stores/provider-model";

function provider(uid: string, models: unknown[] = []) {
  return {
    uid,
    name: uid,
    isCustom: false,
    isEnabled: true,
    encryptedApiKey: "key",
    baseUrl: null,
    modelProfiles: models,
  };
}

describe("provider model store", () => {
  it("分别加载 workspace 与启用 provider，并公开派生选择数据", async () => {
    vi.mocked(listProvidersWithModels).mockResolvedValue([
      provider("provider-1"),
    ] as never);
    vi.mocked(listEnabledProvidersWithModels).mockResolvedValue([
      provider("provider-2"),
    ] as never);
    const store = useProviderModelStore();

    await store.loadWorkspace();
    await store.loadEnabledWorkspace();

    expect(store.providers).toMatchObject([{ uid: "provider-1" }]);
    expect(store.enabledProviders).toMatchObject([{ uid: "provider-2" }]);
    expect(store.savedProviders).toMatchObject([{ uid: "provider-1" }]);
    expect(store.isLoading).toBe(false);
  });

  it("切换 provider/model 启用状态后更新本地实体", async () => {
    const store = useProviderModelStore();
    store.providers = [
      provider("provider-1", [
        {
          uid: "model-1",
          model: "gpt",
          isEnabled: true,
          supportsStream: true,
          supportsStructured: true,
        },
      ]),
    ] as never;
    vi.mocked(updateProvider).mockResolvedValue({
      uid: "provider-1",
      name: "provider-1",
      isEnabled: false,
      isCustom: false,
      encryptedApiKey: "key",
      baseUrl: null,
    } as never);
    vi.mocked(updateModel).mockResolvedValue({
      uid: "model-1",
      model: "gpt",
      isEnabled: false,
      supportsStream: true,
      supportsStructured: true,
    } as never);

    await store.toggleProviderEnabled("provider-1", false);
    await store.toggleModelEnabled("provider-1", "model-1", false);

    expect(store.getProvider("provider-1")).toMatchObject({ isEnabled: false });
    expect(store.getProvider("provider-1")?.modelProfiles).toMatchObject([
      { uid: "model-1", isEnabled: false },
    ]);
    expect(store.isMutating).toBe(false);
  });

  it("加载失败后复位 loading 并保存错误信息", async () => {
    vi.mocked(listProvidersWithModels).mockRejectedValue(
      new Error("provider offline"),
    );
    const store = useProviderModelStore();

    await expect(store.loadWorkspace()).rejects.toThrow("provider offline");
    expect(store).toMatchObject({
      isLoading: false,
      errorMessage: "provider offline",
    });
  });
});
