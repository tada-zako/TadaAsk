import { createApiClient } from "@/shared/api/create-client";

/** 每个 Web Component 实例持有独立 client，避免多个部署地址相互污染。 */
export function createWidgetApiClient(baseUrl: string) {
  return createApiClient({ baseUrl });
}
