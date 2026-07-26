import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, vi } from "vitest";

beforeEach(() => {
  // 每个测试使用独立 Pinia，并清空浏览器侧持久化状态。
  setActivePinia(createPinia());
  window.localStorage.clear();
  window.sessionStorage.clear();
});

afterEach(() => {
  // Vue Test Utils 挂载到 body 的节点不能泄漏到下一个测试。
  document.body.replaceChildren();
  vi.useRealTimers();
});
