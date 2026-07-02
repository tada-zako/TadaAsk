<script setup lang="ts">
// 导入 Vue 核心 API
import { computed } from "vue";
// 导入 Lucide 图标
import { FileText, Globe2, Settings } from "@lucide/vue";

// 导入 UI 组件
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
  SheetClose,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/shared/components/ui/sheet";
import { Switch } from "@/shared/components/ui/switch";

// 定义组件属性
const props = defineProps<{
  sourceType: "local-file" | "web-crawl";
}>();

// 辅助计算属性：判断是否为网页爬取类型
const isWebCrawl = computed(() => props.sourceType === "web-crawl");
// 抽屉标题
const sheetTitle = computed(() =>
  isWebCrawl.value ? "Web crawl settings" : "Local file settings",
);
// 默认数据源名称
const sourceName = computed(() =>
  isWebCrawl.value ? "Main website pages" : "Product docs PDF",
);
// 数据源类型标签
const sourceTypeLabel = computed(() =>
  isWebCrawl.value ? "WEB CRAWL" : "LOCAL FILE",
);
// 状态标签
const statusLabel = computed(() =>
  isWebCrawl.value ? "Processing" : "Indexed",
);
// 可见性提示文本
const visibilityHelp = computed(() =>
  isWebCrawl.value
    ? "Keep enabled only after crawl results are reviewed."
    : "Disable while uploading or reviewing imported files.",
);
</script>

<template>
  <Sheet>
    <SheetTrigger as-child>
      <Button
        type="button"
        :aria-label="`Open ${sourceTypeLabel.toLowerCase()} source settings`"
        variant="outline"
        size="sm"
        class="w-24 overflow-hidden"
      >
        <Settings class="size-3.5" />
        Settings
      </Button>
    </SheetTrigger>
    <SheetContent
      class="w-[min(520px,100vw)] gap-0 border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <SheetHeader class="border-b border-(--line-soft) px-4.5 py-4">
        <SheetTitle class="text-[15px]">{{ sheetTitle }}</SheetTitle>
      </SheetHeader>

      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-5 overflow-auto px-4.5 py-4.5"
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
            <Input id="source-settings-name" :value="sourceName" />
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
                {{ sourceTypeLabel }}
              </span>
              <Badge
                :class="
                  isWebCrawl
                    ? 'border-yellow-300/25 bg-yellow-300/10 text-yellow-100'
                    : 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200'
                "
              >
                {{ statusLabel }}
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
            <Switch checked aria-label="Source visibility" />
          </div>
        </section>

        <section
          v-if="isWebCrawl"
          class="grid gap-4 border-t border-(--line-soft) pt-4.5"
        >
          <div>
            <h2 class="console-panel-title">Web crawl config</h2>
            <p class="console-panel-note">
              Static edit fields mirror the future update surface.
            </p>
          </div>

          <div class="grid gap-2">
            <Label>Entry type</Label>
            <Select default-value="site_root">
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

          <div class="grid gap-2">
            <Label for="web-root-url">Root URL</Label>
            <Input id="web-root-url" value="https://docs.example.com/" />
          </div>

          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="web-max-pages">Max pages</Label>
              <Input id="web-max-pages" value="20" />
            </div>
            <div class="grid gap-2">
              <Label for="web-max-depth">Max depth</Label>
              <Input id="web-max-depth" value="3" />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="web-include-paths">Include paths</Label>
            <Input id="web-include-paths" value="/docs/, /api/" />
          </div>

          <div class="grid gap-2">
            <Label for="web-exclude-paths">Exclude paths</Label>
            <Input id="web-exclude-paths" value="/blog/, /changelog/drafts/" />
          </div>

          <div class="grid gap-2">
            <Label for="web-content-selectors">Content selectors</Label>
            <Input
              id="web-content-selectors"
              value="main, article, .docs-content"
            />
          </div>
        </section>
      </div>

      <SheetFooter
        class="mt-0 flex-row justify-end border-t border-(--line-soft) p-4.5"
      >
        <SheetClose as-child>
          <Button
            type="button"
            aria-label="Close source settings"
            variant="outline"
          >
            Close
          </Button>
        </SheetClose>
        <Button type="button" aria-label="Save source settings" disabled>
          Save changes
        </Button>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
