<script setup lang="ts">
import { computed, ref } from "vue";
import { FileText, Globe2, Plus } from "@lucide/vue";

import type {
  CreateSourceInput,
  WebCrawlConfigInput,
} from "@/console/services/source-workspace";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/shared/components/ui/sheet";
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";

type SourceCreateType = "local_file" | "web_crawl";
type CrawlEntryType = WebCrawlConfigInput["entry_type"];

defineProps<{
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "createSource", input: CreateSourceInput): void;
}>();

// 响应式变量
const open = ref(false);
const sourceType = ref<SourceCreateType>("local_file");
const sourceName = ref("");
const isPublic = ref(true);

// web crawl 爬取策略
const entryType = ref<CrawlEntryType>("url_list");
const urlsText = ref("");
const siteRootUrl = ref("");
const sitemapUrl = ref("");

// crawl config
const allowedDomainsText = ref("");
const includePathsText = ref("");
const excludePathsText = ref("");
const contentSelectorsText = ref("main, article");
const excludeSelectorsText = ref("nav, footer, .toc");
const maxPages = ref(20);
const maxDepth = ref(3);
const requestDelayMs = ref(5000);
const respectRobotsTxt = ref(true);
const localError = ref<string | null>(null);

const isWebCrawl = computed(() => sourceType.value === "web_crawl");

function handleCreate(): void {
  const name = sourceName.value.trim();

  if (!name) {
    localError.value = "Source name is required.";
    return;
  }

  localError.value = null;
  // 触发创建 source 信号
  emit("createSource", {
    sourceName: name,
    sourceType: sourceType.value,
    syncInterval: null,
    isPublic: isPublic.value,
    webCrawlConfig: isWebCrawl.value ? buildWebCrawlConfig() : null,
  });
  // 自动关闭 sheet
  open.value = false;
  resetForm();
}

// 重置 Form 默认字段；
// TODO: 后续移除这里的默认字段，改为 placeholder
function resetForm(): void {
  sourceType.value = "local_file";
  sourceName.value = "";
  isPublic.value = true;
  entryType.value = "site_root";
  siteRootUrl.value = "";
  urlsText.value = "";
  sitemapUrl.value = "";
  allowedDomainsText.value = "";
  includePathsText.value = "";
  excludePathsText.value = "";
  contentSelectorsText.value = "main, article";
  excludeSelectorsText.value = "nav, footer, .toc";
  maxPages.value = 20;
  maxDepth.value = 3;
  requestDelayMs.value = 5000;
  respectRobotsTxt.value = true;
  localError.value = null;
}

/**
 * form 中传递的 web crawl config 调整为适配后端需要的格式
 */
function buildWebCrawlConfig(): WebCrawlConfigInput {
  return {
    entry_type: entryType.value,
    urls: entryType.value === "url_list" ? splitList(urlsText.value) : null,
    sitemap_url:
      entryType.value === "sitemap_url"
        ? normalizeOptionalText(sitemapUrl.value)
        : null,
    site_root_url:
      entryType.value === "site_root"
        ? normalizeOptionalText(siteRootUrl.value)
        : null,
    allowed_domains: splitList(allowedDomainsText.value),
    include_paths: splitList(includePathsText.value),
    exclude_paths: splitList(excludePathsText.value),
    content_selectors: splitList(contentSelectorsText.value),
    exclude_selectors: splitList(excludeSelectorsText.value),
    extraction_rules: [],
    max_pages: normalizePositiveNumber(maxPages.value, 20),
    max_depth: normalizePositiveNumber(maxDepth.value, 3),
    request_delay_ms: normalizePositiveNumber(requestDelayMs.value, 5000),
    respect_robots_txt: respectRobotsTxt.value,
  };
}

function splitList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeOptionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizePositiveNumber(value: number, fallback: number): number {
  const normalized = Number(value);
  return Number.isFinite(normalized) && normalized > 0 ? normalized : fallback;
}
</script>

