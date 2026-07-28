import { describe, expect, it, vi } from "vitest";

vi.mock("@/widget/api/widget-chat", () => ({
  createWidgetChatApi: vi.fn(),
}));
vi.mock("@/shared/api/sse", () => ({
  parseSseStream: vi.fn(),
}));

import { createWidgetChatApi } from "@/widget/api/widget-chat";
import { parseSseStream } from "@/shared/api/sse";
import {
  createWidgetChatService,
  selectCitationItems,
  toWidgetMessage,
  WidgetChatError,
} from "@/widget/services/chat";

describe("widget chat service", () => {
  it("构造已 trim 的 widget 请求并将响应交给 SSE 解析器", async () => {
    const stream = new ReadableStream<Uint8Array>();
    const parseResult = (async function* () {})();
    const api = {
      stream: vi.fn().mockResolvedValue({
        data: stream,
        error: undefined,
        response: new Response(null, { status: 200 }),
      }),
      cancel: vi.fn(),
    };
    vi.mocked(createWidgetChatApi).mockReturnValue(api as never);
    vi.mocked(parseSseStream).mockReturnValue(parseResult as never);
    const service = createWidgetChatService({
      apiBaseUrl: " https://api.example.com/ ",
      projectUid: "project-1",
      widgetUid: "widget-1",
    });

    await expect(
      service.stream({ message: "  Hello  ", chatSessionUid: null }),
    ).resolves.toBe(parseResult);
    expect(createWidgetChatApi).toHaveBeenCalledWith("https://api.example.com");
    expect(api.stream).toHaveBeenCalledWith(
      "project-1",
      "widget-1",
      { message: "Hello", chatSessionUid: null },
      undefined,
    );
    expect(parseSseStream).toHaveBeenCalledWith(stream);
  });

  it("将后端 HTTP 状态映射为访客可理解的错误", async () => {
    vi.mocked(createWidgetChatApi).mockReturnValue({
      stream: vi.fn().mockResolvedValue({
        data: undefined,
        error: { detail: "forbidden" },
        response: new Response(null, { status: 403 }),
      }),
      cancel: vi.fn().mockResolvedValue({
        data: undefined,
        error: { detail: "missing" },
        response: new Response(null, { status: 404 }),
      }),
    } as never);
    const service = createWidgetChatService({
      apiBaseUrl: "",
      projectUid: "project-1",
      widgetUid: "widget-1",
    });

    await expect(
      service.stream({ message: "Hello", chatSessionUid: null }),
    ).rejects.toMatchObject({
      name: WidgetChatError.name,
      status: 403,
      message: "This assistant is not available on this site.",
    });
    await expect(service.cancel("generation-1")).rejects.toMatchObject({
      status: 404,
      message: "This assistant could not be found.",
    });
  });

  it("按正文出现顺序筛选、去重并限制四条 citation", () => {
    const items = [1, 2, 3, 4, 5].map((citationId) => ({
      citationId,
      usedInContext: true,
    }));

    expect(
      selectCitationItems(
        "[[citation:3]] [[citation:1]] [[citation:3]] [[citation:5]] [[citation:2]] [[citation:4]]",
        items as never,
      ),
    ).toMatchObject([
      { citationId: 3, displayId: 1 },
      { citationId: 1, displayId: 2 },
      { citationId: 5, displayId: 3 },
      { citationId: 2, displayId: 4 },
    ]);
    expect(
      toWidgetMessage({ role: "system", message: "hidden" } as never),
    ).toBeNull();
  });
});
