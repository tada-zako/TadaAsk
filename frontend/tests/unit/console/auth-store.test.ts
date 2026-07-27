import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/api/auth", () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
  },
}));

import { authApi } from "@/console/api/auth";
import { useAuthStore } from "@/console/stores/auth";

const tokenKey = "tadaask.admin.accessToken";

describe("auth store", () => {
  it("从 localStorage 读取 token，登录后持久化认证状态", async () => {
    window.localStorage.setItem(tokenKey, "saved-token");
    expect(useAuthStore().token).toBe("saved-token");

    vi.mocked(authApi.login).mockResolvedValue({
      data: { access_token: "new-token" },
      error: undefined,
      response: new Response(null, { status: 200 }),
    } as never);
    const store = useAuthStore();

    await expect(store.login("admin", "password")).resolves.toBe(true);
    expect(authApi.login).toHaveBeenCalledWith({
      username: "admin",
      password: "password",
    });
    expect(store).toMatchObject({
      token: "new-token",
      isAuthenticated: true,
      isLoading: false,
      errorMessage: null,
    });
    expect(window.localStorage.getItem(tokenKey)).toBe("new-token");
  });

  it("无效凭证与登出都会清除 token", async () => {
    const store = useAuthStore();
    vi.mocked(authApi.login).mockResolvedValue({
      data: undefined,
      error: { detail: "invalid" },
      response: new Response(null, { status: 401 }),
    } as never);

    await expect(store.login("admin", "wrong")).resolves.toBe(false);
    expect(store).toMatchObject({
      token: null,
      isAuthenticated: false,
      errorMessage: "Invalid username or password.",
    });

    store.logout();
    expect(store.errorMessage).toBeNull();
    expect(window.localStorage.getItem(tokenKey)).toBeNull();
  });

  it("合并并发 token 验证，并在服务端拒绝时清理凭证", async () => {
    const store = useAuthStore();
    window.localStorage.setItem(tokenKey, "token");
    store.token = "token";
    let resolveMe!: (value: unknown) => void;
    vi.mocked(authApi.me).mockReturnValue(
      new Promise((resolve) => {
        resolveMe = resolve;
      }) as never,
    );

    const first = store.verifyToken();
    const second = store.verifyToken();
    expect(authApi.me).toHaveBeenCalledTimes(1);
    resolveMe({ data: { username: "admin" }, error: undefined });

    await expect(Promise.all([first, second])).resolves.toEqual([true, true]);
    expect(store.isAuthenticated).toBe(true);

    store.clearAuth();
    store.token = "expired";
    window.localStorage.setItem(tokenKey, "expired");
    vi.mocked(authApi.me).mockResolvedValue({
      data: undefined,
      error: {},
    } as never);
    await expect(store.verifyToken()).resolves.toBe(false);
    expect(store).toMatchObject({ token: null, isAuthenticated: false });
    expect(window.localStorage.getItem(tokenKey)).toBeNull();
  });
});