<template>
  <!-- 创建知识库数据源的侧边栏抽屉 -->
  <Sheet v-model:open="open">
    <SheetTrigger as-child>
      <Button type="button" aria-label="Create source">
        <Plus class="size-4" />
        Create source
      </Button>
    </SheetTrigger>
    <SheetContent
      class="w-[min(520px,100vw)] gap-0 border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <!-- 抽屉头部 -->
      <SheetHeader class="border-b border-(--line-soft) px-4.5 py-4">
        <SheetTitle class="text-[15px]">Create source</SheetTitle>
      </SheetHeader>

      <!-- 表单内容滚动区域 -->
      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-4 overflow-auto px-4.5 py-4"
      >
        <!-- 数据源类型选择 -->
        <section class="grid gap-2">
          <Label>Source type</Label>
          <div class="grid grid-cols-2 gap-2 max-[560px]:grid-cols-1">
            <!-- 本地文件类型 -->
            <button
              :class="[
                'grid min-h-24 content-start gap-2 rounded-(--console-radius-lg) border p-3 text-left transition',
                sourceType === 'local_file'
                  ? 'border-primary/35 bg-primary/10'
                  : 'border-(--line) bg-(--surface-panel-soft)',
              ]"
              type="button"
              aria-label="Local file source type"
              @click="sourceType = 'local_file'"
            >
              <span
                class="text-primary grid size-8 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <FileText class="size-4" />
              </span>
              <strong class="text-[13px] font-semibold text-(--text-strong)">
                Local file
              </strong>
              <span class="text-xs leading-5 text-(--text-faint)">
                Upload files from the items page.
              </span>
            </button>

            <!-- 网页爬取类型 -->
            <button
              :class="[
                'grid min-h-24 content-start gap-2 rounded-(--console-radius-lg) border p-3 text-left transition',
                sourceType === 'web_crawl'
                  ? 'border-primary/35 bg-primary/10'
                  : 'border-(--line) bg-(--surface-panel-soft)',
              ]"
              type="button"
              aria-label="Web crawl source type"
              @click="sourceType = 'web_crawl'"
            >
              <span
                class="text-primary grid size-8 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <Globe2 class="size-4" />
              </span>
              <strong class="text-[13px] font-semibold text-(--text-strong)">
                Web crawl
              </strong>
              <span class="text-xs leading-5 text-(--text-faint)">
                Configure crawl rules before sync.
              </span>
            </button>
          </div>
        </section>

        <!-- 数据源名称 -->
        <section class="grid gap-2">
          <Label for="source-name">Name</Label>
          <Input
            id="source-name"
            v-model="sourceName"
            placeholder="Product docs PDF"
          />
        </section>

        <!-- 可见性/启用状态 -->
        <section class="grid gap-2">
          <Label>Visibility</Label>
          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <strong class="block text-[13px] text-(--text-strong)">
                Public for visitor RAG
              </strong>
              <span class="mt-1 block text-xs leading-5 text-(--text-faint)">
                Keep off while importing or reviewing source items.
              </span>
            </div>
            <Switch
              v-model:checked="isPublic"
              aria-label="Public for visitor RAG"
            />
          </div>
          <p class="text-xs leading-5 text-(--text-faint)">
            Visitor RAG still requires at least one completed source item.
          </p>
        </section>

        <!-- 网页爬取配置面板（仅在选择 Web crawl 时展示） -->
        <section v-if="isWebCrawl" class="console-panel grid gap-4 p-4">
          <div>
            <h2 class="console-panel-title">Web crawl config</h2>
            <p class="console-panel-note">
              Crawled pages are materialized from the items workspace.
            </p>
          </div>

          <!-- 入口类型 -->
          <div class="grid gap-2">
            <Label>Entry type</Label>
            <Select v-model="entryType">
              <SelectTrigger class="w-full bg-(--surface-base)">
                <SelectValue placeholder="Entry type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="site_root">site_root</SelectItem>
                <SelectItem value="url_list">url_list</SelectItem>
                <SelectItem value="sitemap_url">sitemap_url</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- 起始 URL -->
          <div v-if="entryType === 'site_root'" class="grid gap-2">
            <Label for="seed-url">Site root URL</Label>
            <Input
              id="seed-url"
              v-model="siteRootUrl"
              placeholder="https://docs.example.com/"
            />
          </div>

          <div v-else-if="entryType === 'sitemap_url'" class="grid gap-2">
            <Label for="sitemap-url">Sitemap URL</Label>
            <Input
              id="sitemap-url"
              v-model="sitemapUrl"
              placeholder="https://docs.example.com/sitemap.xml"
            />
          </div>

          <div v-else class="grid gap-2">
            <Label for="url-list">URLs</Label>
            <Textarea
              id="url-list"
              v-model="urlsText"
              class="min-h-24 bg-(--surface-base)"
              placeholder="https://example.com/docs/intro&#10;https://example.com/docs/install"
            />
          </div>

          <!-- 限制参数 -->
          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="max-pages">Max pages</Label>
              <Input id="max-pages" v-model="maxPages" type="number" />
            </div>
            <div class="grid gap-2">
              <Label for="max-depth">Max depth</Label>
              <Input id="max-depth" v-model="maxDepth" type="number" />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="allowed-domains">Allowed domains</Label>
            <Input
              id="allowed-domains"
              v-model="allowedDomainsText"
              placeholder="docs.example.com, example.com"
            />
          </div>

          <!-- 提取选择器 -->
          <div class="grid gap-2">
            <Label for="content-selectors">Content selectors</Label>
            <Input
              id="content-selectors"
              v-model="contentSelectorsText"
              placeholder="main, article, .docs-content"
            />
          </div>

          <!-- 排除选择器 -->
          <div class="grid gap-2">
            <Label for="exclude-selectors">Exclude selectors</Label>
            <Input
              id="exclude-selectors"
              v-model="excludeSelectorsText"
              placeholder="nav, footer, .toc"
            />
          </div>

          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="include-paths">Include paths</Label>
              <Input
                id="include-paths"
                v-model="includePathsText"
                placeholder="/docs/, /api/"
              />
            </div>
            <div class="grid gap-2">
              <Label for="exclude-paths">Exclude paths</Label>
              <Input
                id="exclude-paths"
                v-model="excludePathsText"
                placeholder="/blog/, /drafts/"
              />
            </div>
          </div>

          <div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
            <div class="grid gap-2">
              <Label for="request-delay">Request delay ms</Label>
              <Input
                id="request-delay"
                v-model="requestDelayMs"
                type="number"
              />
            </div>
            <div class="pt-6">
              <Switch
                v-model:checked="respectRobotsTxt"
                aria-label="Respect robots txt"
              />
            </div>
          </div>
        </section>

        <p v-if="localError" class="text-sm text-red-100">
          {{ localError }}
        </p>
      </div>

      <!-- 底部操作按钮 -->
      <SheetFooter
        class="mt-0 flex-row justify-end border-t border-(--line-soft) p-4.5"
      >
        <Button
          type="button"
          aria-label="Cancel create source"
          variant="outline"
          @click="open = false"
        >
          Cancel
        </Button>
        <Button
          type="button"
          aria-label="Confirm create source"
          :disabled="isMutating"
          @click="handleCreate"
        >
          Create
        </Button>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
