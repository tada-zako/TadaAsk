// 聊天消息 Markdown 渲染服务：MarkdownIt + 代码高亮 + KaTeX + XSS 过滤
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
// 按需注册 highlight.js 语言包，减少打包体积
import bash from "highlight.js/lib/languages/bash";
import css from "highlight.js/lib/languages/css";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";
import MarkdownIt from "markdown-it";
import markdownItKatex from "markdown-it-katex";

export interface RenderChatMarkdownOptions {
  /** 代码块复制按钮的文案（支持 i18n） */
  copyCodeLabel: string;
}

/** markdown-it 渲染时的环境变量 */
interface ChatMarkdownEnv {
  copyCodeLabel?: string;
}

/** 代码语言别名映射：将常见简写/别名统一到 highlight.js 注册的语言名 */
const LANGUAGE_ALIASES: Record<string, string> = {
  cjs: "javascript",
  html: "xml",
  js: "javascript",
  jsx: "javascript",
  md: "markdown",
  mjs: "javascript",
  py: "python",
  sh: "bash",
  shell: "bash",
  ts: "typescript",
  tsx: "typescript",
  vue: "xml",
  yml: "yaml",
  zsh: "bash",
};

/** 允许的链接协议白名单，防止 javascript: / data: 等危险协议注入 */
const SAFE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:"]);

/** MarkdownIt 实例缓存，避免重复创建 */
let markdownRenderer: MarkdownIt | null = null;

registerHighlightLanguages();

/** 将聊天消息中的 Markdown 文本渲染为安全的 HTML */
export function renderChatMarkdown(
  content: string,
  options: RenderChatMarkdownOptions,
): string {
  const renderer = getMarkdownRenderer();
  const html = renderer.render(content, {
    copyCodeLabel: options.copyCodeLabel,
  } satisfies ChatMarkdownEnv);

  // DOMPurify 二次过滤：只允许安全的标签和属性，防御 XSS
  return DOMPurify.sanitize(html, {
    ADD_ATTR: [
      "aria-label",
      "data-chat-code-copy",
      "data-chat-code-lang",
      "data-copied",
      "rel",
      "target",
      "type",
    ],
    ADD_TAGS: ["button", "figcaption", "figure"],
    FORBID_TAGS: [
      "audio",
      "embed",
      "form",
      "iframe",
      "img",
      "input",
      "object",
      "script",
      "select",
      "style",
      "textarea",
      "video",
    ],
  });
}

/** 获取缓存的 MarkdownIt 实例，首次调用时初始化并配置插件 */
function getMarkdownRenderer(): MarkdownIt {
  if (markdownRenderer) {
    return markdownRenderer;
  }

  // 关闭 html 标签支持，从源头阻止 HTML 注入
  const renderer = new MarkdownIt({
    breaks: false,
    html: false,
    linkify: true,
    typographer: false,
  });

  renderer.use(markdownItKatex, {
    errorColor: "#ff6b6b",
    throwOnError: false,
    trust: false,
  });

  // 覆盖 link/image/code block 等样式规则
  configureLinks(renderer);
  configureImages(renderer);
  configureCodeBlocks(renderer);

  markdownRenderer = renderer;
  return renderer;
}

/** 覆写链接渲染规则：过滤危险协议，强制新窗口打开并防 tabnabbing */
function configureLinks(renderer: MarkdownIt) {
  const defaultLinkOpen =
    renderer.renderer.rules.link_open ??
    ((tokens, idx, options, _env, self) =>
      self.renderToken(tokens, idx, options));

  renderer.renderer.rules.link_open = (tokens, idx, options, _env, self) => {
    const token = tokens[idx];
    const href = token.attrGet("href");

    // 不安全链接替换为 #，防止钓鱼/恶意跳转
    if (!href || !isSafeLinkHref(href)) {
      token.attrSet("href", "#");
    }

    token.attrSet("target", "_blank");
    token.attrSet("rel", "noopener noreferrer");

    return defaultLinkOpen(tokens, idx, options, _env, self);
  };
}

