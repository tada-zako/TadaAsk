import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@/shared/api/generated/schema";

/**
 * 前端统一的 OpenAPI client
 */
export const client = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
});

/**
 * Admin 鉴权请求的预留挂载点。
 */
const authMiddleware: Middleware = {
  onRequest({ request, schemaPath }) {
    if (
      schemaPath.startsWith("/admin/") &&
      schemaPath !== "/admin/auth/login"
    ) {
      // TODO: 后续挂载 Admin 鉴权的 token
    }

    return request;
  },
};

client.use(authMiddleware);
