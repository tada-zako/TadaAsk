import { computed, ref } from "vue";
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
  const isLoading = ref(false);
  const errorMessage = ref<string | null>(null);

  const isAuthenticated = computed(() => Boolean(token.value));

  /**
   * 设置 token 并同步到 localStorage
   */
  function setToken(nextToken: string | null): void {
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
    setToken(null);
    errorMessage.value = null;
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
      const { data, error } = await authApi.login({ username, password });

      if (error || !data?.access_token) {
        setToken(null);
        errorMessage.value = "Invalid username or password.";
        return false;
      }

      setToken(data.access_token);
      return true;
    } catch (err) {
      console.error("[AuthStore] Login error:", err);
      setToken(null);
      errorMessage.value = "Unable to sign in. Please try again.";
      return false;
    } finally {
      isLoading.value = false;
    }
  }

  return {
    errorMessage,
    getToken,
    isAuthenticated,
    isLoading,
    login,
    logout,
  };
});
