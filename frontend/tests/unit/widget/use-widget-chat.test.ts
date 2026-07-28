import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/widget/services/chat", () => {
  class WidgetChatError extends Error {}
  return {
    WidgetChatError,
    createWidgetChatService: vi.fn(),
    refreshMessageCitations: vi.fn((message) => message),
    toWidgetMessage: vi.fn((message, status = "completed") =>
      message.role === "user" || message.role === "assistant"
        ? {
            uid: message.uid,
            role: message.role,
            content: message.message,
            sequence: message.sequence,
            status,
            ragSnapshot: message.ragSnapshot ?? null,
            citationItems: [],
          }
        : null,
    ),
  };
});

import { createWidgetChatService } from "@/widget/services/chat";
import { useWidgetChat } from "@/widget/composables/use-widget-chat";

function message(
  uid: string,
  role: "user" | "assistant",
  content: string,
  sequence: number,
) {
  return {
    uid,
    role,
    type: "message",
    message: content,
    sequence,
    provider: "widget",
    model: "widget",
    ragSnapshot: null,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  };
}

async function* events(values: unknown[]) {
  for (const value of values) yield value;
}

describe("useWidgetChat", () => {
  it("阻止缺少部署配置的发送，并暴露配置错误", async () => {
    vi.mocked(createWidgetChatService).mockReturnValue({
      stream: vi.fn(),
      cancel: vi.fn(),
    });
    const chat = useWidgetChat({
      apiBaseUrl: ref(""),
      projectUid: ref("project-1"),
      widgetUid: ref("widget-1"),
    });
    chat.draft.value = "Hello";

    await chat.sendMessage();

    expect(chat).toMatchObject({
      phase: { value: "error" },
      errorMessage: { value: "This assistant has not been configured yet." },
    });
    expect(chat.messages.value).toEqual([]);
  });

  it("以乐观消息开始，并完成 SSE phase、delta 与终态消息", async () => {
    const service = {
      stream: vi.fn().mockResolvedValue(
        events([
          {
            event: "session_ready",
            session: { uid: "session-1" },
          },
          {
            event: "generation_start",
            sessionUid: "session-1",
            generationUid: "generation-1",
            userMessage: message("user-1", "user", "Hello", 1),
            assistantMessage: message("assistant-1", "assistant", "", 2),
          },
          { event: "delta", messageUid: "assistant-1", delta: "Hi" },
          {
            event: "message_done",
            message: message("assistant-1", "assistant", "Hi", 2),
          },
        ]),
      ),
      cancel: vi.fn(),
    };
    vi.mocked(createWidgetChatService).mockReturnValue(service as never);
    const chat = useWidgetChat({
      apiBaseUrl: ref("https://api.example.com"),
      projectUid: ref("project-1"),
      widgetUid: ref("widget-1"),
    });
    chat.draft.value = " Hello ";

    await chat.sendMessage();

    expect(service.stream).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Hello", chatSessionUid: null }),
    );
    expect(chat.phase.value).toBe("idle");
    expect(chat.messages.value).toMatchObject([
      { uid: "user-1", content: "Hello", status: "completed" },
      { uid: "assistant-1", content: "Hi", status: "completed" },
    ]);
  });

  it("新建会话会 abort 旧请求，并由 epoch 忽略其后续事件", async () => {
    let release!: () => void;
    let aborted = false;
    const service = {
      stream: vi.fn().mockImplementation(async ({ signal }) =>
        (async function* () {
          await new Promise<void>((resolve) => {
            signal.addEventListener(
              "abort",
              () => {
                aborted = true;
                resolve();
              },
              { once: true },
            );
            release = resolve;
          });
          yield {
            event: "generation_start",
            sessionUid: "old-session",
            generationUid: "old-generation",
            userMessage: message("old-user", "user", "Old", 1),
            assistantMessage: message("old-assistant", "assistant", "", 2),
          };
        })(),
      ),
      cancel: vi.fn().mockResolvedValue(true),
    };
    vi.mocked(createWidgetChatService).mockReturnValue(service as never);
    const chat = useWidgetChat({
      apiBaseUrl: ref("https://api.example.com"),
      projectUid: ref("project-1"),
      widgetUid: ref("widget-1"),
    });
    chat.draft.value = "Old";

    const pending = chat.sendMessage();
    await vi.waitFor(() => expect(release).toBeTypeOf("function"));
    chat.startNewChat();
    release();
    await pending;

    expect(aborted).toBe(true);
    expect(chat).toMatchObject({
      phase: { value: "idle" },
      messages: { value: [] },
    });
  });

  it("使用 generation UID 取消流，并在 cancelled 事件后收敛消息状态", async () => {
    let release!: () => void;
    const service = {
      stream: vi.fn().mockResolvedValue(
        (async function* () {
          yield {
            event: "generation_start",
            sessionUid: "session-1",
            generationUid: "generation-1",
            userMessage: message("user-1", "user", "Stop", 1),
            assistantMessage: message("assistant-1", "assistant", "", 2),
          };
          await new Promise<void>((resolve) => {
            release = resolve;
          });
          yield { event: "cancelled", messageUid: "assistant-1", delta: "" };
        })(),
      ),
      cancel: vi.fn().mockResolvedValue(true),
    };
    vi.mocked(createWidgetChatService).mockReturnValue(service as never);
    const chat = useWidgetChat({
      apiBaseUrl: ref("https://api.example.com"),
      projectUid: ref("project-1"),
      widgetUid: ref("widget-1"),
    });
    chat.draft.value = "Stop";

    const pending = chat.sendMessage();
    await vi.waitFor(() => expect(chat.phase.value).toBe("thinking"));
    await chat.cancelGeneration();
    expect(service.cancel).toHaveBeenCalledWith("generation-1");
    expect(chat.phase.value).toBe("cancelling");

    release();
    await pending;
    expect(chat.phase.value).toBe("idle");
    expect(chat.messages.value[1]).toMatchObject({
      uid: "assistant-1",
      status: "cancelled",
    });
  });
});
