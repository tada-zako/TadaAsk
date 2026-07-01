import { createI18n } from "vue-i18n";

import { en } from "./locales/en";
import { zhCN } from "./locales/zh-CN";

export const consoleLocales = ["en", "zh-CN"] as const;
export type ConsoleLocale = (typeof consoleLocales)[number];

// i18n 本地语言选择 key
const localeStorageKey = "tadaask.console.locale";

// 目前仅支持中（简体）英文
const messages = {
  en,
  "zh-CN": zhCN,
};

export const i18n = createI18n({
  fallbackLocale: "en",
  globalInjection: false,
  legacy: false, // 使用 Composition API
  locale: getInitialLocale(),
  messages,
});

// 设置本地语言
export function setConsoleLocale(locale: ConsoleLocale): void {
  i18n.global.locale.value = locale;
  window.localStorage.setItem(localeStorageKey, locale);
}

// 支持 .ts 中使用 i18n 能力
export function translate(
  key: string,
  params?: Record<string, string | number>,
): string {
  return i18n.global.t(key, params ?? {});
}

// 读取本地语言设置
function getInitialLocale(): ConsoleLocale {
  const stored = window.localStorage.getItem(localeStorageKey);

  // 尝试从 localStorage 中读取语言配置
  if (isConsoleLocale(stored)) {
    return stored;
  }

  // 尝试从浏览器语言中读取语言配置
  return window.navigator.language.toLowerCase().startsWith("zh")
    ? "zh-CN"
    : "en"; // 默认使用英文
}

function isConsoleLocale(value: string | null): value is ConsoleLocale {
  return consoleLocales.includes(value as ConsoleLocale);
}
