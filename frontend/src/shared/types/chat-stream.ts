import type { components } from "@/shared/api/generated/schema";

/** OpenAPI 生成类型别名 */
export type ChatMessageRead = components["schemas"]["ChatMessageRead"];
export type ChatSessionRead = components["schemas"]["ChatSessionRead"];
export type RAGSnapshot = components["schemas"]["RAGSnapshot"];

/**
 * Chat SSE 事件联合类型
 */
export type ChatStreamEvent =
  | {
      event: "session_ready";
      session: ChatSessionRead;
      created: boolean;
    }
  | {
      event: "session_title_updated";
      session: ChatSessionRead;
    }
  | {
      event: "generation_start";
      generationUid: string;
      sessionUid: string;
      userMessage: ChatMessageRead;
      assistantMessage: ChatMessageRead;
    }
  | {
      event: "rag_ready";
      messageUid: string;
      ragSnapshot: RAGSnapshot;
    }
  | {
      event: "delta";
      messageUid: string;
      delta: string;
    }
  | {
      event: "cancelled";
      messageUid: string;
      delta: string;
    }
  | {
      event: "message_done";
      message: ChatMessageRead;
    }
  | {
      event: "error";
      message: string;
    };
