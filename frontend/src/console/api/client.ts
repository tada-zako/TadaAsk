import type { Middleware } from "openapi-fetch";
import { createApiClient } from "@/shared/api/create-client";
import router from "@/console/router";
import { useAuthStore } from "@/console/stores/auth";

const ADMIN_LOGIN_PATH = "/admin/auth/login";

/**
 * Console Admin 鉴权中间件：
 * - login 请求不携带 token；
 * - 其它 admin 请求从 auth store 注入 Authorization；
 * - 401 表示后端不再接受当前 token，直接登出并回到登录页。
 */
const authMiddleware: Middleware = {
  /**
   * 请求处理
   */
  onRequest({ request, schemaPath }) {
    if (schemaPath.startsWith("/admin/") && schemaPath !== ADMIN_LOGIN_PATH) {
      const authStore = useAuthStore();

      if (authStore.isAuthenticated) {
        const token = authStore.getToken(); // 取当前 token

        const headers = new Headers(request.headers);
        headers.set("Authorization", `Bearer ${token}`);
        return new Request(request, { headers });
      }
    }

    return request;
  },

  /**
   * 响应处理
   */
  onResponse({ response, schemaPath }) {
    if (
      schemaPath.startsWith("/admin/") &&
      schemaPath !== ADMIN_LOGIN_PATH &&
      response.status === 401
    ) {
      // 后端不再接收当前 token
      const authStore = useAuthStore();

      // 设置登出状态
      authStore.logout();

      if (router.currentRoute.value.path !== "/login") {
        // 跳转登录页面，并保留当前路由地址
        void router.replace({
          path: "/login",
          query: { redirect: router.currentRoute.value.fullPath },
        });
      }
    }

    return response;
  },
};

/** Admin Console 专属 API client。 */
export const client = createApiClient({
  middlewares: [authMiddleware],
});
