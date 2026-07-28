import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/services/chat", () => ({
  buildAdminChatRequest: vi.fn((input) => input),
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
    uid: message.uid,
    role: message.role,
    type: message.type,
    content: message.message,
    sequence: message.sequence,
    provider: message.provider,
    model: message.model,
    createdAt: message.createdAt,
    updatedAt: message.updatedAt,
    createdLabel: "",
    citationItems: message.ragSnapshot?.items ?? [],
    citationCount: message.ragSnapshot?.items?.length ?? 0,
    usedCitationCount:
      message.ragSnapshot?.items?.filter((item: any) => item.usedInContext)
        .length ?? 0,
    sourcesReady: true,
    rawMessage: message,
  })),
  toMessageViewModels: vi.fn((messages: any[]) =>
    messages.map((message: any) => ({
      uid: message.uid,
      role: message.role,
      type: message.type,
      content: message.message,
      sequence: message.sequence,
      provider: message.provider,
      model: message.model,
      createdAt: message.createdAt,
      updatedAt: message.updatedAt,
      createdLabel: "",
      citationItems: message.ragSnapshot?.items ?? [],
      citationCount: message.ragSnapshot?.items?.length ?? 0,
      usedCitationCount:
        message.ragSnapshot?.items?.filter((item: any) => item.usedInContext)
          .length ?? 0,
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

import {
  listGlobalChatSessions,
  loadChatMessages,
  streamGlobalChatEvents,
} from "@/console/services/chat";
import { useGlobalChatStore } from "@/console/stores/global-chat";
import { useProviderModelStore } from "@/console/stores/provider-model";

function session(uid: string) {
  return {
    uid,
    title: uid,
    ownerType: "admin",
    provider: "openai",
    model: "gpt",
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  };
}

function message(
  uid: string,
  role: "user" | "assistant",
  text: string,
  sequence: number,
) {
  return {
    uid,
    role,
    type: "message",
    message: text,
    sequence,
    provider: "OpenAI",
    model: "gpt",
    ragSnapshot: null,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  };
}

async function* events(values: unknown[]) {
  for (const value of values) yield value;
}

function enableChatModel() {
  const providerStore = useProviderModelStore();
  providerStore.enabledProviders = [
    {
      uid: "provider-1",
      name: "openai",
      isCustom: false,
      isEnabled: true,
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
}

describe("global chat store", () => {
  it("加载会话并在选择时加载对应消息时间线", async () => {
    vi.mocked(listGlobalChatSessions).mockResolvedValue([
      session("session-1"),
    ] as never);
    vi.mocked(loadChatMessages).mockResolvedValue({
      messages: [message("message-1", "user", "Earlier", 1)],
      hasMoreBefore: true,
      hasMoreAfter: false,
      oldestSequence: 1,
      newestSequence: 1,
    } as never);
    const store = useGlobalChatStore();

    await store.loadSessions();
    await store.selectSession("session-1");

    expect(store.sessions).toMatchObject([{ uid: "session-1" }]);
    expect(store.messages).toMatchObject([
      { uid: "message-1", content: "Earlier" },
    ]);
    expect(store.hasMoreBefore).toBe(true);
    expect(store.oldestSequence).toBe(1);
  });

  it("消费 SSE 并完成临时 session、消息 delta 和最终引用状态", async () => {
    enableChatModel();
    vi.mocked(streamGlobalChatEvents).mockResolvedValue(
      events([
        { event: "session_ready", session: session("session-1") },
        {
          event: "generation_start",
          sessionUid: "session-1",
          generationUid: "generation-1",
          userMessage: message("user-1", "user", "Hello", 1),
          assistantMessage: message("assistant-1", "assistant", "", 2),
        },
        {
          event: "rag_ready",
          messageUid: "assistant-1",
          ragSnapshot: { items: [{ usedInContext: true }] },
        },
        { event: "delta", messageUid: "assistant-1", delta: "Hi" },
        {
          event: "message_done",
          message: {
            ...message("assistant-1", "assistant", "Hi", 2),
            ragSnapshot: { items: [{ usedInContext: true }] },
          },
        },
      ]) as never,
    );
    const store = useGlobalChatStore();
    store.setProviderModel("provider-1", "model-1");
    store.draft = " Hello ";

    await store.sendMessage();
    await vi.waitFor(() => expect(store.isStreaming).toBe(false));

    expect(store.activeSessionUid).toBe("session-1");
    expect(store.messages).toMatchObject([
      { uid: "user-1", content: "Hello" },
      {
        uid: "assistant-1",
        content: "Hi",
        citationCount: 1,
        sourcesReady: true,
      },
    ]);
  });

  it("取消尚未取得 generation UID 的流时不留下进行中的状态", async () => {
    enableChatModel();
    vi.mocked(streamGlobalChatEvents).mockImplementation(
      async (_request, signal) =>
        (async function* () {
          await new Promise<void>((resolve) => {
            signal?.addEventListener("abort", () => resolve(), { once: true });
          });
        })() as never,
    );
    const store = useGlobalChatStore();
    store.setProviderModel("provider-1", "model-1");
    store.draft = "Cancel me";

    await store.sendMessage();
    await vi.waitFor(() => expect(store.isStreaming).toBe(true));
    await store.cancelGeneration();

    expect(store.isStreaming).toBe(false);
    expect(store.cancelledMessageUids).toHaveLength(1);
  });

  it("会话切换后，旧流结果不会污染新的 active timeline", async () => {
    enableChatModel();
    let release!: () => void;
    vi.mocked(streamGlobalChatEvents).mockResolvedValue(
      (async function* () {
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        yield { event: "session_ready", session: session("old-session") };
      })() as never,
    );
    const store = useGlobalChatStore();
    store.setProviderModel("provider-1", "model-1");
    store.draft = "Old request";

    await store.sendMessage();
    await vi.waitFor(() => expect(release).toBeTypeOf("function"));
    store.startNewSession();
    release();
    await vi.waitFor(() =>
      expect(store.sessions).toMatchObject([{ uid: "old-session" }]),
    );

    expect(store.activeSessionUid).toBeNull();
    expect(store.messages).toEqual([]);
  });
});
