import { describe, expect, it, vi } from "vitest";
import {
  buildAdminChatRequest,
  createDefaultRagOptions,
  mergeRagOptions,
  toMessageViewModel,
  toSessionViewModel,
} from "@/console/services/chat";

describe("console chat service", () => {
  it("合并 RAG 默认值且每次创建独立对象", () => {
    const first = createDefaultRagOptions();
    const second = createDefaultRagOptions();
    first.topK = 99;

    expect(second.topK).toBe(8);
    expect(
      mergeRagOptions({ mode: "full", rerankEnabled: false }),
    ).toMatchObject({
      mode: "full",
      topK: 8,
      rerankEnabled: false,
      standaloneEnabled: false,
    });
  });

  it("构造请求时清理文本、去重 source，并保留显式 RAG 覆盖", () => {
    const request = buildAdminChatRequest({
      message: "  explain this  ",
      chatSessionUid: null,
      providerUid: "provider-1",
      modelUid: "model-1",
      adminSystemPrompt: "  system  ",
      thinking: "medium",
      sourceUids: [" source-a ", "", "source-a", "source-b"],
      ragOptions: {
        ...createDefaultRagOptions(),
        topK: 3,
        standaloneEnabled: true,
      },
    });

    expect(request).toEqual({
      message: "explain this",
      chatSessionUid: null,
      providerUid: "provider-1",
      modelUid: "model-1",
      adminSystemPrompt: "system",
      thinking: "medium",
      sourceUids: ["source-a", "source-b"],
      ragOptions: expect.objectContaining({ topK: 3, standaloneEnabled: true }),
    });
  });

  it("将会话和消息映射为 UI 所需的 citation 数据", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-26T10:00:00Z"));

    const session = toSessionViewModel({
      uid: "session-1",
      title: "",
      provider: "openai",
      model: "gpt",
      createdAt: "2026-07-26T09:00:00Z",
      updatedAt: "2026-07-26T09:58:00Z",
    } as never);
    const message = toMessageViewModel({
      uid: "message-1",
      role: "assistant",
      type: "answer",
      message: "Answer",
      sequence: 2,
      provider: "openai",
      model: "gpt",
      createdAt: "2026-07-26T09:59:00Z",
      updatedAt: "2026-07-26T09:59:00Z",
      ragSnapshot: {
        items: [{ usedInContext: true }, { usedInContext: false }],
      },
    } as never);

    expect(session).toMatchObject({ uid: "session-1", updatedLabel: "2m" });
    expect(session.title).not.toBe("");
    expect(message).toMatchObject({
      content: "Answer",
      citationCount: 2,
      usedCitationCount: 1,
      sourcesReady: true,
    });
  });
});
