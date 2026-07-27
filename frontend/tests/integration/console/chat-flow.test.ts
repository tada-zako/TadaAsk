import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/services/chat", () => ({
  buildAdminChatRequest: vi.fn((input: any) => input),
  cancelChatGeneration: vi.fn(),
  createDefaultRagOptions: vi.fn(() => ({
    mode: "adaptive",
    topK: 8,
    rerankEnabled: true,
    ftsK: 30,
    vectorK: 20,
    rerankK: 12,
    maxAlternativeQueries: 2,
    maxKeywords: 5,
    standaloneEnabled: false,
  })),
  deleteChatSession: vi.fn(),
  listGlobalChatSessions: vi.fn(),
  loadChatMessages: vi.fn(),
  revertChatMessage: vi.fn(),
  streamGlobalChatEvents: vi.fn(),
  toMessageViewModel: vi.fn((message: any) => ({
    ...message,
    content: message.message,
    createdLabel: "",
    citationItems: message.ragSnapshot?.items ?? [],
    citationCount: message.ragSnapshot?.items?.length ?? 0,
    usedCitationCount: 0,
    sourcesReady: true,
    rawMessage: message,
  })),
  toMessageViewModels: vi.fn((messages: any[]) =>
    messages.map((message: any) => ({
      ...message,
      content: message.message,
      createdLabel: "",
      citationItems: [],
      citationCount: 0,
      usedCitationCount: 0,
      sourcesReady: true,
      rawMessage: message,
    })),
  ),
  toSessionViewModel: vi.fn((session: any) => ({
    ...session,
    updatedLabel: "now",
    session,
  })),
  toSessionViewModels: vi.fn((sessions: any[]) =>
    sessions.map((session: any) => ({
      ...session,
      updatedLabel: "now",
      session,
    })),
  ),
}));

import { streamGlobalChatEvents } from "@/console/services/chat";
import { useGlobalChatStore } from "@/console/stores/global-chat";
import { useProviderModelStore } from "@/console/stores/provider-model";

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
    provider: "OpenAI",
    model: "gpt",
    ragSnapshot: null,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  };
}

describe("console chat service-to-store integration", () => {
  it("将 mock SSE 的会话、delta 和完成消息收敛到 active timeline", async () => {
    useProviderModelStore().enabledProviders = [
      {
        uid: "provider-1",
        name: "openai",
        isEnabled: true,
        isCustom: false,
        encryptedApiKey: "key",
        baseUrl: null,
        modelProfiles: [
          {
            uid: "model-1",
            model: "gpt",
            isEnabled: true,
            supportsStream: true,
            supportsStructured: true,
          },
        ],
      },
    ] as never;
    vi.mocked(streamGlobalChatEvents).mockResolvedValue(
      (async function* () {
        yield {
          event: "session_ready",
          session: {
            uid: "session-1",
            title: "Session",
            provider: "OpenAI",
            model: "gpt",
            createdAt: "2026-07-01T00:00:00Z",
            updatedAt: "2026-07-01T00:00:00Z",
          },
        };
        yield {
          event: "generation_start",
          sessionUid: "session-1",
          generationUid: "generation-1",
          userMessage: message("user-1", "user", "Hello", 1),
          assistantMessage: message("assistant-1", "assistant", "", 2),
        };
        yield { event: "delta", messageUid: "assistant-1", delta: "Hi" };
        yield {
          event: "message_done",
          message: message("assistant-1", "assistant", "Hi", 2),
        };
      })() as never,
    );
    const store = useGlobalChatStore();
    store.setProviderModel("provider-1", "model-1");
    store.draft = "Hello";

    await store.sendMessage();
    await vi.waitFor(() => expect(store.isStreaming).toBe(false));

    expect(store.activeSessionUid).toBe("session-1");
    expect(store.messages).toMatchObject([
      { uid: "user-1", content: "Hello" },
      { uid: "assistant-1", content: "Hi", sourcesReady: true },
    ]);
  });
});
