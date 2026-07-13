import { createWidgetChatApi } from "../api/widget-chat";
import { parseSseStream } from "@/shared/api/sse";
import type { components } from "@/shared/api/generated/schema";
import type {
  ChatMessageRead,
  ChatStreamEvent,
  RAGSnapshot,
} from "@/shared/types/chat-stream";

export type RAGSnapshotItem = components["schemas"]["RAGSnapshotItem"];
export type WidgetCitationItem = RAGSnapshotItem & { displayId: number };
export type WidgetMessageStatus =
  "pending" | "streaming" | "completed" | "cancelled" | "error";

export interface WidgetMessageViewModel {
  uid: string;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  status: WidgetMessageStatus;
  ragSnapshot: RAGSnapshot | null;
  citationItems: WidgetCitationItem[];
}

export interface WidgetChatService {
  stream(input: {
    message: string;
    chatSessionUid: string | null;
    signal?: AbortSignal;
  }): Promise<AsyncGenerator<ChatStreamEvent, void, unknown>>;
  cancel(generationUid: string): Promise<boolean>;
}

export class WidgetChatError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "WidgetChatError";
    this.status = status;
  }
}

/**
 * 为单个 Widget 实例创建绑定部署标识的业务 service。
 *
 * 由于 widget 侧请求的 baseUrl 是由底层 view 向下传递的，
 * 所以 widget api 并不像 console 侧的 API 封装函数是直接可以使用的，而是首先创建对应的 api 对象，才能在
 * 需要在 service 层创建 widget-service 对象
 */
export function createWidgetChatService(input: {
  apiBaseUrl: string;
  projectUid: string;
  widgetUid: string;
}): WidgetChatService {
  const api = createWidgetChatApi(normalizeBaseUrl(input.apiBaseUrl));

  return {
    async stream(request) {
      const { data, error, response } = await api.stream(
        input.projectUid,
        input.widgetUid,
        {
          message: request.message.trim(),
          chatSessionUid: request.chatSessionUid,
        },
        request.signal,
      );

      if (!data || error) {
        throw toWidgetChatError(response, error);
      }

      // 调用 SSE parse helper 函数
      return parseSseStream<ChatStreamEvent>(
        data as ReadableStream<Uint8Array>,
      );
    },

    async cancel(generationUid) {
      const { data, error, response } = await api.cancel(
        input.projectUid,
        input.widgetUid,
        generationUid,
      );
      if (!data || error) {
        throw toWidgetChatError(response, error);
      }
      return data.cancelled;
    },
  };
}

/** 将 message 转换为 widget 侧 DTO 对象 */
export function toWidgetMessage(
  message: ChatMessageRead,
  status: WidgetMessageStatus = "completed",
): WidgetMessageViewModel | null {
  if (message.role !== "user" && message.role !== "assistant") {
    return null;
  }

  return {
    uid: message.uid,
    role: message.role,
    content: message.message,
    sequence: message.sequence,
    status,
    ragSnapshot: message.ragSnapshot ?? null,
    citationItems: selectCitationItems(
      message.message,
      message.ragSnapshot?.items ?? [],
    ),
  };
}

/** 优先展示正文实际引用的来源，再用参与上下文的结果补足，始终最多四项。 */
export function selectCitationItems(
  content: string,
  items: readonly RAGSnapshotItem[],
): WidgetCitationItem[] {
  const byId = new Map(items.map((item) => [item.citationId, item]));
  const selected: WidgetCitationItem[] = [];
  const selectedIds = new Set<number>();

  // 只展示正文实际引用的来源，并按首次出现顺序建立稳定的 1–4 显示编号。
  for (const match of content.matchAll(/\[\[citation:([1-9]\d*)\]\]/g)) {
    append(Number(match[1]));
  }

  return selected;

  function append(citationId: number) {
    const item = byId.get(citationId);
    if (!item || selectedIds.has(citationId) || selected.length >= 4) {
      return;
    }
    selectedIds.add(citationId);
    selected.push({ ...item, displayId: selected.length + 1 });
  }
}

export function refreshMessageCitations(
  message: WidgetMessageViewModel,
): WidgetMessageViewModel {
  const items = message.ragSnapshot?.items ?? [];
  return {
    ...message,
    citationItems: selectCitationItems(message.content, items),
  };
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

// HTTP 状态码 → 面向访客的友好错误文案
function toWidgetChatError(response: Response, payload: unknown): Error {
  const status = response?.status;
  const messages: Record<number, string> = {
    400: "This assistant is not ready yet. Please try again later.",
    403: "This assistant is not available on this site.",
    404: "This assistant could not be found.",
    413: "Your message is too long. Please shorten it and try again.",
    422: "Please check your message and try again.",
    429: "Too many requests. Please wait a moment and try again.",
    500: "The assistant encountered a problem. Please try again.",
  };

  return new WidgetChatError(
    (status ? messages[status] : undefined) ??
      (payload
        ? "The assistant could not complete this request. Please try again."
        : "Unable to reach the assistant. Check your connection and try again."),
    status,
  );
}
