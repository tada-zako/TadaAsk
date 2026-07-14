import { ref } from "vue";
import { defineStore } from "pinia";

import { authApi } from "@/console/api/auth";

// Token 存储 Key 常量
const ADMIN_ACCESS_TOKEN_KEY = "tadaask.admin.accessToken";

/**
 * Console 登录态 store。
 */
export const useAuthStore = defineStore("console-auth", () => {
  const token = ref<string | null>(
    window.localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY),
  );
  const isAuthenticated = ref(false);
  const isLoading = ref(false);
  const errorMessage = ref<string | null>(null);
  let verifyPromise: Promise<boolean> | null = null;

  /**
   * 设置 token 并同步到 localStorage
   */
  function persistToken(nextToken: string | null): void {
    token.value = nextToken;

    if (nextToken) {
      window.localStorage.setItem(ADMIN_ACCESS_TOKEN_KEY, nextToken);
    } else {
      window.localStorage.removeItem(ADMIN_ACCESS_TOKEN_KEY);
    }
  }

  /**
   * 登出，清除 token 和错误信息
   */
  function logout(): void {
    clearAuth();
    errorMessage.value = null;
  }

  /** 清除失效会话；401 middleware 和路由初始化共用。 */
  function clearAuth(): void {
    persistToken(null);
    isAuthenticated.value = false;
  }

  /** 向后端确认本地 token；合并并发调用，避免重复请求 /me。 */
  async function verifyToken(): Promise<boolean> {
    if (!token.value) return false;
    if (isAuthenticated.value) return true;
    if (verifyPromise) return await verifyPromise;

    // 将所有的请求合并为同一个 Promise 对象
    verifyPromise = (async () => {
      try {
        const { data, error } = await authApi.me();
        if (error || !data) {
          clearAuth();
          return false;
        }
        isAuthenticated.value = true;
        return true;
      } catch {
        clearAuth();
        return false;
      }
    })().finally(() => {
      verifyPromise = null;
    });

    return await verifyPromise;
  }

  /**
   * 登录，调用 authApi.login 接口获取 token
   * @param username
   * @param password
   * @returns
   */
  async function login(username: string, password: string): Promise<boolean> {
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const { data, error, response } = await authApi.login({
        username,
        password,
      });

      if (error || !data?.access_token) {
        clearAuth();
        errorMessage.value =
          response.status === 401
            ? "Invalid username or password."
            : "Unable to sign in. Please try again.";
        return false;
      }

      persistToken(data.access_token);
      isAuthenticated.value = true;
      return true;
    } catch (err) {
      console.error("[AuthStore] Login error:", err);
      clearAuth();
      errorMessage.value = "Unable to sign in. Please try again.";
      return false;
    } finally {
      isLoading.value = false;
    }
  }

  return {
    token,
    errorMessage,
    clearAuth,
    isAuthenticated,
    isLoading,
    login,
    logout,
    verifyToken,
  };
});
