import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  createDefaultRagOptions,
  deleteChatSession,
  listGlobalChatSessions,
  loadChatMessages,
  revertChatMessage,
  toMessageViewModels,
  toSessionViewModels,
  type ChatMessageViewModel,
  type ChatSessionViewModel,
  type HybridSearchRequest,
  type SearchMode,
  type ThinkingLevel,
} from "@/console/services/chat";
import type { ModelProfileRead } from "@/console/api/provider-model";
import { translate as t } from "@/console/i18n";
import { getErrorMessage } from "@/console/lib/api-result";
import { useProviderModelStore } from "@/console/stores/provider-model";
import { useSourceStore } from "@/console/stores/source";

type LoadOptions = {
  silent?: boolean;
};

export interface ChatModelOption {
  providerUid: string;
  providerName: string;
  providerDisplayName: string;
  modelUid: string;
  modelName: string;
  model: ModelProfileRead;
}

export interface ChatModelProviderGroup {
  providerUid: string;
  providerName: string;
  providerDisplayName: string;
  options: ChatModelOption[];
}

const chatStoreErrorKeys = {
  bootstrap: "chat.service.errors.bootstrap",
  deleteSession: "chat.service.errors.deleteSession",
  loadMessages: "chat.service.errors.loadMessages",
  loadSessions: "chat.service.errors.loadSessions",
  revertMessage: "chat.service.errors.revertMessage",
};

