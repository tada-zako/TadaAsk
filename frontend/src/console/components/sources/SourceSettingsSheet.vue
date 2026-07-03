<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { FileText, Globe2, Settings, Trash2 } from "@lucide/vue";

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

const props = defineProps<{
  source: SourceRead;
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "updateSource", input: SourceUpdatePayload): void;
  (event: "deleteSource"): void;
}>();

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
  respectRobotsTxt,
  sitemapUrl,
  siteRootUrl,
  urlsText,
} = useWebCrawlConfigForm();
const localError = ref<string | null>(null);

const sourceRow = computed(() => toSourceRow(props.source));
const isWebCrawl = computed(() => props.source.sourceType === "web_crawl");
const sheetTitle = computed(() =>
  isWebCrawl.value ? "Web crawl settings" : "Local file settings",
);

const visibilityHelp = computed(() =>
  isWebCrawl.value
    ? "Keep enabled only after crawl results are reviewed."
    : "Disable while uploading or reviewing imported files.",
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
    localError.value = "Source name is required.";
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
        :aria-label="`Open ${sourceRow.name} source settings`"
        variant="outline"
        size="sm"
        class="w-24 overflow-hidden"
      >
        <Settings class="size-3.5" />
        Settings
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
            <h2 class="console-panel-title">Source profile</h2>
            <p class="console-panel-note">
              Edit the container name and visitor visibility for this source.
            </p>
          </div>

          <div class="grid gap-2">
            <Label for="source-settings-name">Name</Label>
            <Input id="source-settings-name" v-model="sourceName" />
          </div>

          <div class="grid gap-2">
            <Label>Type</Label>
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
              <Label>Public for visitor RAG</Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                {{ visibilityHelp }}
              </p>
            </div>
            <Switch
              :model-value="isPublic"
              aria-label="Source visibility"
              @update:model-value="isPublic = Boolean($event)"
            />
          </div>
        </section>

        <section
          v-if="isWebCrawl"
          class="grid gap-4 border-t border-(--line-soft) pt-4.5"
        >
          <div>
            <h2 class="console-panel-title">Web crawl config</h2>
            <p class="console-panel-note">
              Updating crawl rules resets the source to pending when accepted.
            </p>
          </div>

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

          <div v-if="entryType === 'site_root'" class="grid gap-2">
            <Label for="web-root-url">Root URL</Label>
            <Input
              id="web-root-url"
              v-model="siteRootUrl"
              placeholder="https://docs.example.com/"
            />
          </div>

          <div v-else-if="entryType === 'sitemap_url'" class="grid gap-2">
            <Label for="web-sitemap-url">Sitemap URL</Label>
            <Input
              id="web-sitemap-url"
              v-model="sitemapUrl"
              placeholder="https://docs.example.com/sitemap.xml"
            />
          </div>

          <div v-else class="grid gap-2">
            <Label for="web-url-list">URLs</Label>
            <Textarea
              id="web-url-list"
              v-model="urlsText"
              class="min-h-24 bg-(--surface-base)"
              placeholder="https://example.com/docs/intro&#10;https://example.com/docs/install"
            />
          </div>

          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="web-max-pages">Max pages</Label>
              <Input id="web-max-pages" v-model="maxPages" type="number" />
            </div>
            <div class="grid gap-2">
              <Label for="web-max-depth">Max depth</Label>
              <Input id="web-max-depth" v-model="maxDepth" type="number" />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="web-allowed-domains">Allowed domains</Label>
            <Input
              id="web-allowed-domains"
              v-model="allowedDomainsText"
              placeholder="docs.example.com, example.com"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-include-paths">Include paths</Label>
            <Input
              id="web-include-paths"
              v-model="includePathsText"
              placeholder="/docs/, /api/"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-exclude-paths">Exclude paths</Label>
            <Input
              id="web-exclude-paths"
              v-model="excludePathsText"
              placeholder="/blog/, /changelog/drafts/"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-content-selectors">Content selectors</Label>
            <Input
              id="web-content-selectors"
              v-model="contentSelectorsText"
              placeholder="main, article, .docs-content"
            />
          </div>

          <div class="grid gap-2">
            <Label for="web-exclude-selectors">Exclude selectors</Label>
            <Input
              id="web-exclude-selectors"
              v-model="excludeSelectorsText"
              placeholder="nav, footer, .toc"
            />
          </div>

          <div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
            <div class="grid gap-2">
              <Label for="web-request-delay">Request delay ms</Label>
              <Input
                id="web-request-delay"
                v-model="requestDelayMs"
                type="number"
              />
            </div>
            <div class="pt-6">
              <Switch
                :model-value="respectRobotsTxt"
                aria-label="Respect robots txt"
                @update:model-value="respectRobotsTxt = Boolean($event)"
              />
            </div>
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
              aria-label="Delete source"
              variant="outline"
              class="border-red-400/35 text-red-100 hover:bg-red-400/10 hover:text-red-100"
              :disabled="isMutating"
            >
              <Trash2 class="size-4" />
              Delete
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this source?</AlertDialogTitle>
              <AlertDialogDescription>
                This removes the source container and its related source items.
                Processing sources may be rejected by the backend.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                class="bg-red-500 text-white hover:bg-red-500/90"
                @click="handleDelete"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <div class="flex justify-end">
          <Button
            type="button"
            aria-label="Save source settings"
            :disabled="isMutating"
            @click="handleSave"
          >
            Save changes
          </Button>
        </div>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
