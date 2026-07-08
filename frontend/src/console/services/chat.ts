import { adminChatApi } from "@/console/api/chat";
import type {
  AdminChatCancelResponse,
  AdminChatRevertResponse,
  AdminRagChatRequest,
  ChatMessageRead,
  ChatMessagesPage,
  ChatSessionRead,
  HybridSearchRequest,
  RAGSnapshotItem,
  SearchMode,
  ThinkingLevel,
} from "@/console/api/chat";
import { unwrapApiData } from "@/console/lib/api-result";

export type {
  AdminRagChatRequest,
  ChatMessageRead,
  ChatSessionRead,
  HybridSearchRequest,
  RAGSnapshotItem,
  SearchMode,
  ThinkingLevel,
};

// 前端展示用的 session 视图模型，附加了格式化标签
export interface ChatSessionViewModel {
  uid: string;
  title: string;
  provider: string;
  model: string;
  createdAt: string;
  updatedAt: string;
  updatedLabel: string;
  session: ChatSessionRead;
}

// 前端展示用的消息视图模型，附加 citation 计数与格式化时间
export interface ChatMessageViewModel {
  uid: string;
  role: ChatMessageRead["role"];
  type: ChatMessageRead["type"];
  content: string;
  sequence: number;
  provider: string;
  model: string;
  createdAt: string;
  updatedAt: string;
  createdLabel: string;
  citationItems: RAGSnapshotItem[];
  citationCount: number;
  usedCitationCount: number;
  rawMessage: ChatMessageRead;
}

export interface BuildAdminChatRequestInput {
  message: string;
  chatSessionUid: string | null;
  providerUid: string;
  modelUid: string;
  adminSystemPrompt: string;
  thinking: ThinkingLevel;
  sourceUids: string[];
  ragOptions: HybridSearchRequest;
}

// 默认 RAG 检索参数：adaptive 模式，rerank 开启，standalone 关闭
export const DEFAULT_RAG_OPTIONS: HybridSearchRequest = {
  mode: "adaptive",
  topK: 8,
  rerankEnabled: true,
  ftsK: 30,
  vectorK: 20,
  rerankK: 12,
  maxAlternativeQueries: 2,
  maxKeywords: 5,
  standaloneEnabled: false,
};

const chatErrors = {
  cancelGeneration: "Failed to cancel generation.",
  deleteSession: "Failed to delete chat session.",
  listMessages: "Failed to load chat messages.",
  listSessions: "Failed to load chat sessions.",
  revertMessage: "Failed to restart from this message.",
};

export function createDefaultRagOptions(): HybridSearchRequest {
  return { ...DEFAULT_RAG_OPTIONS };
}

// 合并 rag options 字段配置
export function mergeRagOptions(
  input: Partial<HybridSearchRequest> | null | undefined,
): HybridSearchRequest {
  return {
    ...DEFAULT_RAG_OPTIONS,
    ...(input ?? {}),
  };
}

// ---- API 调用封装 ----

export async function listGlobalChatSessions(input: {
  limit?: number;
  offset?: number;
}): Promise<ChatSessionRead[]> {
  const { data, error } = await adminChatApi.listGlobalSessions(input);
  return unwrapApiData(data, error, chatErrors.listSessions);
}

export async function loadChatMessages(
  chatSessionUid: string,
  input: {
    limit?: number;
    beforeSequence?: number | null;
    afterSequence?: number | null;
    includeInternal?: boolean;
  } = {},
): Promise<ChatMessagesPage> {
  const { data, error } = await adminChatApi.listMessages(
    chatSessionUid,
    input,
  );
  return unwrapApiData(data, error, chatErrors.listMessages);
}

export async function deleteChatSession(chatSessionUid: string): Promise<void> {
  const { data, error } = await adminChatApi.deleteSession(chatSessionUid);
  unwrapApiData(data, error, chatErrors.deleteSession);
}

export async function revertChatMessage(
  chatSessionUid: string,
  messageUid: string,
): Promise<AdminChatRevertResponse> {
  const { data, error } = await adminChatApi.revertMessage(
    chatSessionUid,
    messageUid,
  );
  return unwrapApiData(data, error, chatErrors.revertMessage);
}

export async function cancelChatGeneration(
  chatSessionUid: string,
  generationUid: string,
): Promise<AdminChatCancelResponse> {
  const { data, error } = await adminChatApi.cancelGeneration(
    chatSessionUid,
    generationUid,
  );
  return unwrapApiData(data, error, chatErrors.cancelGeneration);
}

export function buildAdminChatRequest(
  input: BuildAdminChatRequestInput,
): AdminRagChatRequest {
  return {
    message: input.message.trim(),
    chatSessionUid: input.chatSessionUid,
    providerUid: input.providerUid,
    modelUid: input.modelUid,
    adminSystemPrompt: normalizeOptionalText(input.adminSystemPrompt),
    thinking: input.thinking,
    sourceUids: uniqueNonEmpty(input.sourceUids),
    ragOptions: mergeRagOptions(input.ragOptions),
  };
}

// ---- API 模型 → 视图模型映射 ----

export function toSessionViewModel(
  session: ChatSessionRead,
): ChatSessionViewModel {
  return {
    uid: session.uid,
    title: session.title || "New chat",
    provider: session.provider,
    model: session.model,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
    updatedLabel: formatRelativeTime(session.updatedAt),
    session,
  };
}

export function toMessageViewModel(
  message: ChatMessageRead,
): ChatMessageViewModel {
  const citationItems = message.ragSnapshot?.items ?? [];

  return {
    uid: message.uid,
    role: message.role,
    type: message.type,
    content: message.message,
    sequence: message.sequence,
    provider: message.provider,
    model: message.model,
    createdAt: message.createdAt,
    updatedAt: message.updatedAt,
    createdLabel: formatMessageTime(message.createdAt),
    citationItems,
    citationCount: citationItems.length,
    usedCitationCount: citationItems.filter((item) => item.usedInContext)
      .length,
    rawMessage: message,
  };
}

export function toSessionViewModels(
  sessions: ChatSessionRead[],
): ChatSessionViewModel[] {
  return sessions.map(toSessionViewModel);
}

export function toMessageViewModels(
  messages: ChatMessageRead[],
): ChatMessageViewModel[] {
  return messages.map(toMessageViewModel);
}

// ---- 内部工具函数 ----

function uniqueNonEmpty(values: string[]): string[] {
  return Array.from(
    new Set(values.map((value) => value.trim()).filter(Boolean)),
  );
}

function normalizeOptionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function formatMessageTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const diffMinutes = Math.max(
    0,
    Math.round((Date.now() - date.getTime()) / 60_000),
  );

  if (diffMinutes < 1) {
    return "now";
  }

  if (diffMinutes < 60) {
    return `${diffMinutes}m`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h`;
  }

  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 8) {
    return `${diffDays}d`;
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
  });
}
