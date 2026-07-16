import { ref } from "vue";
import type {
  WebCrawlConfigInput,
  WebCrawlConfigOutput,
} from "@/console/services/source-workspace";

type CrawlEntryType = WebCrawlConfigInput["entry_type"];

interface WebCrawlConfigFormDefaults {
  entryType?: CrawlEntryType;
  siteRootUrl?: string;
  urlsText?: string;
  sitemapUrl?: string;
  allowedDomainsText?: string;
  includePathsText?: string;
  excludePathsText?: string;
  contentSelectorsText?: string;
  excludeSelectorsText?: string;
  maxPages?: number;
  maxDepth?: number;
  requestDelayMs?: number;
  respectRobotsTxt?: boolean;
}

interface BuildWebCrawlConfigOptions {
  extractionRules?: WebCrawlConfigInput["extraction_rules"];
}

// 表单字段出厂默认值
const baseDefaults = {
  allowedDomainsText: "",
  contentSelectorsText: "",
  entryType: "url_list" as CrawlEntryType,
  excludePathsText: "",
  excludeSelectorsText: "",
  includePathsText: "",
  maxDepth: 3,
  maxPages: 20,
  requestDelayMs: 5000,
  respectRobotsTxt: true,
  sitemapUrl: "",
  siteRootUrl: "",
  urlsText: "",
};

/**
 * 可复用的 web crawl config 相关逻辑
 */
export function useWebCrawlConfigForm(
  initialDefaults: WebCrawlConfigFormDefaults = {},
) {
  const defaults = { ...baseDefaults, ...initialDefaults };

  const entryType = ref<CrawlEntryType>(defaults.entryType);
  const siteRootUrl = ref(defaults.siteRootUrl);
  const urlsText = ref(defaults.urlsText);
  const sitemapUrl = ref(defaults.sitemapUrl);
  const allowedDomainsText = ref(defaults.allowedDomainsText);
  const includePathsText = ref(defaults.includePathsText);
  const excludePathsText = ref(defaults.excludePathsText);
  const contentSelectorsText = ref(defaults.contentSelectorsText);
  const excludeSelectorsText = ref(defaults.excludeSelectorsText);
  const maxPages = ref(defaults.maxPages);
  const maxDepth = ref(defaults.maxDepth);
  const requestDelayMs = ref(defaults.requestDelayMs);
  const respectRobotsTxt = ref(defaults.respectRobotsTxt);

  // 重置为默认值（常用于创建表单的清空操作）
  function resetToDefaults(overrides: WebCrawlConfigFormDefaults = {}): void {
    applyDefaults({ ...defaults, ...overrides });
  }

  // 从已有后端配置回填表单（常用于 settings 编辑）
  function resetFromConfig(
    config: WebCrawlConfigOutput | null | undefined,
    fallbackDefaults: WebCrawlConfigFormDefaults = {},
  ): void {
    const fallback = { ...defaults, ...fallbackDefaults };

    entryType.value = config?.entry_type ?? fallback.entryType;
    siteRootUrl.value = config?.site_root_url ?? fallback.siteRootUrl;
    urlsText.value = config?.urls ? joinList(config.urls) : fallback.urlsText;
    sitemapUrl.value = config?.sitemap_url ?? fallback.sitemapUrl;
    allowedDomainsText.value = config?.allowed_domains
      ? joinList(config.allowed_domains)
      : fallback.allowedDomainsText;
    includePathsText.value = config?.include_paths
      ? joinList(config.include_paths)
      : fallback.includePathsText;
    excludePathsText.value = config?.exclude_paths
      ? joinList(config.exclude_paths)
      : fallback.excludePathsText;
    contentSelectorsText.value = config?.content_selectors
      ? joinList(config.content_selectors)
      : fallback.contentSelectorsText;
    excludeSelectorsText.value = config?.exclude_selectors
      ? joinList(config.exclude_selectors)
      : fallback.excludeSelectorsText;
    maxPages.value = config?.max_pages ?? fallback.maxPages;
    maxDepth.value = config?.max_depth ?? fallback.maxDepth;
    requestDelayMs.value = config?.request_delay_ms ?? fallback.requestDelayMs;
    respectRobotsTxt.value =
      config?.respect_robots_txt ?? fallback.respectRobotsTxt;
  }

  // 将表单字段组装为后端 API 所需的 WebCrawlConfigInput
  function buildWebCrawlConfig(
    options: BuildWebCrawlConfigOptions = {},
  ): WebCrawlConfigInput {
    return {
      allowed_domains: splitList(allowedDomainsText.value),
      content_selectors: splitList(contentSelectorsText.value),
      entry_type: entryType.value,
      exclude_paths: splitList(excludePathsText.value),
      exclude_selectors: splitList(excludeSelectorsText.value),
      extraction_rules: options.extractionRules ?? [],
      include_paths: splitList(includePathsText.value),
      max_depth: normalizePositiveNumber(maxDepth.value, 3),
      max_pages: normalizePositiveNumber(maxPages.value, 20),
      request_delay_ms: normalizePositiveNumber(requestDelayMs.value, 5000),
      respect_robots_txt: respectRobotsTxt.value,
      sitemap_url:
        entryType.value === "sitemap_url"
          ? normalizeOptionalText(sitemapUrl.value)
          : null,
      site_root_url:
        entryType.value === "site_root"
          ? normalizeOptionalText(siteRootUrl.value)
          : null,
      urls: entryType.value === "url_list" ? splitList(urlsText.value) : null,
    };
  }

  function applyDefaults(nextDefaults: Required<WebCrawlConfigFormDefaults>) {
    entryType.value = nextDefaults.entryType;
    siteRootUrl.value = nextDefaults.siteRootUrl;
    urlsText.value = nextDefaults.urlsText;
    sitemapUrl.value = nextDefaults.sitemapUrl;
    allowedDomainsText.value = nextDefaults.allowedDomainsText;
    includePathsText.value = nextDefaults.includePathsText;
    excludePathsText.value = nextDefaults.excludePathsText;
    contentSelectorsText.value = nextDefaults.contentSelectorsText;
    excludeSelectorsText.value = nextDefaults.excludeSelectorsText;
    maxPages.value = nextDefaults.maxPages;
    maxDepth.value = nextDefaults.maxDepth;
    requestDelayMs.value = nextDefaults.requestDelayMs;
    respectRobotsTxt.value = nextDefaults.respectRobotsTxt;
  }

  return {
    allowedDomainsText,
    buildWebCrawlConfig,
    contentSelectorsText,
    entryType,
    excludePathsText,
    excludeSelectorsText,
    includePathsText,
    maxDepth,
    maxPages,
    requestDelayMs,
    resetFromConfig,
    resetToDefaults,
    respectRobotsTxt,
    sitemapUrl,
    siteRootUrl,
    urlsText,
  };
}

// 按换行或逗号拆分为字符串数组，用于多值文本字段 → API 数组
function splitList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

// API 数组 → 逗号分隔文本，用于表单回填
function joinList(value: string[]): string {
  return value.join(", ");
}

function normalizeOptionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizePositiveNumber(value: number, fallback: number): number {
  const normalized = Number(value);
  return Number.isFinite(normalized) && normalized > 0 ? normalized : fallback;
}
