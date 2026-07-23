const PROVIDER_DISPLAY_NAMES: Readonly<Record<string, string>> = {
  alibaba: "Alibaba Model Studio",
  "alibaba-cn": "Alibaba Model Studio (China)",
  anthropic: "Anthropic",
  deepseek: "DeepSeek",
  google: "Google AI",
  "google-ai": "Google AI",
  googleai: "Google AI",
  glm: "Zhipu GLM",
  groq: "Groq",
  kimi: "Kimi",
  minimax: "MiniMax (minimax.io)",
  "minimax-cn": "MiniMax (minimaxi.com)",
  ollama: "Ollama",
  openai: "OpenAI",
};

/** 将稳定的 Provider ID 转为控制台使用的统一展示名称。 */
export function formatProviderDisplayName(name: string): string {
  const normalized = name.trim().toLowerCase();
  const displayName = PROVIDER_DISPLAY_NAMES[normalized];
  if (displayName) {
    return displayName;
  }

  return name
    .split(/([\s_-]+)/)
    .map((part) =>
      /^[\s_-]+$/.test(part)
        ? " "
        : part.charAt(0).toUpperCase() + part.slice(1),
    )
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}