/** 覆写图片渲染规则：将图片转换为文本链接，避免外部资源加载泄露隐私 */
function configureImages(renderer: MarkdownIt) {
  renderer.renderer.rules.image = (tokens, idx) => {
    const token = tokens[idx];
    const src = token.attrGet("src") ?? "";
    const label = token.content || token.attrGet("alt") || src || "image";

    // 不安全的 src 仅展示纯文本 label
    if (!src || !isSafeLinkHref(src)) {
      return escapeHtml(label);
    }

    return `<a class="chat-md-image-link" href="${escapeAttribute(src)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
  };
}

/** 覆写围栏代码块渲染规则：添加语言标签、复制按钮，并使用 highlight.js 高亮 */
function configureCodeBlocks(renderer: MarkdownIt) {
  renderer.renderer.rules.fence = (tokens, idx, _options, env) => {
    const token = tokens[idx];
    const normalizedLanguage = normalizeLanguage(token.info);
    const highlighted = highlightCode(token.content, normalizedLanguage);
    const languageLabel = normalizedLanguage || "text";
    const copyCodeLabel =
      (env as ChatMarkdownEnv | null)?.copyCodeLabel ?? "Copy";

    // 使用 figure/figcaption 语义化结构包裹代码块
    return [
      `<figure class="chat-md-code-block" data-chat-code-lang="${escapeAttribute(languageLabel)}">`,
      '<figcaption class="chat-md-code-head">',
      `<span class="chat-md-code-lang">${escapeHtml(languageLabel)}</span>`,
      `<button type="button" class="chat-md-code-copy" data-chat-code-copy aria-label="${escapeAttribute(copyCodeLabel)}">${escapeHtml(copyCodeLabel)}</button>`,
      "</figcaption>",
      '<pre class="console-scrollbar"><code class="hljs">',
      highlighted,
      "</code></pre>",
      "</figure>\n",
    ].join("");
  };
}

function registerHighlightLanguages() {
  hljs.registerLanguage("bash", bash);
  hljs.registerLanguage("css", css);
  hljs.registerLanguage("javascript", javascript);
  hljs.registerLanguage("json", json);
  hljs.registerLanguage("markdown", markdown);
  hljs.registerLanguage("python", python);
  hljs.registerLanguage("sql", sql);
  hljs.registerLanguage("typescript", typescript);
  hljs.registerLanguage("xml", xml);
  hljs.registerLanguage("yaml", yaml);
}

/** 代码高亮，不支持的语言或高亮失败时返回转义后的纯文本 */
function highlightCode(code: string, language: string): string {
  if (!language || !hljs.getLanguage(language)) {
    return escapeHtml(code);
  }

  try {
    return hljs.highlight(code, {
      language,
      ignoreIllegals: true,
    }).value;
  } catch {
    return escapeHtml(code);
  }
}

/**
 * 将 markdown 代码块的语言标识规范化
 * 1. 取空格分隔的首个 token  2. 统一小写并过滤非法字符  3. 映射别名
 */
function normalizeLanguage(info: string): string {
  const rawLanguage = info.trim().split(/\s+/)[0] ?? "";
  const safeLanguage = rawLanguage.toLowerCase().replace(/[^a-z0-9_+-]/g, "");
  return LANGUAGE_ALIASES[safeLanguage] ?? safeLanguage;
}

/** 检查链接是否安全：允许相对路径、锚点和白名单协议 */
function isSafeLinkHref(href: string): boolean {
  const trimmedHref = href.trim();

  // 相对路径和页内锚点始终放行
  if (
    trimmedHref.startsWith("#") ||
    trimmedHref.startsWith("/") ||
    trimmedHref.startsWith("./") ||
    trimmedHref.startsWith("../")
  ) {
    return true;
  }

  try {
    return SAFE_LINK_PROTOCOLS.has(new URL(trimmedHref).protocol);
  } catch {
    return false;
  }
}

/** HTML 实体转义，防止 XSS */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** HTML 属性值转义（当前复用 escapeHtml，预留独立 escape 策略扩展点） */
function escapeAttribute(value: string): string {
  return escapeHtml(value);
}
