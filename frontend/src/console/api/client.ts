import type { Middleware } from "openapi-fetch";
import { createApiClient } from "@/shared/api/create-client";
import router from "@/console/router";
import { useAuthStore } from "@/console/stores/auth";
import { resolveSafeAuthRedirect } from "@/console/lib/auth-redirect";

const ADMIN_LOGIN_PATH = "/admin/auth/login";
const ADMIN_ME_PATH = "/admin/auth/me";
let unauthorizedRedirectPending = false; // 多并发 401 路由跳转限制；避免并发跳转多次重写 redirect

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

      const token = authStore.getToken();
      // 初始化 /me 时 status 仍为 unknown，但本地 token 也必须被带上。
      if (token) {
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
      authStore.invalidateSession();

      if (
        schemaPath !== ADMIN_ME_PATH &&
        router.currentRoute.value.path !== "/login" &&
        !unauthorizedRedirectPending
      ) {
        // 设置跳转进行时标记
        unauthorizedRedirectPending = true;
        const redirect = resolveSafeAuthRedirect(
          router,
          router.currentRoute.value.fullPath,
        );
        // 跳转登录页面，并保留当前路由地址
        void router
          .replace({
            path: "/login",
            query: { redirect },
          })
          .finally(() => {
            unauthorizedRedirectPending = false;
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
