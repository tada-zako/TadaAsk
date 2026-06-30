import { client } from "./client";
import type { VisitorChatRequest } from "@/shared/types/chat-stream";

/** Visitor Widget 侧的公开聊天接口 */
export const widgetChatApi = {
  /** widget 的访客 chat stream */
  stream: (
    projectUid: string,
    widgetUid: string,
    body: VisitorChatRequest,
    signal?: AbortSignal,
  ) =>
    client.POST(
      "/visitor/project/{project_uid}/widget/{widget_uid}/chat/stream",
      {
        params: { path: { project_uid: projectUid, widget_uid: widgetUid } },
        body,
        headers: { Accept: "text/event-stream" },
        parseAs: "stream",
        signal,
      },
    ),
};
