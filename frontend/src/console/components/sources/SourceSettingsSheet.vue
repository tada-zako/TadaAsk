<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { FileText, Globe2, Settings, Trash2 } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import { useWebCrawlConfigForm } from "./useWebCrawlConfigForm";
import { toSourceRow } from "@/console/services/source-workspace";
import type { SourceRead, SourceUpdatePayload } from "@/console/api/sources";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Badge } from "@/shared/components/ui/badge";
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

const props = defineProps<{
  source: SourceRead;
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "updateSource", input: SourceUpdatePayload): void;
  (event: "deleteSource"): void;
}>();

const { t } = useI18n();

// 响应式变量
const open = ref(false);
const sourceName = ref("");
const isPublic = ref(false);

// web crawl 表单字段、构建与重置逻辑抽离至 composable
const {
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
  resetFromConfig: resetWebCrawlConfigForm,
  sitemapUrl,
  siteRootUrl,
  urlsText,
} = useWebCrawlConfigForm();
const localError = ref<string | null>(null);

const sourceRow = computed(() => toSourceRow(props.source));
const isWebCrawl = computed(() => props.source.sourceType === "web_crawl");
const isLegacyCrawlEntry = computed(
  () => isWebCrawl.value && entryType.value !== "url_list",
);
const legacyEntryValue = computed(() =>
  entryType.value === "site_root" ? siteRootUrl.value : sitemapUrl.value,
);
const legacyEntryLabel = computed(() =>
  entryType.value === "site_root"
    ? t("sources.common.fields.rootUrl")
    : t("sources.common.fields.sitemapUrl"),
);
const sheetTitle = computed(() =>
  isWebCrawl.value
    ? t("sources.settings.webTitle")
    : t("sources.settings.localTitle"),
);

const visibilityHelp = computed(() =>
  isWebCrawl.value
    ? t("sources.settings.webVisibilityHelp")
    : t("sources.settings.localVisibilityHelp"),
);

watch(
  () => props.source,
  () => resetForm(),
  { immediate: true },
);

watch(open, (nextOpen) => {
  if (nextOpen) {
    resetForm();
  }
});

// 更新 source settings 触发函数
function handleSave(): void {
  const name = sourceName.value.trim();

  if (!name) {
    localError.value = t("sources.common.nameRequired");
    return;
  }

  localError.value = null;
  const payload: SourceUpdatePayload = {
    sourceName: name,
    isPublic: isPublic.value,
  };

  if (isWebCrawl.value) {
    // extraction_rules 不在 settings 表单中编辑，从现有配置透传保留
    payload.webCrawlConfig = buildWebCrawlConfig({
      extractionRules: props.source.webCrawlConfig?.extraction_rules ?? [],
    });
  }

  emit("updateSource", payload);
  open.value = false;
}

function handleDelete(): void {
  emit("deleteSource");
  open.value = false;
}

/**
 * 重新刷新 settings Form 数据
 */
function resetForm(): void {
  sourceName.value = props.source.sourceName;
  isPublic.value = props.source.isPublic;
  resetWebCrawlConfigForm(props.source.webCrawlConfig);
  localError.value = null;
}

function badgeClass(tone: typeof sourceRow.value.statusTone) {
  if (tone === "success") {
    return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  }

  if (tone === "warning") {
    return "border-yellow-300/25 bg-yellow-300/10 text-yellow-100";
  }

  if (tone === "danger") {
    return "border-red-400/25 bg-red-400/10 text-red-100";
  }

  return "border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)";
}
</script>

