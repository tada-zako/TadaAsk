<script setup lang="ts">
import { computed, ref } from "vue";
import { FileText, Globe2, Plus } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import { useWebCrawlConfigForm } from "./useWebCrawlConfigForm";
import type { CreateSourceInput } from "@/console/services/source-workspace";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
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

defineProps<{
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "createSource", input: CreateSourceInput): void;
}>();

const { t } = useI18n();

// 响应式变量
const open = ref(false);
const sourceType = ref<SourceCreateType>("local_file");
const sourceName = ref("");
const isPublic = ref(true);

// web crawl 表单字段、构建与重置逻辑抽离至 composable
const {
  allowedDomainsText,
  buildWebCrawlConfig,
  contentSelectorsText,
  excludePathsText,
  excludeSelectorsText,
  includePathsText,
  maxDepth,
  maxPages,
  requestDelayMs,
  resetToDefaults: resetWebCrawlConfigForm,
  urlsText,
} = useWebCrawlConfigForm({
  contentSelectorsText: "main, article",
  entryType: "url_list",
  excludeSelectorsText: "nav, footer, .toc",
});
const localError = ref<string | null>(null);

const isWebCrawl = computed(() => sourceType.value === "web_crawl");

/** source create */
function handleCreate(): void {
  const name = sourceName.value.trim();

  if (!name) {
    localError.value = t("sources.common.nameRequired");
    return;
  }

  localError.value = null;
  // 触发创建 source 信号; source view 调用真正的 source create API
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
  resetWebCrawlConfigForm({ entryType: "url_list" });
  localError.value = null;
}
</script>

