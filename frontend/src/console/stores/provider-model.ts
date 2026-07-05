import { computed, ref } from "vue";
import { defineStore } from "pinia";

import type {
  ModelProfileRead,
  ProviderRead,
  ProviderWithModelsRead,
} from "@/console/api/provider-model";
import { getErrorMessage } from "@/console/lib/api-result";
import {
  connectOfficialProvider as connectOfficialProviderRequest,
  createCustomModel as createCustomModelRequest,
  createCustomProvider as createCustomProviderRequest,
  createProviderModelWorkspace,
  deleteModel as deleteModelRequest,
  deleteProvider as deleteProviderRequest,
  listEnabledProvidersWithModels,
  listProvidersWithModels,
  providerModelErrors,
  updateModel as updateModelRequest,
  updateProvider as updateProviderRequest,
  type ConnectOfficialProviderInput,
  type CreateCustomModelInput,
  type CreateCustomProviderInput,
  type UpdateCustomModelInput,
  type UpdateProviderInput,
} from "@/console/services/provider-model";

type LoadOptions = {
  silent?: boolean;
};

/** Provider-model 共享状态，供配置页与后续 chat 选择流复用。 */
export const useProviderModelStore = defineStore(
  "console-provider-model",
  () => {
    // === 核心状态 ===
    const providers = ref<ProviderWithModelsRead[]>([]);
    const enabledProviders = ref<ProviderWithModelsRead[]>([]);
    const isLoading = ref(false);
    const isMutating = ref(false);
    const errorMessage = ref<string | null>(null);

    // === 派生数据：通过 workspace 工厂拆分为各组 ViewModel ===
    const workspace = computed(() =>
      createProviderModelWorkspace(providers.value),
    );

    const savedProviders = computed(() => workspace.value.savedProviders);
    const availableProviders = computed(
      () => workspace.value.availableProviders,
    );
    const officialModelGroups = computed(
      () => workspace.value.officialModelGroups,
    );
    const customModelGroups = computed(() => workspace.value.customModelGroups);

    // === 数据加载 ===
    async function loadWorkspace(
      options: LoadOptions = {},
    ): Promise<ProviderWithModelsRead[]> {
      return await withLoading(
        providerModelErrors.loadWorkspace,
        async () => {
          const providerList = await listProvidersWithModels();
          providers.value = providerList;
          return providerList;
        },
        options,
      );
    }

    async function loadEnabledWorkspace(
      options: LoadOptions = {},
    ): Promise<ProviderWithModelsRead[]> {
      return await withLoading(
        providerModelErrors.loadEnabledWorkspace,
        async () => {
          const providerList = await listEnabledProvidersWithModels();
          enabledProviders.value = providerList;
          return providerList;
        },
        options,
      );
    }

    // === Provider 变更操作（含状态更新） ===
    async function connectOfficialProvider(
      providerUid: string,
      input: ConnectOfficialProviderInput,
    ): Promise<ProviderRead> {
      return await withMutation(
        providerModelErrors.connectProvider,
        async () => {
          const provider = await connectOfficialProviderRequest(
            providerUid,
            input,
          );
          patchProvider(provider);
          return provider;
        },
      );
    }

    async function createCustomProvider(
      input: CreateCustomProviderInput,
    ): Promise<ProviderWithModelsRead> {
      return await withMutation(
        providerModelErrors.createProvider,
        async () => {
          const provider = await createCustomProviderRequest(input);
          upsertProvider(provider);
          return provider;
        },
      );
    }

    async function updateProvider(
      providerUid: string,
      input: UpdateProviderInput,
    ): Promise<ProviderRead> {
      return await withMutation(
        providerModelErrors.updateProvider,
        async () => {
          const provider = await updateProviderRequest(providerUid, input);
          patchProvider(provider);
          return provider;
        },
      );
    }

    async function deleteProvider(providerUid: string): Promise<void> {
      await withMutation(providerModelErrors.deleteProvider, async () => {
        await deleteProviderRequest(providerUid);
        removeProvider(providerUid);
      });
    }

    // === Model 变更操作 ===
    async function createCustomModel(
      providerUid: string,
      input: CreateCustomModelInput,
    ): Promise<ModelProfileRead> {
      return await withMutation(providerModelErrors.createModel, async () => {
        const model = await createCustomModelRequest(providerUid, input);
        upsertModel(providerUid, model);
        return model;
      });
    }

    async function updateModel(
      providerUid: string,
      modelUid: string,
      input: UpdateCustomModelInput,
    ): Promise<ModelProfileRead> {
      return await withMutation(providerModelErrors.updateModel, async () => {
        const model = await updateModelRequest(providerUid, modelUid, input);
        upsertModel(providerUid, model);
        return model;
      });
    }

    async function deleteModel(
      providerUid: string,
      modelUid: string,
    ): Promise<void> {
      await withMutation(providerModelErrors.deleteModel, async () => {
        await deleteModelRequest(providerUid, modelUid);
        removeModel(providerUid, modelUid);
      });
    }

    async function toggleProviderEnabled(
      providerUid: string,
      isEnabled: boolean,
    ): Promise<ProviderRead> {
      return await updateProvider(providerUid, { isEnabled });
    }

    async function toggleModelEnabled(
      providerUid: string,
      modelUid: string,
      isEnabled: boolean,
    ): Promise<ModelProfileRead> {
      return await updateModel(providerUid, modelUid, { isEnabled });
    }

    // === 本地状态更新：避免全量 reload ===
    function getProvider(providerUid: string): ProviderWithModelsRead | null {
      return (
        providers.value.find((provider) => provider.uid === providerUid) ?? null
      );
    }

    function upsertProvider(provider: ProviderWithModelsRead): void {
      const exists = providers.value.some((item) => item.uid === provider.uid);
      providers.value = exists
        ? providers.value.map((item) =>
            item.uid === provider.uid ? provider : item,
          )
        : [provider, ...providers.value];
    }

    function patchProvider(provider: ProviderRead): void {
      providers.value = providers.value.map((item) =>
        item.uid === provider.uid
          ? {
              ...item,
              ...provider,
              modelProfiles: item.modelProfiles ?? [],
            }
          : item,
      );
    }

    function removeProvider(providerUid: string): void {
      providers.value = providers.value.filter(
        (provider) => provider.uid !== providerUid,
      );
      enabledProviders.value = enabledProviders.value.filter(
        (provider) => provider.uid !== providerUid,
      );
    }

    function upsertModel(providerUid: string, model: ModelProfileRead): void {
      providers.value = providers.value.map((provider) => {
        if (provider.uid !== providerUid) {
          return provider;
        }

        const models = provider.modelProfiles ?? [];
        const exists = models.some((item) => item.uid === model.uid);
        return {
          ...provider,
          modelProfiles: exists
            ? models.map((item) => (item.uid === model.uid ? model : item))
            : [...models, model],
        };
      });
    }

    function removeModel(providerUid: string, modelUid: string): void {
      providers.value = providers.value.map((provider) =>
        provider.uid === providerUid
          ? {
              ...provider,
              modelProfiles: (provider.modelProfiles ?? []).filter(
                (model) => model.uid !== modelUid,
              ),
            }
          : provider,
      );
    }

    // === 加载 / 变更包装器：统一 isLoading / isMutating / errorMessage ===
    async function withLoading<T>(
      fallbackMessage: string,
      task: () => Promise<T>,
      options: LoadOptions = {},
    ): Promise<T> {
      if (!options.silent) {
        isLoading.value = true;
      }
      errorMessage.value = null;

      try {
        return await task();
      } catch (error) {
        errorMessage.value = getErrorMessage(error, fallbackMessage);
        throw error;
      } finally {
        if (!options.silent) {
          isLoading.value = false;
        }
      }
    }

    async function withMutation<T>(
      fallbackMessage: string,
      task: () => Promise<T>,
    ): Promise<T> {
      isMutating.value = true;
      errorMessage.value = null;

      try {
        return await task();
      } catch (error) {
        errorMessage.value = getErrorMessage(error, fallbackMessage);
        throw error;
      } finally {
        isMutating.value = false;
      }
    }

    return {
      availableProviders,
      connectOfficialProvider,
      createCustomModel,
      createCustomProvider,
      customModelGroups,
      deleteModel,
      deleteProvider,
      enabledProviders,
      errorMessage,
      getProvider,
      isLoading,
      isMutating,
      loadEnabledWorkspace,
      loadWorkspace,
      officialModelGroups,
      providers,
      savedProviders,
      toggleModelEnabled,
      toggleProviderEnabled,
      updateModel,
      updateProvider,
      workspace,
    };
  },
);
