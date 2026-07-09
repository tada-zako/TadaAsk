import { computed, markRaw, ref } from "vue";
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

type ChatSessionKey = string;
type ChatStreamStatus = "connecting" | "streaming" | "cancelling";

// 单个 session 的消息时间线状态（含分页、加载状态）
interface ChatTimelineState {
  messages: ChatMessageViewModel[];
  hasMoreBefore: boolean;
  hasMoreAfter: boolean;
  oldestSequence: number | null;
  newestSequence: number | null;
  didInitialLoad: boolean; // 是否已有 messages 载入
  isLoadingInitial: boolean; // 是否处于 messages 载入状态
  isLoadingOlder: boolean;
  errorMessage: string | null;
}

// 单个 session 的 SSE 流式状态数据结构
interface ChatStreamState {
  sessionKey: ChatSessionKey;
  sessionUid: string | null;
  generationUid: string | null;
  controller: AbortController;
  status: ChatStreamStatus;
  pendingUserMessageUid: string | null;
  pendingAssistantMessageUid: string | null;
  assistantMessageUid: string | null;
  originalMessage: string;
}

const MESSAGE_PAGE_LIMIT = 30;
const NEW_CHAT_DRAFT_KEY = "__new_chat__";
const TEMP_SESSION_PREFIX = "temp:";

// 模型选择器：单个模型选项
export interface ChatModelOption {
  providerUid: string;
  providerName: string;
  providerDisplayName: string;
  modelUid: string;
  modelName: string;
  model: ModelProfileRead;
}

// 模型选择器：按 provider 分组的选项组
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

// 模块级递增计数器，用于生成临时 session / message uid
let temporarySessionIndex = 0;
let temporaryMessageIndex = 0;

