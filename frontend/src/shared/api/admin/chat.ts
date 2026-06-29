import { client } from "../client";
import type { AdminRagChatRequest } from "@/shared/types/chat-stream";

/** Admin Console 中的聊天流接口。 */
export const adminChatApi = {
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
