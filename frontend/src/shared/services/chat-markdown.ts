import { katex as markdownItKatex } from "@mdit/plugin-katex";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/common";
import dart from "highlight.js/lib/languages/dart";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import http from "highlight.js/lib/languages/http";
import nginx from "highlight.js/lib/languages/nginx";
import powershell from "highlight.js/lib/languages/powershell";
import protobuf from "highlight.js/lib/languages/protobuf";
import MarkdownIt from "markdown-it";

export interface RenderChatMarkdownOptions {
  /** 代码块复制按钮的文案（支持 i18n） */
  copyCodeLabel: string;
  /** 当前 assistant message 中真实存在的 citation id */
  citationIds?: readonly number[];
  /** citation 按钮的无障碍文案 */
  citationAriaLabel?: (citationId: number) => string;
  /** citation 的可见编号；省略时继续显示后端原始 ID。 */
  citationLabel?: (citationId: number) => string | number;
  /** 流式阶段隐藏尚未闭合的 citation 尾部片段 */
  streaming?: boolean;
  /** 移除当前允许集合之外的 citation marker，用于终态发布与 Widget 数量限制。 */
  stripUnknownCitationMarkers?: boolean;
}

/** markdown-it 渲染时的环境变量 */
interface ChatMarkdownEnv {
  copyCodeLabel?: string;
  citationIds?: ReadonlySet<number>;
  citationAriaLabel?: (citationId: number) => string;
  citationLabel?: (citationId: number) => string | number;
}

interface CitationTokenMeta {
  citationId: number;
}

interface CodeLanguage {
  /** highlight.js 使用的语言标识 */
  id: string;
  /** 代码块标题中展示的名称 */
  label: string;
}

/** 常见 fenced code language 别名，同时保留对用户更友好的展示名。 */
const LANGUAGE_ALIASES: Record<string, CodeLanguage> = {
  c: { id: "c", label: "C" },
  cjs: { id: "javascript", label: "JavaScript" },
  cpp: { id: "cpp", label: "C++" },
  cs: { id: "csharp", label: "C#" },
  csharp: { id: "csharp", label: "C#" },
  dart: { id: "dart", label: "Dart" },
  docker: { id: "dockerfile", label: "Dockerfile" },
  dockerfile: { id: "dockerfile", label: "Dockerfile" },
  go: { id: "go", label: "Go" },
  gql: { id: "graphql", label: "GraphQL" },
  graphql: { id: "graphql", label: "GraphQL" },
  html: { id: "xml", label: "HTML" },
  http: { id: "http", label: "HTTP" },
  ini: { id: "ini", label: "INI" },
  java: { id: "java", label: "Java" },
  js: { id: "javascript", label: "JavaScript" },
  javascript: { id: "javascript", label: "JavaScript" },
  json: { id: "json", label: "JSON" },
  jsx: { id: "javascript", label: "JSX" },
  kt: { id: "kotlin", label: "Kotlin" },
  kotlin: { id: "kotlin", label: "Kotlin" },
  md: { id: "markdown", label: "Markdown" },
  mjs: { id: "javascript", label: "JavaScript" },
  nginx: { id: "nginx", label: "Nginx" },
  plaintext: { id: "plaintext", label: "Text" },
  powershell: { id: "powershell", label: "PowerShell" },
  proto: { id: "protobuf", label: "Protobuf" },
  protobuf: { id: "protobuf", label: "Protobuf" },
  ps1: { id: "powershell", label: "PowerShell" },
  py: { id: "python", label: "Python" },
  python: { id: "python", label: "Python" },
  rb: { id: "ruby", label: "Ruby" },
  rs: { id: "rust", label: "Rust" },
  rust: { id: "rust", label: "Rust" },
  sh: { id: "bash", label: "Shell" },
  shell: { id: "bash", label: "Shell" },
  sql: { id: "sql", label: "SQL" },
  svelte: { id: "xml", label: "Svelte" },
  swift: { id: "swift", label: "Swift" },
  text: { id: "plaintext", label: "Text" },
  ts: { id: "typescript", label: "TypeScript" },
  tsx: { id: "typescript", label: "TSX" },
  typescript: { id: "typescript", label: "TypeScript" },
  vue: { id: "xml", label: "Vue" },
  xml: { id: "xml", label: "XML" },
  yaml: { id: "yaml", label: "YAML" },
  yml: { id: "yaml", label: "YAML" },
  zsh: { id: "bash", label: "Zsh" },
};