export const useGlobalChatStore = defineStore("console-global-chat", () => {
  const providerModelStore = useProviderModelStore();
  const sourceStore = useSourceStore();

  // ---- 核心状态 ----
  // session 与 timeline 状态
  const sessions = ref<ChatSessionViewModel[]>([]);
  const activeSessionUid = ref<ChatSessionKey | null>(null);
  const timelinesBySessionKey = ref<Record<ChatSessionKey, ChatTimelineState>>(
    {},
  );
  const draftBySessionKey = ref<Record<ChatSessionKey, string>>({});
  const streamStatesBySessionKey = ref<Record<ChatSessionKey, ChatStreamState>>(
    {},
  ); // 记录 SSE 流对象

  // 模型、RAG 与 prompt 设置
  const selectedProviderUid = ref<string | null>(null);
  const selectedModelUid = ref<string | null>(null);
  const thinking = ref<ThinkingLevel>("medium");
  const selectedSourceUids = ref<string[]>([]);
  const ragOptions = ref<HybridSearchRequest>(createDefaultRagOptions());
  const adminSystemPrompt = ref("");

  // 全局 UI 状态
  const isBootstrapping = ref(false);
  const isLoadingSessions = ref(false);
  const isMutating = ref(false);
  const globalErrorMessage = ref<string | null>(null);
  const cancelledMessageUids = ref<string[]>([]);

  // ---- 派生计算 ----
  const activeSessionKey = computed<ChatSessionKey>(
    () => activeSessionUid.value ?? NEW_CHAT_DRAFT_KEY,
  );

  const activeRouteSessionUid = computed(() =>
    // 对于 temp session 不触发 route 更新
    activeSessionUid.value && !isTemporarySessionKey(activeSessionUid.value)
      ? activeSessionUid.value
      : null,
  );

  const activeSession = computed(
    () =>
      sessions.value.find(
        (session) => session.uid === activeSessionUid.value,
      ) ?? null,
  );

  const activeTimeline = computed(() =>
    getReadonlyTimelineState(activeSessionKey.value),
  );
  const activeStream = computed(
    () => streamStatesBySessionKey.value[activeSessionKey.value] ?? null,
  );

  const messages = computed(() => activeTimeline.value.messages);
  const hasMoreBefore = computed(() => activeTimeline.value.hasMoreBefore);
  const hasMoreAfter = computed(() => activeTimeline.value.hasMoreAfter);
  const oldestSequence = computed(() => activeTimeline.value.oldestSequence);
  const newestSequence = computed(() => activeTimeline.value.newestSequence);
  const isLoadingMessages = computed(
    () => activeTimeline.value.isLoadingInitial,
  );
  const isLoadingOlderMessages = computed(
    () => activeTimeline.value.isLoadingOlder,
  );
  const errorMessage = computed(
    () => activeTimeline.value.errorMessage ?? globalErrorMessage.value,
  );
  const isStreaming = computed(() => Boolean(activeStream.value));
  const isCancelling = computed(
    () => activeStream.value?.status === "cancelling",
  );
  const activeGenerationUid = computed(
    () => activeStream.value?.generationUid ?? null,
  );
  const streamingSessionUid = computed(
    () => activeStream.value?.sessionUid ?? null,
  );
  const streamingAssistantMessageUid = computed(
    () => activeStream.value?.assistantMessageUid ?? null,
  );
  const threadTitle = computed(() => activeSession.value?.title);
  const selectedSourceCount = computed(() => selectedSourceUids.value.length);

  const draft = computed({
    get: () => draftBySessionKey.value[activeSessionKey.value] ?? "",
    set: (value: string) => {
      setDraft(activeSessionKey.value, value);
    },
  });

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

  // ---- 初始化 & session 管理 ----
  /** 初始化：加载 sessions / 模型 / 来源，并选中默认 session */
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

      // 默认首次进入 /chat 页面，展示 New Session 样式
      startNewSession();
    });
  }

  /** 加载 admin 所有的 global scope session */
  async function loadSessions(options: LoadOptions = {}) {
    await withLoadingSessions(
      chatStoreError("loadSessions"),
      async () => {
        const loadedSessions = await listGlobalChatSessions({
          limit: 50,
          offset: 0,
        });
        const pendingSessions = sessions.value.filter((session) =>
          isTemporarySessionKey(session.uid),
        );
        sessions.value = mergeSessionViewModels(
          pendingSessions,
          toSessionViewModels(loadedSessions),
        );
      },
      options,
    );
  }

  /** 选中 session; 加载完整的 session 数据 */
  async function selectSession(sessionUid: string) {
    activeSessionUid.value = sessionUid;

    if (isTemporarySessionKey(sessionUid)) {
      ensureTimelineState(sessionUid);
      return;
    }

    const timeline = ensureTimelineState(sessionUid);
    if (!timeline.didInitialLoad && !timeline.isLoadingInitial) {
      await loadInitialMessages(sessionUid);
    }
  }

  // 新建空白 session（activeSessionUid = null → draft key）
  function startNewSession() {
    activeSessionUid.value = null;
    setDraft(NEW_CHAT_DRAFT_KEY, "");
    ensureTimelineState(NEW_CHAT_DRAFT_KEY);
  }

  // ---- 消息加载 ----
  async function loadMessages(sessionUid = activeRouteSessionUid.value) {
    await loadInitialMessages(sessionUid);
  }

  /** 载入完整的 session messages */
  async function loadInitialMessages(sessionUid = activeRouteSessionUid.value) {
    if (!sessionUid || isTemporarySessionKey(sessionUid)) {
      if (!activeSessionUid.value) {
        updateTimeline(NEW_CHAT_DRAFT_KEY, () => createEmptyTimelineState());
      }
      return;
    }

    // 避免重复请求
    const sessionKey = sessionUid;
    const timeline = ensureTimelineState(sessionKey);
    if (timeline.isLoadingInitial) {
      return;
    }

    updateTimeline(sessionKey, (current) => ({
      ...current,
      isLoadingInitial: true,
      errorMessage: null,
    }));

    try {
      // 向后端请求消息
      const page = await loadChatMessages(sessionUid, {
        limit: MESSAGE_PAGE_LIMIT,
        includeInternal: false,
      });
      const loadedMessages = toMessageViewModels(page.messages);
      const hasActiveStream = isSessionStreaming(sessionKey);

      updateTimeline(sessionKey, (current) => ({
        ...current,
        messages: hasActiveStream
          ? mergeMessageViewModels(current.messages, loadedMessages)
          : loadedMessages,
        hasMoreBefore: page.hasMoreBefore,
        hasMoreAfter: page.hasMoreAfter,
        oldestSequence: page.oldestSequence ?? null,
        newestSequence: page.newestSequence ?? null,
        didInitialLoad: true,
        isLoadingInitial: false,
      }));
    } catch (error) {
      updateTimeline(sessionKey, (current) => ({
        ...current,
        isLoadingInitial: false,
        errorMessage: getErrorMessage(error, chatStoreError("loadMessages")),
      }));
      throw error;
    }
  }

  // 加载更早消息（无限滚动向上翻页），返回 false 表示无更多数据
  async function loadOlderMessages() {
    const sessionKey = activeSessionUid.value;
    const sessionUid = activeRouteSessionUid.value;

    if (
      !sessionKey ||
      !sessionUid ||
      isTemporarySessionKey(sessionKey) ||
      isLoadingMessages.value ||
      isLoadingOlderMessages.value ||
      !hasMoreBefore.value ||
      oldestSequence.value == null
    ) {
      return false;
    }

    updateTimeline(sessionKey, (current) => ({
      ...current,
      isLoadingOlder: true,
      errorMessage: null,
    }));

    try {
      const page = await loadChatMessages(sessionUid, {
        limit: MESSAGE_PAGE_LIMIT,
        beforeSequence: oldestSequence.value,
        includeInternal: false,
      });
      const loadedMessages = toMessageViewModels(page.messages);

      updateTimeline(sessionKey, (current) => {
        const nextMessages = mergeMessageViewModels(
          loadedMessages,
          current.messages,
        );
        return {
          ...current,
          messages: nextMessages,
          hasMoreBefore: page.hasMoreBefore,
          oldestSequence: minMessageSequence(nextMessages),
          newestSequence: maxMessageSequence(nextMessages),
          isLoadingOlder: false,
        };
      });
      return page.messages.length > 0;
    } catch (error) {
      updateTimeline(sessionKey, (current) => ({
        ...current,
        isLoadingOlder: false,
        errorMessage: getErrorMessage(error, chatStoreError("loadMessages")),
      }));
      throw error;
    }
  }

  // ---- session 删除 & 消息回退 ----
  async function deleteSession(sessionUid: string) {
    if (isSessionStreaming(sessionUid)) {
      return;
    }

    if (isTemporarySessionKey(sessionUid)) {
      removeSessionLocally(sessionUid);
      if (activeSessionUid.value === sessionUid) {
        startNewSession();
      }
      return;
    }

    await withMutation(chatStoreError("deleteSession"), async () => {
      await deleteChatSession(sessionUid);
      removeSessionLocally(sessionUid);

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
    const sessionUid = activeRouteSessionUid.value;
    const sessionKey = activeSessionUid.value;
    const targetMessage = messages.value.find(
      (message) => message.uid === messageUid,
    );

    if (
      !sessionUid ||
      !sessionKey ||
      isSessionStreaming(sessionKey) ||
      !targetMessage ||
      targetMessage.role !== "user"
    ) {
      return;
    }

    await withMutation(chatStoreError("revertMessage"), async () => {
      draft.value = targetMessage.content;
      await revertChatMessage(sessionUid, messageUid);
      await loadMessages(sessionUid);
      await loadSessions({ silent: true });
    });
  }

  // ---- 消息发送 & 流式控制 ----
  // 发送消息：创建乐观消息 → 发起 SSE 流式对话
  async function sendMessage() {
    const originalDraftKey = activeSessionKey.value;
    const message = draft.value.trim();
    const providerUid = selectedProviderUid.value;
    const modelUid = selectedModelUid.value;

    if (!message || !providerUid || !modelUid) {
      return;
    }

    let sessionKey = activeSessionUid.value;
    if (!sessionKey) {
      // 创建 pending status session, 乐观渲染 session
      sessionKey = createPendingSession();
      activeSessionUid.value = sessionKey;
    }

    if (isSessionStreaming(sessionKey)) {
      return;
    }

    const selectedModel = selectedModelOption.value;
    const providerLabel =
      selectedModel?.providerDisplayName ?? selectedModel?.providerName ?? "";
    const modelLabel = selectedModel?.modelName ?? "";
    const optimisticMessages = createOptimisticMessages({
      message,
      provider: providerLabel,
      model: modelLabel,
      sessionKey,
    });

    appendMessages(sessionKey, optimisticMessages);
    // 覆盖 draft cache
    setDraft(originalDraftKey, "");
    setDraft(sessionKey, "");

    const request = buildAdminChatRequest({
      message,
      chatSessionUid: isTemporarySessionKey(sessionKey) ? null : sessionKey,
      providerUid,
      modelUid,
      adminSystemPrompt: adminSystemPrompt.value,
      thinking: thinking.value,
      sourceUids: selectedSourceUids.value,
      ragOptions: ragOptions.value,
    });

    const controller = markRaw(new AbortController()); // markRaw() 避免 vue 将其当成响应式
    setStreamState(sessionKey, {
      sessionKey,
      sessionUid: isTemporarySessionKey(sessionKey) ? null : sessionKey,
      generationUid: null,
      controller,
      status: "connecting",
      pendingUserMessageUid: optimisticMessages.user.uid,
      pendingAssistantMessageUid: optimisticMessages.assistant.uid,
      assistantMessageUid: optimisticMessages.assistant.uid,
      originalMessage: message,
    });

    void consumeChatStream(sessionKey, request, controller).catch(
      () => undefined,
    );
  }

  async function cancelGeneration() {
    const sessionKey = activeSessionKey.value;
    const streamState = streamStatesBySessionKey.value[sessionKey];

    if (!streamState || streamState.status === "cancelling") {
      return;
    }

    const sessionUid = streamState.sessionUid;
    const generationUid = streamState.generationUid;

    // 缺少 generation_uid 对象，直接中断流式
    if (!sessionUid || !generationUid) {
      streamState.controller.abort();
      if (streamState.assistantMessageUid) {
        markMessageCancelled(streamState.assistantMessageUid);
      }
      clearStreamState(sessionKey, streamState.controller);
      return;
    }

    patchStreamState(sessionKey, { status: "cancelling" });
    clearTimelineError(sessionKey);

    try {
      // 通过 cancel API 进行流式 API 中断
      const response = await cancelChatGeneration(sessionUid, generationUid);
      if (!response.cancelled) {
        patchStreamState(sessionKey, { status: "streaming" });
      }
    } catch (error) {
      patchStreamState(sessionKey, { status: "streaming" });
      setTimelineError(
        sessionKey,
        getErrorMessage(error, chatStoreError("cancelGeneration")),
      );
    }
  }

  // ---- 设置项 (model / RAG / prompt / source) ----
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

  // ---- 多 session 并发流状态查询 ----
  function isSessionStreaming(sessionKey: string): boolean {
    return Boolean(streamStatesBySessionKey.value[sessionKey]);
  }

  function isSessionCancelling(sessionKey: string): boolean {
    return streamStatesBySessionKey.value[sessionKey]?.status === "cancelling";
  }

  /** 选定默认模型；默认 models 中第一个 */
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

  // ---- SSE 流消费与事件分发 ----
  // 消费 SSE 事件流，通过 AbortController 支持取消
  async function consumeChatStream(
    initialSessionKey: ChatSessionKey,
    request: ReturnType<typeof buildAdminChatRequest>,
    controller: AbortController,
  ) {
    let sessionKey = initialSessionKey;
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

        sessionKey = applyChatStreamEvent(sessionKey, event);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        handleStreamError(sessionKey, controller, generationStarted, error);
        if (generationStarted) {
          await refreshSessionMessagesAfterStreamError(sessionKey);
        }
      }
    } finally {
      clearStreamState(sessionKey, controller);
    }
  }

  // SSE 事件 → 状态变更分发
  function applyChatStreamEvent(
    sessionKey: ChatSessionKey,
    event: ChatStreamEvent,
  ): ChatSessionKey {
    switch (event.event) {
      case "session_ready":
        return applySessionReady(sessionKey, event.session);
      case "session_title_updated":
        upsertSession(event.session);
        return sessionKey;
      case "generation_start":
        return applyGenerationStart(sessionKey, event);
      case "delta":
        appendMessageDelta(sessionKey, event.messageUid, event.delta);
        return sessionKey;
      case "cancelled":
        appendMessageDelta(sessionKey, event.messageUid, event.delta);
        markMessageCancelled(event.messageUid);
        clearStreamState(sessionKey);
        return sessionKey;
      case "message_done":
        upsertMessage(sessionKey, event.message);
        unmarkMessageCancelled(event.message.uid);
        clearStreamState(sessionKey);
        return sessionKey;
      case "error":
        throw new Error(event.message);
    }
  }

  function applySessionReady(
    sessionKey: ChatSessionKey,
    session: ChatSessionRead,
  ): ChatSessionKey {
    const nextSessionKey = migrateSessionKey(sessionKey, session.uid);
    upsertSession(session);
    patchStreamState(nextSessionKey, {
      sessionKey: nextSessionKey,
      sessionUid: session.uid,
    });
    return nextSessionKey;
  }

  function applyGenerationStart(
    sessionKey: ChatSessionKey,
    event: Extract<ChatStreamEvent, { event: "generation_start" }>,
  ): ChatSessionKey {
    const nextSessionKey = migrateSessionKey(sessionKey, event.sessionUid);
    const streamState = streamStatesBySessionKey.value[nextSessionKey];

    replaceOptimisticMessages(nextSessionKey, event, streamState);
    patchStreamState(nextSessionKey, {
      sessionKey: nextSessionKey,
      sessionUid: event.sessionUid,
      generationUid: event.generationUid,
      status: "streaming",
      pendingUserMessageUid: null,
      pendingAssistantMessageUid: null,
      assistantMessageUid: event.assistantMessage.uid,
    });

    return nextSessionKey;
  }

  function upsertSession(session: ChatSessionRead) {
    const viewModel = toSessionViewModel(session);
    // withoutSameUid 中去除旧的 session view model 对象
    const withoutSameUid = sessions.value.filter(
      (item) => item.uid !== session.uid,
    );
    sessions.value = [viewModel, ...withoutSameUid].sort(
      compareSessionsByUpdatedAt,
    );
  }

  function upsertMessage(sessionKey: ChatSessionKey, message: ChatMessageRead) {
    const viewModel = toMessageViewModel(message);
    updateTimeline(sessionKey, (current) => {
      const nextMessages = upsertMessageViewModel(current.messages, viewModel);
      return {
        ...current,
        messages: nextMessages,
        oldestSequence: minMessageSequence(nextMessages),
        newestSequence: maxMessageSequence(nextMessages),
      };
    });
  }

  function appendMessageDelta(
    sessionKey: ChatSessionKey,
    messageUid: string,
    delta: string,
  ) {
    if (!delta) {
      return;
    }

    updateTimeline(sessionKey, (current) => {
      const targetIndex = resolveDeltaMessageIndex(
        current.messages,
        sessionKey,
        messageUid,
      );

      if (targetIndex < 0) {
        return current;
      }

      const targetMessage = current.messages[targetIndex];
      const nextMessages = current.messages.slice();
      nextMessages[targetIndex] = appendDeltaToMessage(targetMessage, delta);

      return {
        ...current,
        messages: nextMessages,
      };
    });
  }

  /** 确定 delta 消息需要追加到的 message 对应的 index */
  function resolveDeltaMessageIndex(
    messages: ChatMessageViewModel[],
    sessionKey: ChatSessionKey,
    messageUid: string,
  ): number {
    const streamState = streamStatesBySessionKey.value[sessionKey];
    const tailIndex = messages.length - 1;

    // fast path
    if (messages[tailIndex]?.uid === messageUid) {
      return tailIndex;
    }

    if (
      streamState?.assistantMessageUid === messageUid &&
      messages[tailIndex]?.uid === streamState.assistantMessageUid
    ) {
      return tailIndex;
    }

    // 全量查询
    return messages.findIndex((message) => message.uid === messageUid);
  }

  function markMessageCancelled(messageUid: string) {
    if (cancelledMessageUids.value.includes(messageUid)) {
      return;
    }

    cancelledMessageUids.value = [...cancelledMessageUids.value, messageUid];
  }

  function unmarkMessageCancelled(messageUid: string) {
    cancelledMessageUids.value = cancelledMessageUids.value.filter(
      (uid) => uid !== messageUid,
    );
  }

  // 流错误处理：流开始前错误则回退乐观消息，已开始则仅设置错误信息
  function handleStreamError(
    sessionKey: ChatSessionKey,
    controller: AbortController,
    generationStarted: boolean,
    error: unknown,
  ) {
    const streamState = streamStatesBySessionKey.value[sessionKey];
    const errorText = getErrorMessage(error, chatStoreError("streamGlobal"));
    setTimelineError(sessionKey, errorText);

    if (!generationStarted && streamState?.controller === controller) {
      rollbackOptimisticStream(sessionKey, streamState);
    }
  }

  async function refreshSessionMessagesAfterStreamError(
    sessionKey: ChatSessionKey,
  ) {
    if (isTemporarySessionKey(sessionKey)) {
      return;
    }

    const currentErrorMessage =
      timelinesBySessionKey.value[sessionKey]?.errorMessage ?? null;

    try {
      const page = await loadChatMessages(sessionKey, {
        limit: MESSAGE_PAGE_LIMIT,
        includeInternal: false,
      });
      const loadedMessages = toMessageViewModels(page.messages);
      updateTimeline(sessionKey, (current) => ({
        ...current,
        messages: mergeMessageViewModels(loadedMessages, current.messages),
        hasMoreBefore: page.hasMoreBefore,
        hasMoreAfter: page.hasMoreAfter,
        oldestSequence: page.oldestSequence ?? null,
        newestSequence: page.newestSequence ?? null,
        didInitialLoad: true,
      }));
    } catch {
      // 保留原始 stream 错误，避免二次刷新错误覆盖用户真正需要看到的信息。
    } finally {
      if (currentErrorMessage) {
        setTimelineError(sessionKey, currentErrorMessage);
      }
    }
  }

  function getReadonlyTimelineState(
    sessionKey: ChatSessionKey,
  ): ChatTimelineState {
    return (
      timelinesBySessionKey.value[sessionKey] ?? createEmptyTimelineState()
    );
  }

  /** 返回 session 对应的 timeline */
  function ensureTimelineState(sessionKey: ChatSessionKey): ChatTimelineState {
    const existing = timelinesBySessionKey.value[sessionKey];
    if (existing) {
      return existing;
    }

    const timeline = createEmptyTimelineState();
    timelinesBySessionKey.value = {
      ...timelinesBySessionKey.value,
      [sessionKey]: timeline,
    };
    return timeline;
  }

  function updateTimeline(
    sessionKey: ChatSessionKey,
    updater: (timeline: ChatTimelineState) => ChatTimelineState,
  ): ChatTimelineState {
    const current = ensureTimelineState(sessionKey);
    const next = updater(current);
    timelinesBySessionKey.value = {
      ...timelinesBySessionKey.value,
      [sessionKey]: next,
    };
    return next;
  }

  function setTimelineError(sessionKey: ChatSessionKey, message: string) {
    updateTimeline(sessionKey, (current) => ({
      ...current,
      errorMessage: message,
    }));
  }

  function clearTimelineError(sessionKey: ChatSessionKey) {
    updateTimeline(sessionKey, (current) => ({
      ...current,
      errorMessage: null,
    }));
  }

  function setDraft(sessionKey: ChatSessionKey, value: string) {
    draftBySessionKey.value = {
      ...draftBySessionKey.value,
      [sessionKey]: value,
    };
  }

  function setStreamState(
    sessionKey: ChatSessionKey,
    streamState: ChatStreamState | null,
  ) {
    const nextStates = { ...streamStatesBySessionKey.value };
    if (streamState) {
      nextStates[sessionKey] = streamState;
    } else {
      delete nextStates[sessionKey];
    }
    streamStatesBySessionKey.value = nextStates;
  }

  function patchStreamState(
    sessionKey: ChatSessionKey,
    patch: Partial<ChatStreamState>,
  ) {
    const current = streamStatesBySessionKey.value[sessionKey];
    if (!current) {
      return;
    }

    setStreamState(sessionKey, {
      ...current,
      ...patch,
    });
  }

  // 为未持久化的新对话创建临时 session（显示为 pending 状态）
  function createPendingSession(): ChatSessionKey {
    const sessionUid = createTemporarySessionUid();
    const selectedModel = selectedModelOption.value;
    const providerLabel =
      selectedModel?.providerDisplayName ?? selectedModel?.providerName ?? "";
    const modelLabel = selectedModel?.modelName ?? "";
    const session = createPendingSessionViewModel(
      sessionUid,
      providerLabel,
      modelLabel,
    );

    sessions.value = [session, ...sessions.value].sort(
      compareSessionsByUpdatedAt,
    );
    ensureTimelineState(sessionUid);
    return sessionUid;
  }

  /**
   * 创建乐观 message;
   * 前端创建 user/assistant message 占位，避免用户长时等待
   */
  function createOptimisticMessages(input: {
    message: string;
    provider: string;
    model: string;
    sessionKey: ChatSessionKey;
  }): { user: ChatMessageViewModel; assistant: ChatMessageViewModel } {
    const timeline = ensureTimelineState(input.sessionKey);
    const baseSequence = (maxMessageSequence(timeline.messages) ?? 0) + 1;

    return {
      user: createOptimisticMessage({
        uid: createTemporaryMessageUid("user"),
        role: "user",
        message: input.message,
        sequence: baseSequence,
        provider: input.provider,
        model: input.model,
      }),
      assistant: createOptimisticMessage({
        uid: createTemporaryMessageUid("assistant"),
        role: "assistant",
        message: "",
        sequence: baseSequence + 1,
        provider: input.provider,
        model: input.model,
      }),
    };
  }

  function appendMessages(
    sessionKey: ChatSessionKey,
    messagesToAppend: {
      user: ChatMessageViewModel;
      assistant: ChatMessageViewModel;
    },
  ) {
    updateTimeline(sessionKey, (current) => {
      const nextMessages = mergeMessageViewModels(
        [messagesToAppend.user, messagesToAppend.assistant],
        current.messages,
      );
      return {
        ...current,
        messages: nextMessages,
        oldestSequence: minMessageSequence(nextMessages),
        newestSequence: maxMessageSequence(nextMessages),
        didInitialLoad: true,
        errorMessage: null,
      };
    });
  }

  // 将临时 session key 迁移为服务端返回的真实 uid，
  // 同时合并 timeline / streamState / draft 等状态到新 key 下
  function migrateSessionKey(
    sessionKey: ChatSessionKey,
    realSessionUid: string,
  ): ChatSessionKey {
    if (sessionKey === realSessionUid || !isTemporarySessionKey(sessionKey)) {
      return realSessionUid;
    }

    const tempTimeline = timelinesBySessionKey.value[sessionKey];
    const realTimeline = timelinesBySessionKey.value[realSessionUid];
    if (tempTimeline) {
      const nextTimeline = mergeTimelines(realTimeline, tempTimeline);
      const nextTimelines = { ...timelinesBySessionKey.value };
      delete nextTimelines[sessionKey];
      nextTimelines[realSessionUid] = nextTimeline;
      timelinesBySessionKey.value = nextTimelines;
    }

    const streamState = streamStatesBySessionKey.value[sessionKey];
    if (streamState) {
      const nextStates = { ...streamStatesBySessionKey.value };
      delete nextStates[sessionKey];
      nextStates[realSessionUid] = {
        ...streamState,
        sessionKey: realSessionUid,
        sessionUid: realSessionUid,
      };
      streamStatesBySessionKey.value = nextStates;
    }

    if (draftBySessionKey.value[sessionKey] != null) {
      const nextDrafts = { ...draftBySessionKey.value };
      nextDrafts[realSessionUid] = nextDrafts[sessionKey];
      delete nextDrafts[sessionKey];
      draftBySessionKey.value = nextDrafts;
    }

    // 过滤 Temp sessionKey
    sessions.value = sessions.value.filter(
      (session) => session.uid !== sessionKey,
    );

    if (activeSessionUid.value === sessionKey) {
      activeSessionUid.value = realSessionUid;
    }

    return realSessionUid;
  }

  // generation_start 时用服务端返回的真实消息替换乐观消息
  function replaceOptimisticMessages(
    sessionKey: ChatSessionKey,
    event: Extract<ChatStreamEvent, { event: "generation_start" }>,
    streamState: ChatStreamState | undefined,
  ) {
    const userMessage = toMessageViewModel(event.userMessage);
    const assistantMessage = toMessageViewModel(event.assistantMessage);

    updateTimeline(sessionKey, (current) => {
      let nextMessages = current.messages.map((message) => {
        if (message.uid === streamState?.pendingUserMessageUid) {
          return userMessage;
        }

        if (message.uid === streamState?.pendingAssistantMessageUid) {
          return assistantMessage;
        }

        return message;
      });

      if (
        !nextMessages.some((message) => message.uid === event.userMessage.uid)
      ) {
        nextMessages = [...nextMessages, userMessage];
      }

      if (
        !nextMessages.some(
          (message) => message.uid === event.assistantMessage.uid,
        )
      ) {
        nextMessages = [...nextMessages, assistantMessage];
      }

      nextMessages = dedupeMessagesByUid(nextMessages).sort(
        compareMessagesBySequence,
      );

      return {
        ...current,
        messages: nextMessages,
        oldestSequence: minMessageSequence(nextMessages),
        newestSequence: maxMessageSequence(nextMessages),
        didInitialLoad: true,
      };
    });
  }

  // 流错误且未开始生成时：清除乐观消息，恢复草稿
  function rollbackOptimisticStream(
    sessionKey: ChatSessionKey,
    streamState: ChatStreamState,
  ) {
    removeMessagesByUid(
      sessionKey,
      [
        streamState.pendingUserMessageUid,
        streamState.pendingAssistantMessageUid,
      ]
        .filter(Boolean)
        .map(String),
    );

    if (isTemporarySessionKey(sessionKey)) {
      removeSessionLocally(sessionKey);
      setDraft(NEW_CHAT_DRAFT_KEY, streamState.originalMessage);
      if (activeSessionUid.value === sessionKey) {
        activeSessionUid.value = null;
      }
      return;
    }

    setDraft(sessionKey, streamState.originalMessage);
  }

  function removeMessagesByUid(sessionKey: ChatSessionKey, uids: string[]) {
    if (!uids.length) {
      return;
    }

    const uidSet = new Set(uids);
    updateTimeline(sessionKey, (current) => {
      const nextMessages = current.messages.filter(
        (message) => !uidSet.has(message.uid),
      );
      return {
        ...current,
        messages: nextMessages,
        oldestSequence: minMessageSequence(nextMessages),
        newestSequence: maxMessageSequence(nextMessages),
      };
    });
  }

  function removeSessionLocally(sessionKey: ChatSessionKey) {
    sessions.value = sessions.value.filter(
      (session) => session.uid !== sessionKey,
    );

    const nextTimelines = { ...timelinesBySessionKey.value };
    delete nextTimelines[sessionKey];
    timelinesBySessionKey.value = nextTimelines;

    const nextDrafts = { ...draftBySessionKey.value };
    delete nextDrafts[sessionKey];
    draftBySessionKey.value = nextDrafts;

    setStreamState(sessionKey, null);
  }

  function clearStreamState(
    sessionKey: ChatSessionKey,
    controller?: AbortController,
  ) {
    const streamState = streamStatesBySessionKey.value[sessionKey];
    if (!streamState) {
      return;
    }

    if (controller && streamState.controller !== controller) {
      return;
    }

    setStreamState(sessionKey, null);
  }

  // ---- 异步操作包装器 (loading / error 状态管理) ----
  async function withBootstrap<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
  ): Promise<T> {
    isBootstrapping.value = true;
    globalErrorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      globalErrorMessage.value = getErrorMessage(error, fallbackMessage);
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
    globalErrorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      globalErrorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      if (!options.silent) {
        isLoadingSessions.value = false;
      }
    }
  }

  async function withMutation<T>(
    fallbackMessage: string,
    task: () => Promise<T>,
  ): Promise<T> {
    isMutating.value = true;
    globalErrorMessage.value = null;

    try {
      return await task();
    } catch (error) {
      globalErrorMessage.value = getErrorMessage(error, fallbackMessage);
      throw error;
    } finally {
      isMutating.value = false;
    }
  }

  return {
    activeGenerationUid,
    activeRouteSessionUid,
    activeSession,
    activeSessionUid,
    adminSystemPrompt,
    bootstrap,
    cancelGeneration,
    cancelledMessageUids,
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
    isLoadingOlderMessages,
    isLoadingSessions,
    isMutating,
    isSessionCancelling,
    isSessionStreaming,
    isSourceSelected,
    isStreaming,
    loadInitialMessages,
    loadMessages,
    loadOlderMessages,
    loadSessions,
    messages,
    modelOptionGroups,
    modelOptions,
    newestSequence,
    oldestSequence,
    ragOptions,
    restartFromMessage,
    selectSession,
    selectedModelLabel,
    selectedModelOption,
    selectedModelUid,
    selectedProviderUid,
    selectedSourceCount,
    selectedSourceUids,
    sendMessage,
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

// ============================================================
// 模块级工具函数（纯函数，不依赖 store 实例）
// ============================================================

function createEmptyTimelineState(): ChatTimelineState {
  return {
    messages: [],
    hasMoreBefore: false,
    hasMoreAfter: false,
    oldestSequence: null,
    newestSequence: null,
    didInitialLoad: false,
    isLoadingInitial: false,
    isLoadingOlder: false,
    errorMessage: null,
  };
}

function createPendingSessionRead(
  uid: string,
  provider: string,
  model: string,
): ChatSessionRead {
  const now = new Date().toISOString();
  return {
    uid,
    title: t("chat.sessions.newChat"),
    ownerType: "admin",
    provider,
    model,
    createdAt: now,
    updatedAt: now,
  };
}

function createPendingSessionViewModel(
  uid: string,
  provider: string,
  model: string,
): ChatSessionViewModel {
  const session = createPendingSessionRead(uid, provider, model);
  return {
    ...toSessionViewModel(session),
    isPending: true,
  };
}

function createOptimisticMessage(input: {
  uid: string;
  role: ChatMessageRead["role"];
  message: string;
  sequence: number;
  provider: string;
  model: string;
}): ChatMessageViewModel {
  const now = new Date().toISOString();
  return toMessageViewModel({
    uid: input.uid,
    role: input.role,
    message: input.message,
    type: "message",
    sequence: input.sequence,
    provider: input.provider,
    model: input.model,
    ragSnapshot: null,
    createdAt: now,
    updatedAt: now,
  });
}

function appendDeltaToMessage(
  message: ChatMessageViewModel,
  delta: string,
): ChatMessageViewModel {
  const nextContent = `${message.content}${delta}`;
  return {
    ...message,
    content: nextContent,
    rawMessage: {
      ...message.rawMessage,
      message: nextContent,
    },
  };
}

function chatStoreError(key: keyof typeof chatStoreErrorKeys): string {
  return t(chatStoreErrorKeys[key]);
}

function isTemporarySessionKey(sessionKey: string): boolean {
  return sessionKey.startsWith(TEMP_SESSION_PREFIX);
}

function createTemporarySessionUid(): string {
  temporarySessionIndex += 1;
  return `${TEMP_SESSION_PREFIX}${Date.now()}:${temporarySessionIndex}`;
}

function createTemporaryMessageUid(role: ChatMessageRead["role"]): string {
  temporaryMessageIndex += 1;
  return `temp-message:${role}:${Date.now()}:${temporaryMessageIndex}`;
}

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

function mergeMessageViewModels(
  incoming: ChatMessageViewModel[],
  current: ChatMessageViewModel[],
): ChatMessageViewModel[] {
  const byUid = new Map<string, ChatMessageViewModel>();

  for (const message of current) {
    byUid.set(message.uid, message);
  }

  for (const message of incoming) {
    byUid.set(message.uid, message);
  }

  return Array.from(byUid.values()).sort(compareMessagesBySequence);
}

/** 合并 pending 类型的 session 以及 API 返回的真实 sessions */
function mergeSessionViewModels(
  pendingSessions: ChatSessionViewModel[],
  loadedSessions: ChatSessionViewModel[],
): ChatSessionViewModel[] {
  const byUid = new Map<string, ChatSessionViewModel>();

  for (const session of loadedSessions) {
    byUid.set(session.uid, session);
  }

  for (const session of pendingSessions) {
    byUid.set(session.uid, session);
  }

  return Array.from(byUid.values()).sort(compareSessionsByUpdatedAt);
}

function mergeTimelines(
  existing: ChatTimelineState | undefined,
  incoming: ChatTimelineState,
): ChatTimelineState {
  const base = existing ?? createEmptyTimelineState();
  const messages = mergeMessageViewModels(incoming.messages, base.messages);
  return {
    ...base,
    ...incoming,
    messages,
    hasMoreBefore: base.hasMoreBefore || incoming.hasMoreBefore,
    hasMoreAfter: base.hasMoreAfter || incoming.hasMoreAfter,
    oldestSequence: minMessageSequence(messages),
    newestSequence: maxMessageSequence(messages),
    didInitialLoad: base.didInitialLoad || incoming.didInitialLoad,
    isLoadingInitial: base.isLoadingInitial || incoming.isLoadingInitial,
    isLoadingOlder: base.isLoadingOlder || incoming.isLoadingOlder,
    errorMessage: incoming.errorMessage ?? base.errorMessage,
  };
}

function upsertMessageViewModel(
  messages: ChatMessageViewModel[],
  message: ChatMessageViewModel,
): ChatMessageViewModel[] {
  const exists = messages.some((item) => item.uid === message.uid);
  const nextMessages = exists
    ? messages.map((item) => (item.uid === message.uid ? message : item))
    : [...messages, message];

  return nextMessages.sort(compareMessagesBySequence);
}

function dedupeMessagesByUid(
  messages: ChatMessageViewModel[],
): ChatMessageViewModel[] {
  const byUid = new Map<string, ChatMessageViewModel>();
  for (const message of messages) {
    byUid.set(message.uid, message);
  }
  return Array.from(byUid.values());
}

function minMessageSequence(messages: ChatMessageViewModel[]): number | null {
  if (!messages.length) {
    return null;
  }

  return Math.min(...messages.map((message) => message.sequence));
}

function maxMessageSequence(messages: ChatMessageViewModel[]): number | null {
  if (!messages.length) {
    return null;
  }

  return Math.max(...messages.map((message) => message.sequence));
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
