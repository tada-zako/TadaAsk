import { client } from "./client";
import type { components } from "@/shared/api/generated/schema";

/** OpenAPI 生成类型别名 */
export type AdminRagChatRequest = components["schemas"]["AdminRAGChatRequest"];
export type AdminChatCancelResponse =
  components["schemas"]["AdminChatCancelResponse"];
export type AdminChatRevertResponse =
  components["schemas"]["AdminChatRevertResponse"];
export type ChatMessageRead = components["schemas"]["ChatMessageRead"];
export type ChatMessagesPage = components["schemas"]["ChatMessagesPage"];
export type ChatSessionRead = components["schemas"]["ChatSessionRead"];
export type HybridSearchRequest = components["schemas"]["HybridSearchRequest"];
export type RAGSnapshot = components["schemas"]["RAGSnapshot"];
export type RAGSnapshotItem = components["schemas"]["RAGSnapshotItem"];
export type SearchMode = components["schemas"]["SearchMode"];
export type ThinkingLevel = components["schemas"]["ThinkingLevel"];

export type ListChatSessionsQuery = {
  limit?: number;
  offset?: number;
};

export type ListChatMessagesQuery = {
  limit?: number;
  beforeSequence?: number | null;
  afterSequence?: number | null;
  includeInternal?: boolean;
};

/** Admin Console 中的聊天流接口。 */
export const adminChatApi = {
  /** 获取不绑定 project 的 Admin chat sessions */
  listGlobalSessions: (query: ListChatSessionsQuery = {}) =>
    client.GET("/admin/sessions", {
      params: { query },
    }),

  /** 获取指定 chat session 的消息分页 */
  listMessages: (chatSessionUid: string, query: ListChatMessagesQuery = {}) =>
    client.GET("/admin/session/{chat_session_uid}/messages", {
      params: {
        path: { chat_session_uid: chatSessionUid },
        query,
      },
    }),

  /** 删除指定 chat session */
  deleteSession: (chatSessionUid: string) =>
    client.DELETE("/admin/session/{chat_session_uid}", {
      params: {
        path: { chat_session_uid: chatSessionUid },
      },
    }),

  /** 回退到指定 user message，后端会删除它以及之后的消息 */
  revertMessage: (chatSessionUid: string, messageUid: string) =>
    client.POST(
      "/admin/session/{chat_session_uid}/messages/{message_uid}/revert",
      {
        params: {
          path: {
            chat_session_uid: chatSessionUid,
            message_uid: messageUid,
          },
        },
      },
    ),

  /** 取消指定 session 下的活跃 generation */
  cancelGeneration: (chatSessionUid: string, generationUid: string) =>
    client.POST(
      "/admin/session/{chat_session_uid}/generation/{generation_uid}/cancel",
      {
        params: {
          path: {
            chat_session_uid: chatSessionUid,
            generation_uid: generationUid,
          },
        },
      },
    ),

  /** global scoped Admin chat stream */
  streamGlobal: (body: AdminRagChatRequest, signal?: AbortSignal) =>
    client.POST("/admin/chat/stream", {
      body,
      headers: { Accept: "text/event-stream" },
      parseAs: "stream",
      signal,
    }),

  /** 发起 project-scoped Admin chat stream */
  streamProject: (
    projectUid: string,
    body: AdminRagChatRequest,
    signal?: AbortSignal,
  ) =>
    client.POST("/admin/project/{project_uid}/chat/stream", {
      params: { path: { project_uid: projectUid } },
      body,
      headers: { Accept: "text/event-stream" },
      parseAs: "stream",
      signal,
    }),
};
