import type { Middleware } from "openapi-fetch";
import { createApiClient } from "@/shared/api/create-client";

/**
 * Console Admin 鉴权中间件。
 *
 * 当前只固定挂载边界，后续登录态接入时在这里注入 Authorization。
 */
export const authMiddleware: Middleware = {
  onRequest({ request, schemaPath }) {
    if (schemaPath !== "/admin/auth/login") {
      // TODO: 后续从 console auth store/token helper 注入 Bearer token。
    }

    return request;
  },
};

/** Admin Console 专属 API client。 */
export const client = createApiClient({
  middlewares: [authMiddleware],
});
