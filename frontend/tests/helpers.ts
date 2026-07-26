import { nextTick } from "vue";

/**
 * 流式文本 mock 函数；
 * 将文本分块包装为浏览器 ReadableStream，供 SSE 和流式响应测试复用。
 */
export function createTextStreamResponse(
  chunks: readonly string[],
  init: ResponseInit = {},
): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  const headers = new Headers(init.headers);
  if (!headers.has("content-type")) {
    headers.set("content-type", "text/event-stream");
  }
  return new Response(stream, { ...init, headers });
}

/**
 * 等待当前 Promise 队列和 Vue 响应式更新完成。
 */
export async function flushAsyncUpdates(): Promise<void> {
  await Promise.resolve();
  await nextTick();
}
