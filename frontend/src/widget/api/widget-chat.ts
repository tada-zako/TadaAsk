import { createWidgetApiClient } from "./client";
import type { components } from "@/shared/api/generated/schema";

/** OpenAPI 生成类型别名 */
export type VisitorChatRequest = components["schemas"]["VisitorChatRequest"];

/** Visitor Widget 侧的公开聊天接口 */
export type VisitorChatCancelResponse =
  components["schemas"]["VisitorChatCancelResponse"];

/** Visitor API 只保留传输细节，错误与事件语义由 service 处理。 */
export function createWidgetChatApi(baseUrl: string) {
  const client = createWidgetApiClient(baseUrl);

  return {
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
    cancel: (projectUid: string, widgetUid: string, generationUid: string) =>
      client.POST(
        "/visitor/project/{project_uid}/widget/{widget_uid}/generation/{generation_uid}/cancel",
        {
          params: {
            path: {
              project_uid: projectUid,
              widget_uid: widgetUid,
              generation_uid: generationUid,
            },
          },
        },
      ),
  };
}
