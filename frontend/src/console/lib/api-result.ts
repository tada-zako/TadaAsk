import {
  formatErrorWithReference,
  readBackendErrorReference,
} from "@/shared/api/error-reference";

/**
 * openapi-fetch 返回 { data, error } 形态；这里统一解包，避免各业务 service 重复解析。
 */
export function unwrapApiData<T>(
  data: T | undefined,
  error: unknown,
  fallbackMessage: string,
): T {
  if (error) {
    throw new Error(getApiErrorMessage(error, fallbackMessage));
  }

  if (data === undefined) {
    throw new Error(fallbackMessage);
  }

  return data;
}

// 解析 FastAPI 常见错误结构，支持 detail: string 和 validation detail 数组。
export function getApiErrorMessage(
  error: unknown,
  fallbackMessage: string,
): string {
  if (!error || typeof error !== "object") {
    return fallbackMessage;
  }

  const reference = readBackendErrorReference(error);

  if ("detail" in error) {
    const detail = error.detail;

    if (typeof detail === "string") {
      return formatErrorWithReference(detail, reference);
    }

    if (Array.isArray(detail)) {
      return formatErrorWithReference(
        detail
          .map((item) =>
            typeof item === "object" && item && "msg" in item
              ? String(item.msg)
              : String(item),
          )
          .join(", "),
        reference,
      );
    }
  }

  return formatErrorWithReference(fallbackMessage, reference);
}

export function getErrorMessage(
  error: unknown,
  fallbackMessage: string,
): string {
  return error instanceof Error
    ? error.message
    : getApiErrorMessage(error, fallbackMessage);
}