/** 需要避开 LLM Markdown 修复的 inline code / math 片段。 */
const PROTECTED_INLINE_PATTERN =
  /(`+)([\s\S]*?)\1|\$\$[\s\S]*?\$\$|\$[^$\n]+?\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]/g;

const CITATION_MARKER_PREFIX = "[[citation:";
const CITATION_MARKER_PATTERN = /^\[\[citation:([1-9]\d*)\]\]/;

/** 允许的链接协议白名单，防止 javascript: / data: 等危险协议注入 */
const SAFE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:"]);

/** MarkdownIt 实例缓存，避免重复创建 */
let markdownRenderer: MarkdownIt | null = null;

registerAdditionalHighlightLanguages();

/** 将聊天消息中的 Markdown 文本渲染为安全的 HTML */
export function renderChatMarkdown(
  content: string,
  options: RenderChatMarkdownOptions,
): string {
  const renderer = getMarkdownRenderer();
  const citationIds = new Set(options.citationIds ?? []);
  const renderContent = options.streaming
    ? hideTrailingCitationFragment(content)
    : content;
  // 仅保留当前 UI 已允许发布的 citation marker。
  const normalizedContent = options.stripUnknownCitationMarkers
    ? stripUnknownCitationMarkers(renderContent, citationIds)
    : renderContent;
  const html = renderer.render(normalizedContent, {
    citationAriaLabel: options.citationAriaLabel,
    citationIds,
    citationLabel: options.citationLabel,
    copyCodeLabel: options.copyCodeLabel,
  } satisfies ChatMarkdownEnv);

  // DOMPurify 二次过滤：保留 KaTeX 的 HTML/MathML，同时阻止主动内容与外部媒体。
  return DOMPurify.sanitize(html, {
    ADD_ATTR: [
      "aria-label",
      "data-chat-citation-id",
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

/** 隐藏未进入当前展示集合的 marker，不修改原始 message content。 */
function stripUnknownCitationMarkers(
  content: string,
  citationIds: ReadonlySet<number>,
): string {
  return content.replace(/\[\[citation:([1-9]\d*)\]\]/g, (marker, rawId) =>
    citationIds.has(Number(rawId)) ? marker : "",
  );
}

/** 获取缓存的 MarkdownIt 实例，首次调用时初始化并配置插件 */
function getMarkdownRenderer(): MarkdownIt {
  if (markdownRenderer) {
    return markdownRenderer;
  }

  // 关闭 html 标签支持，从源头阻止 HTML 注入。
  const renderer = new MarkdownIt({
    breaks: false,
    html: false,
    linkify: true,
    typographer: false,
  });

  renderer.use(markdownItKatex, {
    delimiters: "all",
    logger: () => "ignore",
    mathFence: true,
    throwOnError: false,
    trust: false,
  });

  configureLlmMarkdownNormalization(renderer);
  configureCitations(renderer);
  configureLinks(renderer);
  configureImages(renderer);
  configureCodeBlocks(renderer);

  markdownRenderer = renderer;
  return renderer;
}

/**
 * 只将 snapshot 中真实存在的 [[citation:N]] 转换为交互 token。
 * code、math 与 link 内部由 markdown-it 自身的 token 边界隔离。
 *
 * 自定义的 markdown-it parse/render 规则；
 * parse 部分规则:
 *   识别 [[citation:xxx]] 类型文本，并解析为
 *   [
 *     ...  // 先前解析的内容
 *     {
 *        { type: 'chat_citation', tag: 'button', meta: { citationId: 42 } },
 *     }
 *     ...
 *   ]
 *   的中间态
 *
 * render 部分规则：
 *  识别 type 为 'chat_citation' 的 token，
 *  并最终渲染为 <button>xxx</button> 的 DOM
 */
function configureCitations(renderer: MarkdownIt) {
  // 在 markdown-it 处理 []() link 规则之前解析
  renderer.inline.ruler.before("link", "chat_citation", (state, silent) => {
    // markdown-it 运行时提供 linkLevel，但当前 @types/markdown-it 未声明该字段。
    const linkLevel = (state as typeof state & { linkLevel: number }).linkLevel;
    if (linkLevel > 0) {
      // 跳过嵌套在 [] 中的 [] token 解析
      return false;
    }

    const match = CITATION_MARKER_PATTERN.exec(state.src.slice(state.pos));
    if (!match) {
      return false;
    }

    const citationId = Number(match[1]);
    const env = state.env as ChatMarkdownEnv;
    if (!env.citationIds?.has(citationId)) {
      return false;
    }

    if (!silent) {
      const token = state.push("chat_citation", "button", 0);
      token.meta = { citationId } satisfies CitationTokenMeta;
    }

    // 推进 parse 进度
    state.pos += match[0].length;
    return true;
  });

  // 增加 citation button
  renderer.renderer.rules.chat_citation = (tokens, idx, _options, env) => {
    const { citationId } = tokens[idx].meta as CitationTokenMeta;
    const chatEnv = env as ChatMarkdownEnv;
    const ariaLabel =
      chatEnv.citationAriaLabel?.(citationId) ?? `Open citation ${citationId}`;
    const visibleLabel = chatEnv.citationLabel?.(citationId) ?? citationId;

    return `<button type="button" class="chat-md-citation" data-chat-citation-id="${citationId}" aria-label="${escapeAttribute(ariaLabel)}"><span aria-hidden="true">${escapeHtml(String(visibleLabel))}</span></button>`;
  };
}

/**
 * SSE 可能把 marker 拆到多个 delta；仅在显示层隐藏末尾可继续成为 marker 的片段。
 * 原始 message content 不会被修改。
 */
function hideTrailingCitationFragment(content: string): string {
  const markerStart = content.lastIndexOf(CITATION_MARKER_PREFIX);
  if (markerStart >= 0) {
    const tail = content.slice(markerStart);
    /**
     * 匹配 [[citation:123]] 是否生成完整
     * [[citation:, [[citation:1, [[citation:123 会被匹配成功
     */
    if (/^\[\[citation:\d*\]?$/.test(tail)) {
      return content.slice(0, markerStart);
    }
  }

  /**
   * 处理不完整的 [[citation 前缀
   * 匹配 [[citation, [[citatio, [[citati ... [ 前缀
   * 删除整个尾部片段
   */
  const maxPartialLength = Math.min(
    content.length,
    CITATION_MARKER_PREFIX.length - 1,
  );
  for (let length = maxPartialLength; length > 0; length -= 1) {
    const suffix = content.slice(-length);
    if (CITATION_MARKER_PREFIX.startsWith(suffix)) {
      return content.slice(0, -length);
    }
  }

  return content;
}

/**
 * 修复少量高频 LLM Markdown 瑕疵。
 * 只处理 block parser 已识别出的 inline token，避免影响 fenced code block。
 */
function configureLlmMarkdownNormalization(renderer: MarkdownIt) {
  renderer.core.ruler.before("inline", "normalize_llm_markdown", (state) => {
    for (const token of state.tokens) {
      if (token.type === "inline") {
        token.content = normalizeLooseStrongMarkers(token.content);
      }
    }
  });
}

/** 修复 `** text **`，并绕开 inline code 与数学公式。 */
function normalizeLooseStrongMarkers(content: string): string {
  let result = "";
  let lastIndex = 0;

  for (const match of content.matchAll(PROTECTED_INLINE_PATTERN)) {
    const matchIndex = match.index ?? 0;
    result += normalizeStrongSegment(content.slice(lastIndex, matchIndex));
    result += match[0];
    lastIndex = matchIndex + match[0].length;
  }

  return result + normalizeStrongSegment(content.slice(lastIndex));
}

function normalizeStrongSegment(content: string): string {
  return content.replace(
    /\*\*[ \t]+([^*\n]+?)[ \t]+\*\*/g,
    (_match, inner: string) => `**${inner.trim()}**`,
  );
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

    if (!href || !isSafeLinkHref(href)) {
      // 覆写不安全 link
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
    const language = resolveCodeLanguage(token.info);
    const highlighted = highlightCode(token.content, language.id);
    const copyCodeLabel =
      (env as ChatMarkdownEnv | null)?.copyCodeLabel ?? "Copy";

    return [
      `<figure class="chat-md-code-block" data-chat-code-lang="${escapeAttribute(language.label)}">`,
      '<figcaption class="chat-md-code-head">',
      `<span class="chat-md-code-lang">${escapeHtml(language.label)}</span>`,
      `<button type="button" class="chat-md-code-copy" data-chat-code-copy aria-label="${escapeAttribute(copyCodeLabel)}">${escapeHtml(copyCodeLabel)}</button>`,
      "</figcaption>",
      '<pre class="console-scrollbar"><code class="hljs">',
      highlighted,
      "</code></pre>",
      "</figure>\n",
    ].join("");
  };
}

/** highlight.js common 已覆盖主流语言，这里只补充常见但未内置的语言。 */
function registerAdditionalHighlightLanguages() {
  hljs.registerLanguage("dart", dart);
  hljs.registerLanguage("dockerfile", dockerfile);
  hljs.registerLanguage("http", http);
  hljs.registerLanguage("nginx", nginx);
  hljs.registerLanguage("powershell", powershell);
  hljs.registerLanguage("protobuf", protobuf);
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

/** 解析 fenced code info，并兼顾 parser id 与用户可读标签。 */
function resolveCodeLanguage(info: string): CodeLanguage {
  const rawLanguage = info.trim().split(/\s+/)[0] ?? "";
  const safeLanguage = rawLanguage.toLowerCase().replace(/[^a-z0-9_+-]/g, "");

  if (!safeLanguage) {
    return { id: "plaintext", label: "Text" };
  }

  const aliased = LANGUAGE_ALIASES[safeLanguage];
  if (aliased) {
    return aliased;
  }

  if (hljs.getLanguage(safeLanguage)) {
    return { id: safeLanguage, label: rawLanguage || safeLanguage };
  }

  return { id: "plaintext", label: rawLanguage || "Text" };
}

/** 检查链接是否安全：允许相对路径、锚点和白名单协议 */
function isSafeLinkHref(href: string): boolean {
  const trimmedHref = href.trim();

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

function escapeAttribute(value: string): string {
  return escapeHtml(value);
}
