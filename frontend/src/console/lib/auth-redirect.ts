import type { Router } from "vue-router";

/** 只接受当前 SPA 内已注册的非登录路由，避免把 redirect 当作外部地址使用。 */
export function resolveSafeAuthRedirect(
  router: Router,
  value: unknown,
  fallback = "/project",
): string {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//")
  ) {
    return fallback;
  }

  const resolved = router.resolve(value);
  if (resolved.matched.length === 0 || resolved.name === "login") {
    return fallback;
  }
  return resolved.fullPath;
}