export const useGlobalChatStore = defineStore("console-global-chat", () => {
  const providerModelStore = useProviderModelStore();
  const sourceStore = useSourceStore();

  // ---- 核心状态 ----
  const sessions = ref<ChatSessionViewModel[]>([]);
  const activeSessionUid = ref<string | null>(null);
  const messages = ref<ChatMessageViewModel[]>([]);
  const draft = ref("");

  // ---- 用户配置：模型 / thinking / source / RAG / system prompt ----
  const selectedProviderUid = ref<string | null>(null);
  const selectedModelUid = ref<string | null>(null);
  const thinking = ref<ThinkingLevel>("medium");
  const selectedSourceUids = ref<string[]>([]);
  const ragOptions = ref<HybridSearchRequest>(createDefaultRagOptions());
  const adminSystemPrompt = ref("");

  const hasMoreBefore = ref(false);
  const hasMoreAfter = ref(false);
  const oldestSequence = ref<number | null>(null);
  const newestSequence = ref<number | null>(null);

  // ---- 加载 / 错误状态 ----
  const isBootstrapping = ref(false);
  const isLoadingSessions = ref(false);
  const isLoadingMessages = ref(false);
  const isMutating = ref(false);
  const errorMessage = ref<string | null>(null);

  // ---- 派生状态 ----
  const activeSession = computed(
    () =>
      sessions.value.find(
        (session) => session.uid === activeSessionUid.value,
      ) ?? null,
  );

  const threadTitle = computed(() => activeSession.value?.title);
  const selectedSourceCount = computed(() => selectedSourceUids.value.length);

  const modelOptions = computed<ChatModelOption[]>(() =>
    providerModelStore.enabledProviders.flatMap((provider) =>
      (provider.modelProfiles ?? [])
        .filter((model) => model.isEnabled)
        .map((model) => ({
          providerUid: provider.uid,
          providerName: provider.name,
          providerDisplayName: formatProviderDisplayName(provider.name),
          modelUid: model.uid,
          modelName: model.model,
          model,
        })),
    ),
  );

  // 按照 provider 聚合的 models 数据显示
  const modelOptionGroups = computed<ChatModelProviderGroup[]>(() =>
    providerModelStore.enabledProviders
      .map((provider) => {
        const providerDisplayName = formatProviderDisplayName(provider.name);
        const options = (provider.modelProfiles ?? [])
          .filter((model) => model.isEnabled)
          .map((model) => ({
            providerUid: provider.uid,
            providerName: provider.name,
            providerDisplayName,
            modelUid: model.uid,
            modelName: model.model,
            model,
          }));

        return {
          providerUid: provider.uid,
          providerName: provider.name,
          providerDisplayName,
          options,
        };
      })
      .filter((group) => group.options.length > 0),
  );

  const selectedModelOption = computed(
    () =>
      modelOptions.value.find(
        (option) =>
          option.providerUid === selectedProviderUid.value &&
          option.modelUid === selectedModelUid.value,
      ) ?? null,
  );

  const selectedModelLabel = computed(
    () =>
      selectedModelOption.value?.modelName ?? t("chat.composer.selectModel"),
  );

  const canSend = computed(
    () =>
      Boolean(draft.value.trim()) &&
      Boolean(selectedProviderUid.value) &&
      Boolean(selectedModelUid.value),
  );

  // ---- Actions ----
  async function bootstrap(initialSessionUid: string | null = null) {
    await withBootstrap(chatStoreError("bootstrap"), async () => {
      await Promise.all([
        loadSessions({ silent: true }),
        providerModelStore.loadEnabledWorkspace({ silent: true }),
        sourceStore.loadSources(),
      ]);

      ensureDefaultProviderModel();

      if (initialSessionUid) {
        await selectSession(initialSessionUid);
        return;
      }

      if (sessions.value[0]) {
        await selectSession(sessions.value[0].uid);
      }
    });
  }

  async function loadSessions(options: LoadOptions = {}) {
    await withLoadingSessions(
      chatStoreError("loadSessions"),
      async () => {
        const loadedSessions = await listGlobalChatSessions({
          limit: 50,
          offset: 0,
        });
        sessions.value = toSessionViewModels(loadedSessions);
      },
      options,
    );
  }

  async function selectSession(sessionUid: string) {
    activeSessionUid.value = sessionUid;
    await loadMessages(sessionUid);
  }

  function startNewSession() {
    activeSessionUid.value = null;
    messages.value = [];
    draft.value = "";
    resetMessagePage();
  }

  async function loadMessages(sessionUid = activeSessionUid.value) {
    if (!sessionUid) {
      messages.value = [];
      resetMessagePage();
      return;
    }

    await withLoadingMessages(chatStoreError("loadMessages"), async () => {
      const page = await loadChatMessages(sessionUid, {
        limit: 80,
        includeInternal: false,
      });
      messages.value = toMessageViewModels(page.messages);
      hasMoreBefore.value = page.hasMoreBefore;
      hasMoreAfter.value = page.hasMoreAfter;
      oldestSequence.value = page.oldestSequence ?? null;
      newestSequence.value = page.newestSequence ?? null;
    });
  }

  async function deleteSession(sessionUid: string) {
    await withMutation(chatStoreError("deleteSession"), async () => {
      await deleteChatSession(sessionUid);
      sessions.value = sessions.value.filter(
        (session) => session.uid !== sessionUid,
      );

      if (activeSessionUid.value === sessionUid) {
        const nextSession = sessions.value[0] ?? null;
        if (nextSession) {
          await selectSession(nextSession.uid);
        } else {
          startNewSession();
        }
      }
    });
  }

  async function restartFromMessage(messageUid: string) {
    const sessionUid = activeSessionUid.value;
    const targetMessage = messages.value.find(
      (message) => message.uid === messageUid,
    );

    if (!sessionUid || !targetMessage || targetMessage.role !== "user") {
      return;
    }

    await withMutation(chatStoreError("revertMessage"), async () => {
      draft.value = targetMessage.content;
      await revertChatMessage(sessionUid, messageUid);
      await loadMessages(sessionUid);
      await loadSessions({ silent: true });
    });
  }

  function setProviderModel(providerUid: string, modelUid: string) {
    selectedProviderUid.value = providerUid;
    selectedModelUid.value = modelUid;
  }

  function setThinking(nextThinking: ThinkingLevel) {
    thinking.value = nextThinking;
  }

  function setRagMode(mode: SearchMode) {
    ragOptions.value = {
      ...ragOptions.value,
      mode,
    };
  }

  function setRerankEnabled(rerankEnabled: boolean) {
    ragOptions.value = {
      ...ragOptions.value,
      rerankEnabled,
    };
  }

  function setStandaloneEnabled(standaloneEnabled: boolean) {
    ragOptions.value = {
      ...ragOptions.value,
      standaloneEnabled,
    };
  }

  function setAdminSystemPrompt(value: string | number) {
    adminSystemPrompt.value = String(value);
  }

  function setSourceSelected(sourceUid: string, selected: boolean) {
    const current = new Set(selectedSourceUids.value);
    if (selected) {
      current.add(sourceUid);
    } else {
      current.delete(sourceUid);
    }
    selectedSourceUids.value = Array.from(current);
  }

  function isSourceSelected(sourceUid: string): boolean {
    return selectedSourceUids.value.includes(sourceUid);
  }

  function ensureDefaultProviderModel() {
    const currentIsValid = modelOptions.value.some(
      (option) =>
        option.providerUid === selectedProviderUid.value &&
        option.modelUid === selectedModelUid.value,
    );

    if (currentIsValid) {
      return;
    }

    const firstOption = modelOptions.value[0];
    selectedProviderUid.value = firstOption?.providerUid ?? null;
    selectedModelUid.value = firstOption?.modelUid ?? null;
  }

  // ---- 异步状态包装器：统一 loading / error 管理 ----
  async function withBootstrap<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
  ): Promise<T> {
    isBootstrapping.value = true;
    errorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      errorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      isBootstrapping.value = false;
    }
  }

  async function withLoadingSessions<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
    options: LoadOptions = {},
  ): Promise<T> {
    if (!options.silent) {
      isLoadingSessions.value = true;
    }
    errorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      errorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      if (!options.silent) {
        isLoadingSessions.value = false;
      }
    }
  }

  async function withLoadingMessages<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
  ): Promise<T> {
    isLoadingMessages.value = true;
    errorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      errorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      isLoadingMessages.value = false;
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

  function resetMessagePage() {
    hasMoreBefore.value = false;
    hasMoreAfter.value = false;
    oldestSequence.value = null;
    newestSequence.value = null;
  }

  // ---- 对外暴露 ----
  return {
    activeSession,
    activeSessionUid,
    adminSystemPrompt,
    bootstrap,
    canSend,
    deleteSession,
    draft,
    ensureDefaultProviderModel,
    errorMessage,
    hasMoreAfter,
    hasMoreBefore,
    isBootstrapping,
    isLoadingMessages,
    isLoadingSessions,
    isMutating,
    isSourceSelected,
    loadMessages,
    loadSessions,
    messages,
    modelOptionGroups,
    modelOptions,
    newestSequence,
    oldestSequence,
    ragOptions,
    restartFromMessage,
    selectedModelLabel,
    selectedModelOption,
    selectedModelUid,
    selectedProviderUid,
    selectedSourceCount,
    selectedSourceUids,
    selectSession,
    sessions,
    setAdminSystemPrompt,
    setProviderModel,
    setRagMode,
    setRerankEnabled,
    setSourceSelected,
    setStandaloneEnabled,
    setThinking,
    startNewSession,
    thinking,
    threadTitle,
  };
});

// ---- 格式化工具函数 ----

function chatStoreError(key: keyof typeof chatStoreErrorKeys): string {
  return t(chatStoreErrorKeys[key]);
}

function formatProviderDisplayName(name: string): string {
  return name
    .split(/([\s_-]+)/)
    .map((part) =>
      /^[\s_-]+$/.test(part)
        ? " "
        : part.charAt(0).toUpperCase() + part.slice(1),
    )
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}