<template>
  <Sheet v-model:open="open">
    <SheetTrigger as-child>
      <Button
        type="button"
        :aria-label="t('sources.settings.openAria', { name: sourceRow.name })"
        variant="outline"
        size="sm"
        class="w-24 overflow-hidden"
      >
        <Settings class="size-3.5" />
        {{ t("sources.common.actions.settings") }}
      </Button>
    </SheetTrigger>
    <SheetContent
      class="!right-0 !w-[min(520px,100dvw)] !max-w-[100dvw] min-w-0 gap-0 overflow-x-hidden border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <SheetHeader class="border-b border-(--line-soft) px-4.5 py-4">
        <SheetTitle class="text-[15px]">{{ sheetTitle }}</SheetTitle>
      </SheetHeader>

      <div
        class="console-scrollbar grid min-h-0 min-w-0 flex-1 content-start gap-5 overflow-x-hidden overflow-y-auto px-4.5 py-4.5"
      >
        <section class="grid gap-4">
          <div>
            <h2 class="console-panel-title">
              {{ t("sources.settings.profileTitle") }}
            </h2>
            <p class="console-panel-note">
              {{ t("sources.settings.profileHelp") }}
            </p>
          </div>

          <div class="grid gap-2">
            <Label for="source-settings-name">
              {{ t("sources.common.fields.name") }}
            </Label>
            <Input id="source-settings-name" v-model="sourceName" />
          </div>

          <div class="grid gap-2">
            <Label>{{ t("sources.common.fields.type") }}</Label>
            <div
              class="flex min-h-10 items-center justify-between rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3"
            >
              <span
                class="flex items-center gap-2 text-[13px] text-(--text-body)"
              >
                <Globe2 v-if="isWebCrawl" class="text-primary size-4" />
                <FileText v-else class="text-primary size-4" />
                {{ sourceRow.typeLabel }}
              </span>
              <Badge :class="badgeClass(sourceRow.statusTone)">
                {{ sourceRow.statusLabel }}
              </Badge>
            </div>
          </div>

          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <Label>
                {{ t("sources.common.fields.publicForVisitorRag") }}
              </Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                {{ visibilityHelp }}
              </p>
            </div>
            <Switch
              :model-value="isPublic"
              :aria-label="t('sources.settings.visibilityAria')"
              @update:model-value="isPublic = Boolean($event)"
            />
          </div>
        </section>

        <section
          v-if="isWebCrawl"
          class="grid gap-4 border-t border-(--line-soft) pt-4.5"
        >
          <div>
            <h2 class="console-panel-title">
              {{ t("sources.common.fields.webCrawlConfig") }}
            </h2>
            <p class="console-panel-note">
              {{ t("sources.settings.crawlHelp") }}
            </p>
          </div>

          <!-- 未启用 crawl 类型 DOM 说明 -->
          <div
            v-if="isLegacyCrawlEntry"
            class="grid gap-3 rounded-(--console-radius-lg) border border-amber-300/15 bg-amber-300/[0.045] p-3"
          >
            <div class="grid gap-1">
              <strong class="text-[13px] font-semibold text-amber-100/90">
                {{ t("sources.settings.legacyEntryTitle") }}
              </strong>
              <p class="text-xs leading-5 text-(--text-faint)">
                {{ t("sources.settings.legacyEntryHelp") }}
              </p>
            </div>
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
          </div>

          <div v-if="entryType === 'site_root'" class="grid gap-2">
            <Label for="web-root-url">
              {{ t("sources.common.fields.rootUrl") }}
            </Label> -->
              <Label>{{ legacyEntryLabel }}</Label>
              <Input
                :model-value="legacyEntryValue"
                readonly
                class="text-(--text-muted)"
              />
            </div>

            <!-- <div v-else-if="entryType === 'sitemap_url'" class="grid gap-2">
            <Label for="web-sitemap-url">
              {{ t("sources.common.fields.sitemapUrl") }}
            </Label>
            <Input
              id="web-sitemap-url"
              v-model="sitemapUrl"
              placeholder="https://docs.example.com/sitemap.xml"
            /> -->
          </div>

          <div v-else class="grid gap-2">
            <Label for="web-url-list">
              {{ t("sources.common.fields.urls") }}
            </Label>
            <Textarea
              id="web-url-list"
              v-model="urlsText"
              class="min-h-24 bg-(--surface-base)"
              placeholder="https://example.com/docs/intro&#10;https://example.com/docs/install"
            />
          </div>

          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="web-max-pages">
                {{ t("sources.common.fields.maxPages") }}
              </Label>
              <Input id="web-max-pages" v-model="maxPages" type="number" />
            </div>
            <div class="grid gap-2">
              <Label for="web-max-depth">
                {{ t("sources.common.fields.maxDepth") }}
              </Label>
              <Input id="web-max-depth" v-model="maxDepth" type="number" />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="web-allowed-domains">
              {{ t("sources.common.fields.allowedDomains") }}
            </Label>
            <Input
              id="web-allowed-domains"
              v-model="allowedDomainsText"
              placeholder="docs.example.com, example.com"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-include-paths">
              {{ t("sources.common.fields.includePaths") }}
            </Label>
            <Input
              id="web-include-paths"
              v-model="includePathsText"
              placeholder="/docs/, /api/"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-exclude-paths">
              {{ t("sources.common.fields.excludePaths") }}
            </Label>
            <Input
              id="web-exclude-paths"
              v-model="excludePathsText"
              placeholder="/blog/, /changelog/drafts/"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-content-selectors">
              {{ t("sources.common.fields.contentSelectors") }}
            </Label>
            <Input
              id="web-content-selectors"
              v-model="contentSelectorsText"
              placeholder="main, article, .docs-content"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-exclude-selectors">
              {{ t("sources.common.fields.excludeSelectors") }}
            </Label>
            <Input
              id="web-exclude-selectors"
              v-model="excludeSelectorsText"
              placeholder="nav, footer, .toc"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-request-delay">
              {{ t("sources.common.fields.requestDelayMs") }}
            </Label>
            <Input
              id="web-request-delay"
              v-model="requestDelayMs"
              type="number"
            />
            <!-- </div>
            <div class="pt-6">
              <Switch
                :model-value="respectRobotsTxt"
                :aria-label="t('sources.common.respectRobotsAria')"
                @update:model-value="respectRobotsTxt = Boolean($event)"
              />
            </div> -->
          </div>
        </section>

        <p v-if="localError" class="text-sm text-red-100">
          {{ localError }}
        </p>
      </div>

      <SheetFooter
        class="mt-0 flex-row justify-between border-t border-(--line-soft) p-4.5"
      >
        <AlertDialog>
          <AlertDialogTrigger as-child>
            <Button
              type="button"
              :aria-label="t('sources.settings.deleteAria')"
              variant="outline"
              class="border-red-400/35 text-red-100 hover:bg-red-400/10 hover:text-red-100"
              :disabled="isMutating"
            >
              <Trash2 class="size-4" />
              {{ t("sources.common.actions.delete") }}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {{ t("sources.settings.deleteTitle") }}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {{ t("sources.settings.deleteDescription") }}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>
                {{ t("sources.common.actions.cancel") }}
              </AlertDialogCancel>
              <AlertDialogAction
                class="bg-red-500 text-white hover:bg-red-500/90"
                @click="handleDelete"
              >
                {{ t("sources.common.actions.delete") }}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <div class="flex justify-end">
          <Button
            type="button"
            :aria-label="t('sources.settings.saveAria')"
            :disabled="isMutating"
            @click="handleSave"
          >
            {{ t("sources.common.actions.saveChanges") }}
          </Button>
        </div>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
