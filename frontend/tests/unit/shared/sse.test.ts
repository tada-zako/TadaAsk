import { describe, expect, it } from "vitest";
import { createTextStreamResponse } from "../../helpers";
import { parseSseStream } from "@/shared/api/sse";

async function collect<T>(stream: AsyncGenerator<T>): Promise<T[]> {
  const events: T[] = [];
  for await (const event of stream) {
    events.push(event);
  }
  return events;
}

describe("parseSseStream", () => {
  it("解析跨分块的 LF/CRLF frame、event、id 和多行 data", async () => {
    const response = createTextStreamResponse([
      ": keepalive\n",
      'id: event-1\nevent: chat_update\ndata: {"answer":\n',
      'data: "hello"}\n\n',
      'event: done\r\nid: event-2\r\ndata: {"ok":true}\r\n\r\n',
    ]);

    await expect(
      collect(
        parseSseStream<{
          answer?: string;
          ok?: boolean;
          event: string;
          sseId?: string;
        }>(response.body!),
      ),
    ).resolves.toEqual([
      { answer: "hello", event: "chat_update", sseId: "event-1" },
      { ok: true, event: "done", sseId: "event-2" },
    ]);
  });

  it("保留只有 event 的 frame，并忽略纯注释 frame", async () => {
    const response = createTextStreamResponse([
      ": heartbeat\n\n",
      "event: ping\nid: ping-1\n\n",
    ]);

    await expect(
      collect(
        parseSseStream<{ event: string; sseId?: string }>(response.body!),
      ),
    ).resolves.toEqual([{ event: "ping", sseId: "ping-1" }]);
  });

  it("在 JSON 损坏或流结束时 frame 不完整时抛错并释放 reader", async () => {
    const malformed = createTextStreamResponse(['data: {"broken"}\n\n']);
    await expect(collect(parseSseStream(malformed.body!))).rejects.toThrow();
    expect(malformed.body!.locked).toBe(false);

    const incomplete = createTextStreamResponse(['data: {"partial": true}']);
    await expect(collect(parseSseStream(incomplete.body!))).rejects.toThrow(
      "SSE stream ended with an incomplete frame.",
    );
    expect(incomplete.body!.locked).toBe(false);
  });

  it("调用方提前停止迭代时释放 reader 锁", async () => {
    const response = createTextStreamResponse(['data: {"step":1}\n\n']);
    const iterator = parseSseStream<{ step: number }>(response.body!);

    await expect(iterator.next()).resolves.toMatchObject({
      done: false,
      value: { event: "message", step: 1 },
    });
    await iterator.return(undefined);

    expect(response.body!.locked).toBe(false);
  });
});
