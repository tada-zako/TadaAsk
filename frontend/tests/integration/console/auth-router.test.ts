import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/api/auth", () => ({
  authApi: { me: vi.fn(), login: vi.fn() },
}));

import { authApi } from "@/console/api/auth";
import { createConsoleRouter } from "@/console/router";
import { useAuthStore } from "@/console/stores/auth";

describe("auth + router integration", () => {
  it("未认证访问保护路由时跳转登录并保留内部 redirect", async () => {
    const router = createConsoleRouter(createMemoryHistory());

    await router.push("/sources");

    expect(router.currentRoute.value).toMatchObject({
      path: "/login",
      query: { redirect: "/sources" },
    });
  });

  it("有效本地 token 会在 guard 中验证后访问保护路由", async () => {
    const store = useAuthStore();
    store.token = "saved-token";
    vi.mocked(authApi.me).mockResolvedValue({
      data: { username: "admin" },
      error: undefined,
    } as never);
    const router = createConsoleRouter(createMemoryHistory());

    await router.push("/sources");

    expect(authApi.me).toHaveBeenCalledTimes(1);
    expect(store.isAuthenticated).toBe(true);
    expect(router.currentRoute.value.path).toBe("/sources");
  });

  it("已登录访问 login 时拒绝外部 redirect", async () => {
    const store = useAuthStore();
    store.token = "token";
    store.isAuthenticated = true;
    const router = createConsoleRouter(createMemoryHistory());

    await router.push("/login?redirect=//evil.example");

    expect(router.currentRoute.value.path).toBe("/project");
  });
});
