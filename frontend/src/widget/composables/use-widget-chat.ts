import {
  computed,
  onBeforeUnmount,
  ref,
  toValue,
  type MaybeRefOrGetter,
} from "vue";

import type { ChatStreamEvent } from "@/shared/types/chat-stream";
import { formatErrorWithReference } from "@/shared/api/error-reference";
import {
  createWidgetChatService,
  refreshMessageCitations,
  toWidgetMessage,
  WidgetChatError,
  type WidgetMessageViewModel,
} from "../services/chat";

export type WidgetChatPhase =
  "idle" | "connecting" | "thinking" | "streaming" | "cancelling" | "error";

interface UseWidgetChatOptions {
  apiBaseUrl: MaybeRefOrGetter<string>;
  projectUid: MaybeRefOrGetter<string>;
  widgetUid: MaybeRefOrGetter<string>;
}

let temporaryMessageIndex = 0;

// Widget 聊天核心状态机：管理消息列表、SSE 流式接收、取消与 epoch 隔离
export function useWidgetChat(options: UseWidgetChatOptions) {
  const messages = ref<WidgetMessageViewModel[]>([]);
  const draft = ref("");
  const phase = ref<WidgetChatPhase>("idle");
  const errorMessage = ref<string | null>(null);
  const sessionUid = ref<string | null>(null);
  const generationUid = ref<string | null>(null);
  const activeAssistantUid = ref<string | null>(null);

  // AbortController + epoch 双重隔离：新请求递增 epoch，旧回调自动丢弃
  let controller: AbortController | null = null;
  let requestEpoch = 0; // widget 不实际记录 sessions list, 使用简单的 epoch 区分不同的 session

  const isBusy = computed(() =>
    ["connecting", "thinking", "streaming", "cancelling"].includes(phase.value),
  );
  const hasMessages = computed(() => messages.value.length > 0);
  const hasValidConfig = computed(
    () =>
      Boolean(toValue(options.apiBaseUrl).trim()) &&
      Boolean(toValue(options.projectUid).trim()) &&
      Boolean(toValue(options.widgetUid).trim()),
  );
  const canSend = computed(
    () => Boolean(draft.value.trim()) && hasValidConfig.value && !isBusy.value,
  );

  // 乐观 UI：先插入临时 user + assistant 占位消息，再通过 SSE 流逐步替换为服务端数据
  async function sendMessage() {
    const content = draft.value.trim();
    if (!content || isBusy.value) return;
    if (!hasValidConfig.value) {
      errorMessage.value = "This assistant has not been configured yet.";
      phase.value = "error";
      return;
    }

    const epoch = ++requestEpoch;
    // 中断信号
    const requestController = new AbortController();
    controller = requestController;
    errorMessage.value = null;
    phase.value = "connecting";
    draft.value = "";

    const sequence = nextSequence();
    const userUid = temporaryUid("user");
    const assistantUid = temporaryUid("assistant");
    // 插入乐观 message 占位
    messages.value.push(
      {
        uid: userUid,
        role: "user",
        content,
        sequence,
        status: "completed",
        ragSnapshot: null,
        citationItems: [],
      },
      {
        uid: assistantUid,
        role: "assistant",
        content: "",
        sequence: sequence + 1,
        status: "pending",
        ragSnapshot: null,
        citationItems: [],
      },
    );
    activeAssistantUid.value = assistantUid;

    try {
      // 进行流式 API 请求
      const service = createService();
      const stream = await service.stream({
        message: content,
        chatSessionUid: sessionUid.value,
        signal: requestController.signal,
      });

      for await (const event of stream) {
        if (epoch !== requestEpoch) break;
        // 处理 event
        applyEvent(event, userUid, assistantUid);
      }
    } catch (error) {
      if (epoch !== requestEpoch || isAbortError(error)) return;
      errorMessage.value = visitorErrorMessage(error);
      phase.value = "error";
      patchActiveAssistant((message) =>
        refreshMessageCitations({ ...message, status: "error" }),
      );
    } finally {
      if (epoch === requestEpoch) {
        controller = null;
        generationUid.value = null;
        activeAssistantUid.value = null;
        if (phase.value !== "error") phase.value = "idle";
      }
    }
  }

  /** 取消生成 */
  async function cancelGeneration() {
    if (!generationUid.value || !isBusy.value) return;
    phase.value = "cancelling";
    try {
      await createService().cancel(generationUid.value);
    } catch (error) {
      errorMessage.value = visitorErrorMessage(error);
      phase.value = "streaming";
    }
  }

  /** 新会话立即清空 UI；旧流通过 epoch 隔离，取消请求仅作 best effort。 */
  function startNewChat() {
    const oldGenerationUid = generationUid.value;
    requestEpoch += 1;
    controller?.abort(); // 强制中断连接
    controller = null;

    if (oldGenerationUid) {
      // 最大努力通知后端关闭流式
      void createService()
        .cancel(oldGenerationUid)
        .catch(() => undefined);
    }

    messages.value = [];
    draft.value = "";
    phase.value = "idle";
    errorMessage.value = null;
    sessionUid.value = null;
    generationUid.value = null;
    activeAssistantUid.value = null;
  }

  /** 关闭 error 显示 */
  function dismissError() {
    errorMessage.value = null;
    if (phase.value === "error") phase.value = "idle";
  }

  // SSE 事件分发：按事件类型更新 phase、消息内容与引用来源
  function applyEvent(
    event: ChatStreamEvent,
    optimisticUserUid: string,
    optimisticAssistantUid: string,
  ) {
    switch (event.event) {
      case "session_ready":
        sessionUid.value = event.session.uid;
        phase.value = "thinking";
        break;
      case "session_title_updated":
        break;
      case "generation_start": {
        sessionUid.value = event.sessionUid;
        generationUid.value = event.generationUid;
        phase.value = "thinking";
        replaceOptimisticMessage(
          optimisticUserUid,
          toWidgetMessage(event.userMessage),
        );
        const assistant = toWidgetMessage(event.assistantMessage, "pending");
        replaceOptimisticMessage(optimisticAssistantUid, assistant);
        activeAssistantUid.value = assistant?.uid ?? optimisticAssistantUid;
        break;
      }
      case "rag_ready":
        patchMessage(event.messageUid, (message) => ({
          ...message,
          ragSnapshot: event.ragSnapshot,
          // rag_ready 只缓存原始 snapshot；引用 UI 在终态统一发布。
          citationItems: [],
        }));
        break;
      case "delta":
        phase.value = "streaming";
        patchMessage(event.messageUid, (message) =>
          refreshMessageCitations({
            ...message,
            content: `${message.content}${event.delta}`,
            status: "streaming",
          }),
        );
        break;
      case "cancelled":
        patchMessage(event.messageUid, (message) =>
          refreshMessageCitations({
            ...message,
            content: `${message.content}${event.delta}`,
            status: "cancelled",
          }),
        );
        phase.value = "idle";
        break;
      case "message_done": {
        const completed = toWidgetMessage(event.message);
        if (completed) replaceOptimisticMessage(event.message.uid, completed);
        phase.value = "idle";
        break;
      }
      case "error":
        errorMessage.value = formatErrorWithReference(
          "The assistant could not finish this response.",
          { errorId: event.errorId },
        );
        phase.value = "error";
        patchActiveAssistant((message) =>
          refreshMessageCitations({ ...message, status: "error" }),
        );
        break;
    }
  }

  /** 用服务端返回的真实消息替换临时占位消息，并按 sequence 重排 */
  function replaceOptimisticMessage(
    targetUid: string,
    incoming: WidgetMessageViewModel | null,
  ) {
    if (!incoming) return;
    const targetIndex = messages.value.findIndex(
      (message) => message.uid === targetUid,
    );
    const existingIndex = messages.value.findIndex(
      (message) => message.uid === incoming.uid,
    );
    const index = targetIndex >= 0 ? targetIndex : existingIndex;
    if (index >= 0) messages.value[index] = incoming;
    else messages.value.push(incoming);
    messages.value.sort((left, right) => left.sequence - right.sequence);
  }

  /** 更新消息对象 */
  function patchMessage(
    uid: string,
    updater: (message: WidgetMessageViewModel) => WidgetMessageViewModel,
  ) {
    const index = messages.value.findIndex((message) => message.uid === uid);
    if (index >= 0) messages.value[index] = updater(messages.value[index]);
  }

  function patchActiveAssistant(
    updater: (message: WidgetMessageViewModel) => WidgetMessageViewModel,
  ) {
    if (activeAssistantUid.value) {
      patchMessage(activeAssistantUid.value, updater);
    }
  }

  function createService() {
    return createWidgetChatService({
      apiBaseUrl: toValue(options.apiBaseUrl),
      projectUid: toValue(options.projectUid),
      widgetUid: toValue(options.widgetUid),
    });
  }

  function nextSequence() {
    return (
      messages.value.reduce(
        (maximum, message) => Math.max(maximum, message.sequence),
        0,
      ) + 1
    );
  }

  onBeforeUnmount(() => {
    requestEpoch += 1;
    controller?.abort();
  });

  return {
    canSend,
    cancelGeneration,
    dismissError,
    draft,
    errorMessage,
    hasMessages,
    isBusy,
    messages,
    phase,
    sendMessage,
    startNewChat,
  };
}

// 临时 uid：服务端尚未返回真实 uid 前的本地占位标识
function temporaryUid(role: "user" | "assistant") {
  temporaryMessageIndex += 1;
  return `widget-temp:${role}:${Date.now()}:${temporaryMessageIndex}`;
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function visitorErrorMessage(error: unknown) {
  return error instanceof WidgetChatError
    ? error.message
    : "Unable to reach the assistant. Check your connection and try again.";
}
