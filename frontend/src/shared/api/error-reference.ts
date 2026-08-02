export interface BackendErrorReference {
  errorId?: string;
  requestId?: string;
}

/** 从 HTTP/SSE 错误载荷读取后端关联标识，不依赖具体 API client。 */
export function readBackendErrorReference(
  payload: unknown,
  response?: Response,
): BackendErrorReference {
  const errorId = readStringField(payload, "error_id", "errorId");
  const requestId =
    readStringField(payload, "request_id", "requestId") ??
    response?.headers.get("X-Request-ID") ??
    undefined;

  return { errorId, requestId };
}

/** 优先展示 errorId；没有业务错误 ID 时退回 requestId。 */
export function formatErrorWithReference(
  message: string,
  reference: BackendErrorReference,
): string {
  const referenceId = reference.errorId ?? reference.requestId;
  return referenceId ? `${message} Reference: ${referenceId}` : message;
}

function readStringField(
  payload: unknown,
  snakeCaseKey: string,
  camelCaseKey: string,
): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }

  const record = payload as Record<string, unknown>;
  const value = record[snakeCaseKey] ?? record[camelCaseKey];
  return typeof value === "string" && value ? value : undefined;
}
