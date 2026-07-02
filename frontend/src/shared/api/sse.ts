/**
 * SSE 流解析后返回的封装对象
 */
interface SseFrame {
  id?: string;
  event: string;
  data: string;
}

/**
 * 解析后端返回的 SSE ReadableStream
 */
export async function* parseSseStream<TEvent>(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<TEvent, void, unknown> {
  // 读取流并解析 SSE frame
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      let boundary = findFrameBoundary(buffer);
      while (boundary) {
        // 切分出完整的 SSE frame
        const frameText = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.endIndex);

        const frame = parseSseFrame(frameText);
        if (frame) {
          // NOTE: 目前后端 SSE 传输的都是 schema data，
          // 这里可以直接 JSON.parse 解析
          const payload = frame.data ? JSON.parse(frame.data) : {};
          yield { ...payload, event: frame.event, sseId: frame.id } as TEvent;
        }

        boundary = findFrameBoundary(buffer);
      }
    }

    // 流结束处理，最后剩余的 buffer 按不完整 frame 处理
    buffer += decoder.decode(); // 流结束时解码剩余的 buffer
    if (buffer.trim()) {
      // 避免 JSON.parse 损坏内容
      throw new Error("SSE stream ended with an incomplete frame.");
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * 解析单个 SSE frame
 *
 * Frame example:
 * event: chat_update
 * data: {
 * data:   "generationUid": "gen-8f9d0c2e",
 * data:   "sessionUid": "sess-3a2b1c0d",
 * data:   "userMessage": {
 * data:     "id": "msg-u1",
 * data:     "role": "user",
 * data:     "content": "请分析这段代码",
 * data:     "created_at": "2026-06-29T10:00:00Z"
 * data:   },
 * data: }
 */
function parseSseFrame(frameText: string): SseFrame | null {
  const lines = frameText.split(/\r?\n/);
  const dataLines: string[] = [];
  let id: string | undefined;
  let event = "message"; // 默认 event 类型

  for (const line of lines) {
    if (!line || line.startsWith(":")) {
      continue;
    }

    // 解析 field 和 value
    const separatorIndex = line.indexOf(":");
    const field = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
    const rawValue =
      separatorIndex === -1 ? "" : line.slice(separatorIndex + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;

    if (field === "id") {
      id = value;
    } else if (field === "event") {
      event = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  if (!dataLines.length && event === "message") {
    return null;
  }

  return {
    id,
    event,
    data: dataLines.join("\n"),
  };
}

/** 查找 buffer 中最早出现的 SSE frame 分隔符 */
function findFrameBoundary(
  buffer: string,
): { index: number; endIndex: number } | null {
  const lineBreak = buffer.indexOf("\n\n");
  const windowsLineBreak = buffer.indexOf("\r\n\r\n");

  if (lineBreak === -1 && windowsLineBreak === -1) {
    return null;
  }

  if (
    lineBreak !== -1 &&
    (windowsLineBreak === -1 || lineBreak < windowsLineBreak)
  ) {
    // 存在 \n\n 分隔符，并且在 \r\n\r\n 分隔符之前
    return { index: lineBreak, endIndex: lineBreak + 2 };
  }

  return { index: windowsLineBreak, endIndex: windowsLineBreak + 4 };
}
