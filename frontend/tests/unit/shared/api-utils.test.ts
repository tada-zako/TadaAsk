import type { Router } from "vue-router";
import { describe, expect, it, vi } from "vitest";
import {
  getApiErrorMessage,
  getErrorMessage,
  unwrapApiData,
} from "@/console/lib/api-result";
import { resolveSafeAuthRedirect } from "@/console/lib/auth-redirect";
import {
  normalizeOptionalText,
  normalizeProgress,
} from "@/console/lib/normalize";

describe("公共 API 工具", () => {
  it("归一化 FastAPI detail 与未知错误", () => {
    expect(getApiErrorMessage({ detail: "Not allowed" }, "fallback")).toBe(
      "Not allowed",
    );
    expect(
      getApiErrorMessage(
        { detail: [{ msg: "Invalid email" }, "other"] },
        "fallback",
      ),
    ).toBe("Invalid email, other");
    expect(getApiErrorMessage({ message: "hidden" }, "fallback")).toBe(
      "fallback",
    );
    expect(getErrorMessage(new Error("local"), "fallback")).toBe("local");
    expect(() => unwrapApiData(undefined, null, "missing")).toThrow("missing");
  });

  it("只接受路由表中已注册的内部登录重定向", () => {
    const resolve = vi.fn((value: string) => ({
      fullPath: value,
      matched: value.startsWith("/known") || value === "/login" ? [{}] : [],
      name: value === "/login" ? "login" : "project",
    }));
    const router = { resolve } as unknown as Router;

    expect(resolveSafeAuthRedirect(router, "/known?tab=1")).toBe(
      "/known?tab=1",
    );
    expect(resolveSafeAuthRedirect(router, "//evil.example")).toBe("/project");
    expect(resolveSafeAuthRedirect(router, "https://evil.example")).toBe(
      "/project",
    );
    expect(resolveSafeAuthRedirect(router, "/login", "/fallback")).toBe(
      "/fallback",
    );
    expect(resolveSafeAuthRedirect(router, "/missing", "/fallback")).toBe(
      "/fallback",
    );
  });

  it("规范化可选文本和后端兼容的进度值", () => {
    expect(normalizeOptionalText("  text  ")).toBe("text");
    expect(normalizeOptionalText(" ")).toBeNull();
    expect(normalizeProgress(0.456)).toBe(46);
    expect(normalizeProgress(150)).toBe(100);
    expect(normalizeProgress(Number.NaN)).toBeNull();
  });
});