<template>
  <!-- 创建知识库数据源的侧边栏抽屉 -->
  <Sheet v-model:open="open">
    <SheetTrigger as-child>
      <Button type="button" :aria-label="t('sources.create.openAria')">
        <Plus class="size-4" />
        {{ t("sources.create.title") }}
      </Button>
    </SheetTrigger>
    <SheetContent
      class="!right-0 !w-[min(520px,100dvw)] !max-w-[100dvw] min-w-0 gap-0 overflow-x-hidden border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <!-- 抽屉头部 -->
      <SheetHeader class="border-b border-(--line-soft) px-4.5 py-4">
        <SheetTitle class="text-[15px]">
          {{ t("sources.create.title") }}
        </SheetTitle>
      </SheetHeader>

      <!-- 表单内容滚动区域 -->
      <div
        class="console-scrollbar grid min-h-0 min-w-0 flex-1 content-start gap-4 overflow-x-hidden overflow-y-auto px-4.5 py-4"
      >
        <!-- 数据源类型选择 -->
        <section class="grid gap-2">
          <Label>{{ t("sources.common.fields.sourceType") }}</Label>
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
              :aria-label="t('sources.create.localFileAria')"
              @click="sourceType = 'local_file'"
            >
              <span
                class="text-primary grid size-8 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <FileText class="size-4" />
              </span>
              <strong class="text-[13px] font-semibold text-(--text-strong)">
                {{ t("sources.common.localFile") }}
              </strong>
              <span class="text-xs leading-5 text-(--text-faint)">
                {{ t("sources.create.localFileHelp") }}
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
              :aria-label="t('sources.create.webCrawlAria')"
              @click="sourceType = 'web_crawl'"
            >
              <span
                class="text-primary grid size-8 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <Globe2 class="size-4" />
              </span>
              <strong class="text-[13px] font-semibold text-(--text-strong)">
                {{ t("sources.common.webCrawl") }}
              </strong>
              <span class="text-xs leading-5 text-(--text-faint)">
                {{ t("sources.create.webCrawlHelp") }}
              </span>
            </button>
          </div>
        </section>

        <!-- 数据源名称 -->
        <section class="grid gap-2">
          <Label for="source-name">
            {{ t("sources.common.fields.name") }}
          </Label>
          <Input
            id="source-name"
            v-model="sourceName"
            :placeholder="t('sources.create.namePlaceholder')"
          />
        </section>

        <!-- 可见性/启用状态 -->
        <section class="grid gap-2">
          <Label>{{ t("sources.common.fields.visibility") }}</Label>
          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <strong class="block text-[13px] text-(--text-strong)">
                {{ t("sources.common.fields.publicForVisitorRag") }}
              </strong>
              <span class="mt-1 block text-xs leading-5 text-(--text-faint)">
                {{ t("sources.create.publicHelp") }}
              </span>
            </div>
            <Switch
              :model-value="isPublic"
              :aria-label="t('sources.common.fields.publicForVisitorRag')"
              @update:model-value="isPublic = Boolean($event)"
            />
          </div>
          <p class="text-xs leading-5 text-(--text-faint)">
            {{ t("sources.create.visitorReadyHelp") }}
          </p>
        </section>

        <!-- 网页爬取配置面板（仅在选择 Web crawl 时展示） -->
        <section v-if="isWebCrawl" class="console-panel grid gap-4 p-4">
          <div>
            <h2 class="console-panel-title">
              {{ t("sources.common.fields.webCrawlConfig") }}
            </h2>
            <p class="console-panel-note">
              {{ t("sources.create.crawlHelp") }}
            </p>
          </div>

          <!-- 入口类型 -->
          <div class="grid gap-2">
            <!-- <Label>{{ t("sources.common.fields.entryType") }}</Label>
            <Select v-model="entryType">
              <SelectTrigger class="w-full bg-(--surface-base)">
                <SelectValue
                  :placeholder="t('sources.common.fields.entryType')"
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="site_root">site_root</SelectItem>
                <SelectItem value="url_list">url_list</SelectItem>
                <SelectItem value="sitemap_url">sitemap_url</SelectItem>
              </SelectContent>
            </Select>
          </div> -->

            <!-- 起始 URL -->
            <!-- <div v-if="entryType === 'site_root'" class="grid gap-2">
            <Label for="seed-url">
              {{ t("sources.common.fields.rootUrl") }}
            </Label>
            <Input
              id="seed-url"
              v-model="siteRootUrl"
              placeholder="https://docs.example.com/"
            />
          </div>

          <div v-else-if="entryType === 'sitemap_url'" class="grid gap-2">
            <Label for="sitemap-url">
              {{ t("sources.common.fields.sitemapUrl") }}
            </Label>
            <Input
              id="sitemap-url"
              v-model="sitemapUrl"
              placeholder="https://docs.example.com/sitemap.xml"
            />
          </div> -->

            <!-- <div v-else class="grid gap-2"> -->
            <!-- MVP 仅开放明确 URL 列表抓取。 -->
            <Label for="url-list">{{ t("sources.common.fields.urls") }}</Label>
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
              <Label for="max-pages">
                {{ t("sources.common.fields.maxPages") }}
              </Label>
              <Input id="max-pages" v-model="maxPages" type="number" />
            </div>
            <div class="grid gap-2">
              <Label for="max-depth">
                {{ t("sources.common.fields.maxDepth") }}
              </Label>
              <Input id="max-depth" v-model="maxDepth" type="number" />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="allowed-domains">
              {{ t("sources.common.fields.allowedDomains") }}
            </Label>
            <Input
              id="allowed-domains"
              v-model="allowedDomainsText"
              placeholder="docs.example.com, example.com"
            />
          </div>

          <!-- 提取选择器 -->
          <div class="grid gap-2">
            <Label for="content-selectors">
              {{ t("sources.common.fields.contentSelectors") }}
            </Label>
            <Input
              id="content-selectors"
              v-model="contentSelectorsText"
              placeholder="main, article, .docs-content"
            />
          </div>

          <!-- 排除选择器 -->
          <div class="grid gap-2">
            <Label for="exclude-selectors">
              {{ t("sources.common.fields.excludeSelectors") }}
            </Label>
            <Input
              id="exclude-selectors"
              v-model="excludeSelectorsText"
              placeholder="nav, footer, .toc"
            />
          </div>

          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="include-paths">
                {{ t("sources.common.fields.includePaths") }}
              </Label>
              <Input
                id="include-paths"
                v-model="includePathsText"
                placeholder="/docs/, /api/"
              />
            </div>
            <div class="grid gap-2">
              <Label for="exclude-paths">
                {{ t("sources.common.fields.excludePaths") }}
              </Label>
              <Input
                id="exclude-paths"
                v-model="excludePathsText"
                placeholder="/blog/, /drafts/"
              />
            </div>
          </div>

          <!-- <div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3"> -->
          <div class="grid gap-2">
            <Label for="request-delay">
              {{ t("sources.common.fields.requestDelayMs") }}
            </Label>
            <Input id="request-delay" v-model="requestDelayMs" type="number" />
          </div>
          <!-- MVP 阶段不暴露 robots.txt 可选 -->
          <!-- <div class="pt-6">
              <Switch
                :model-value="respectRobotsTxt"
                :aria-label="t('sources.common.respectRobotsAria')"
                @update:model-value="respectRobotsTxt = Boolean($event)"
              />
            </div> -->
          <!-- </div> -->
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
          :aria-label="t('sources.create.cancelAria')"
          variant="outline"
          @click="open = false"
        >
          {{ t("sources.common.actions.cancel") }}
        </Button>
        <Button
          type="button"
          :aria-label="t('sources.create.confirmAria')"
          :disabled="isMutating"
          @click="handleCreate"
        >
          {{ t("sources.common.actions.create") }}
        </Button>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
