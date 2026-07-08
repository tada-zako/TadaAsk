import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  buildAdminChatRequest,
  cancelChatGeneration,
  createDefaultRagOptions,
  deleteChatSession,
  listGlobalChatSessions,
  loadChatMessages,
  revertChatMessage,
  streamGlobalChatEvents,
  toMessageViewModel,
  toMessageViewModels,
  toSessionViewModel,
  toSessionViewModels,
  type ChatMessageRead,
  type ChatMessageViewModel,
  type ChatSessionRead,
  type ChatSessionViewModel,
  type ChatStreamEvent,
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
  cancelGeneration: "chat.service.errors.cancelGeneration",
  deleteSession: "chat.service.errors.deleteSession",
  loadMessages: "chat.service.errors.loadMessages",
  loadSessions: "chat.service.errors.loadSessions",
  revertMessage: "chat.service.errors.revertMessage",
  streamGlobal: "chat.service.errors.streamGlobal",
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
  // ---- SSE streaming 状态 ----
  const isStreaming = ref(false);
  const isCancelling = ref(false);
  const errorMessage = ref<string | null>(null);
  const activeGenerationUid = ref<string | null>(null);
  const streamingSessionUid = ref<string | null>(null);
  const streamingAssistantMessageUid = ref<string | null>(null);
  let streamAbortController: AbortController | null = null;

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
      Boolean(selectedModelUid.value) &&
      !isStreaming.value,
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
    if (isStreaming.value) {
      return;
    }

    activeSessionUid.value = sessionUid;
    await loadMessages(sessionUid);
  }

  function startNewSession() {
    if (isStreaming.value) {
      return;
    }

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
    if (isStreaming.value) {
      return;
    }

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
    if (isStreaming.value) {
      return;
    }

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

  // 发送消息 → 构建请求 → 开启 SSE stream → 逐事件更新 UI
  async function sendMessage() {
    if (isStreaming.value) {
      return;
    }

    const message = draft.value.trim();
    const providerUid = selectedProviderUid.value;
    const modelUid = selectedModelUid.value;

    if (!message || !providerUid || !modelUid) {
      return;
    }

    const request = buildAdminChatRequest({
      message,
      chatSessionUid: activeSessionUid.value,
      providerUid,
      modelUid,
      adminSystemPrompt: adminSystemPrompt.value,
      thinking: thinking.value,
      sourceUids: selectedSourceUids.value,
      ragOptions: ragOptions.value,
    });

    const controller = new AbortController();
    streamAbortController = controller;
    isStreaming.value = true;
    isCancelling.value = false;
    activeGenerationUid.value = null;
    streamingSessionUid.value = activeSessionUid.value;
    streamingAssistantMessageUid.value = null;
    errorMessage.value = null;
    draft.value = "";

    let generationStarted = false;

    try {
      const stream = await streamGlobalChatEvents(request, controller.signal);

      for await (const event of stream) {
        if (controller.signal.aborted) {
          break;
        }

        if (event.event === "generation_start") {
          generationStarted = true;
        }

        applyChatStreamEvent(event);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        errorMessage.value = getErrorMessage(
          error,
          chatStoreError("streamGlobal"),
        );

        if (!generationStarted && !draft.value) {
          draft.value = message;
        }

        await refreshActiveMessagesAfterStreamError();
      }
    } finally {
      if (streamAbortController === controller) {
        clearStreamingState();
      }
    }
  }

  async function cancelGeneration() {
    if (!isStreaming.value || isCancelling.value) {
      return;
    }

    const sessionUid = streamingSessionUid.value ?? activeSessionUid.value;
    const generationUid = activeGenerationUid.value;

    if (!sessionUid || !generationUid) {
      streamAbortController?.abort();
      clearStreamingState();
      return;
    }

    isCancelling.value = true;
    errorMessage.value = null;

    try {
      const response = await cancelChatGeneration(sessionUid, generationUid);
      if (!response.cancelled) {
        isCancelling.value = false;
      }
    } catch (error) {
      isCancelling.value = false;
      errorMessage.value = getErrorMessage(
        error,
        chatStoreError("cancelGeneration"),
      );
    }
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

  // SSE 事件分发：按 event 类型路由到对应的 state 更新函数
  function applyChatStreamEvent(event: ChatStreamEvent) {
    switch (event.event) {
      case "session_ready":
        applySessionReady(event.session);
        break;
      case "session_title_updated":
        upsertSession(event.session);
        break;
      case "generation_start":
        applyGenerationStart(event);
        break;
      case "delta":
        appendMessageDelta(event.messageUid, event.delta);
        break;
      case "cancelled":
        appendMessageDelta(event.messageUid, event.delta);
        activeGenerationUid.value = null;
        streamingAssistantMessageUid.value = null;
        isCancelling.value = false;
        break;
      case "message_done":
        upsertMessage(event.message);
        activeGenerationUid.value = null;
        streamingAssistantMessageUid.value = null;
        isCancelling.value = false;
        break;
      case "error":
        throw new Error(event.message);
    }
  }

  function applySessionReady(session: ChatSessionRead) {
    upsertSession(session);
    activeSessionUid.value = session.uid;
    streamingSessionUid.value = session.uid;
  }

  function applyGenerationStart(
    event: Extract<ChatStreamEvent, { event: "generation_start" }>,
  ) {
    activeGenerationUid.value = event.generationUid;
    activeSessionUid.value = event.sessionUid;
    streamingSessionUid.value = event.sessionUid;
    streamingAssistantMessageUid.value = event.assistantMessage.uid;

    upsertMessage(event.userMessage);
    upsertMessage(event.assistantMessage);
  }

  function upsertSession(session: ChatSessionRead) {
    const viewModel = toSessionViewModel(session);
    const exists = sessions.value.some((item) => item.uid === session.uid);
    const nextSessions = exists
      ? sessions.value.map((item) =>
          item.uid === session.uid ? viewModel : item,
        )
      : [viewModel, ...sessions.value];

    sessions.value = nextSessions.sort(compareSessionsByUpdatedAt);
  }

  function upsertMessage(message: ChatMessageRead) {
    const viewModel = toMessageViewModel(message);
    const exists = messages.value.some((item) => item.uid === message.uid);

    messages.value = (
      exists
        ? messages.value.map((item) =>
            item.uid === message.uid ? viewModel : item,
          )
        : [...messages.value, viewModel]
    ).sort(compareMessagesBySequence);

    updateMessagePageBounds(viewModel.sequence);
  }

  function appendMessageDelta(messageUid: string, delta: string) {
    if (!delta) {
      return;
    }

    messages.value = messages.value.map((message) => {
      if (message.uid !== messageUid) {
        return message;
      }

      const nextContent = `${message.content}${delta}`;
      return {
        ...message,
        content: nextContent,
        rawMessage: {
          ...message.rawMessage,
          message: nextContent,
        },
      };
    });
  }

  // stream 出错后重新拉取消息，保留原始错误信息不被覆盖
  async function refreshActiveMessagesAfterStreamError() {
    const sessionUid = activeSessionUid.value;
    const currentErrorMessage = errorMessage.value;

    if (!sessionUid) {
      return;
    }

    try {
      const page = await loadChatMessages(sessionUid, {
        limit: 80,
        includeInternal: false,
      });
      messages.value = toMessageViewModels(page.messages);
      hasMoreBefore.value = page.hasMoreBefore;
      hasMoreAfter.value = page.hasMoreAfter;
      oldestSequence.value = page.oldestSequence ?? null;
      newestSequence.value = page.newestSequence ?? null;
    } catch {
      // 保留原始 stream 错误，避免二次刷新错误覆盖用户真正需要看到的信息。
    } finally {
      errorMessage.value = currentErrorMessage;
    }
  }

  function clearStreamingState() {
    streamAbortController = null;
    isStreaming.value = false;
    isCancelling.value = false;
    activeGenerationUid.value = null;
    streamingSessionUid.value = null;
    streamingAssistantMessageUid.value = null;
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

  function updateMessagePageBounds(sequence: number) {
    oldestSequence.value =
      oldestSequence.value == null
        ? sequence
        : Math.min(oldestSequence.value, sequence);
    newestSequence.value =
      newestSequence.value == null
        ? sequence
        : Math.max(newestSequence.value, sequence);
  }

  // ---- 对外暴露 ----
  return {
    activeSession,
    activeSessionUid,
    activeGenerationUid,
    adminSystemPrompt,
    bootstrap,
    cancelGeneration,
    canSend,
    deleteSession,
    draft,
    ensureDefaultProviderModel,
    errorMessage,
    hasMoreAfter,
    hasMoreBefore,
    isBootstrapping,
    isCancelling,
    isLoadingMessages,
    isLoadingSessions,
    isMutating,
    isStreaming,
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
    sendMessage,
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
    streamingAssistantMessageUid,
    streamingSessionUid,
    thinking,
    threadTitle,
  };
});

// ---- 格式化工具函数 ----

function chatStoreError(key: keyof typeof chatStoreErrorKeys): string {
  return t(chatStoreErrorKeys[key]);
}

// ---- 排序比较器 ----

function compareSessionsByUpdatedAt(
  left: ChatSessionViewModel,
  right: ChatSessionViewModel,
): number {
  return dateValue(right.updatedAt) - dateValue(left.updatedAt);
}

function compareMessagesBySequence(
  left: ChatMessageViewModel,
  right: ChatMessageViewModel,
): number {
  return left.sequence - right.sequence;
}

function dateValue(value: string): number {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
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
