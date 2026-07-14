import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { authApi } from "@/console/api/auth";
import type { components } from "@/shared/api/generated/schema";

// Token 存储 Key 常量
const ADMIN_ACCESS_TOKEN_KEY = "tadaask.admin.accessToken";
type AdminRead = components["schemas"]["AdminRead"];
type AuthStatus = "unknown" | "authenticated" | "anonymous";

/**
 * Console 登录态 store。
 */
export const useAuthStore = defineStore("console-auth", () => {
  const token = ref<string | null>(
    window.localStorage.getItem(ADMIN_ACCESS_TOKEN_KEY),
  );
  const status = ref<AuthStatus>(token.value ? "unknown" : "anonymous");
  const currentAdmin = ref<AdminRead | null>(null);
  const isLoading = ref(false);
  const errorMessage = ref<string | null>(null);
  let initializePromise: Promise<void> | null = null;

  const isAuthenticated = computed(() => status.value === "authenticated");
  const isInitialized = computed(() => status.value !== "unknown");

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
   * 获取当前 token
   */
  function getToken(): string | null {
    return token.value;
  }

  /**
   * 登出，清除 token 和错误信息
   */
  function logout(): void {
    invalidateSession();
    errorMessage.value = null;
  }

  /** 清除失效会话；401 middleware 和路由初始化共用。 */
  function invalidateSession(): void {
    persistToken(null);
    currentAdmin.value = null;
    status.value = "anonymous";
  }

  /** 首次路由进入前向后端确认 token，避免无效 token 短暂进入 Console。 */
  async function initializeAuth(): Promise<void> {
    if (status.value !== "unknown") return;
    if (initializePromise) return await initializePromise;

    initializePromise = (async () => {
      if (!token.value) {
        status.value = "anonymous";
        return;
      }

      try {
        const { data, error } = await authApi.me();
        if (error || !data) {
          invalidateSession();
          return;
        }
        currentAdmin.value = data;
        status.value = "authenticated";
      } catch {
        invalidateSession();
      }
    })().finally(() => {
      initializePromise = null;
    });

    await initializePromise;
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
        invalidateSession();
        errorMessage.value =
          response.status === 401
            ? "Invalid username or password."
            : "Unable to sign in. Please try again.";
        return false;
      }

      persistToken(data.access_token);
      status.value = "authenticated";
      return true;
    } catch (err) {
      console.error("[AuthStore] Login error:", err);
      invalidateSession();
      errorMessage.value = "Unable to sign in. Please try again.";
      return false;
    } finally {
      isLoading.value = false;
    }
  }

  return {
    errorMessage,
    currentAdmin,
    getToken,
    initializeAuth,
    invalidateSession,
    isAuthenticated,
    isInitialized,
    isLoading,
    login,
    logout,
  };
});
