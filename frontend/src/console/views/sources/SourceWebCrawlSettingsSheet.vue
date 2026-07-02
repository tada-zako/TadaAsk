<script setup lang="ts">
// 导入 Lucide 图标
import { Globe2, Settings } from "@lucide/vue";

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
</script>

<template>
  <!-- 网页爬取数据源的设置抽屉 -->
  <Sheet>
    <SheetTrigger as-child>
      <Button
        type="button"
        aria-label="Open web crawl source settings"
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
      <!-- 抽屉头部 -->
      <SheetHeader class="border-b border-(--line-soft) px-4.5 py-4">
        <SheetTitle class="text-[15px]">Web crawl settings</SheetTitle>
      </SheetHeader>

      <!-- 设置表单滚动区域 -->
      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-5 overflow-auto px-4.5 py-4.5"
      >
        <!-- 数据源基本信息配置 -->
        <section class="grid gap-4">
          <div>
            <h2 class="console-panel-title">Source profile</h2>
            <p class="console-panel-note">
              Edit the source container before changing crawl rules.
            </p>
          </div>

          <!-- 数据源名称 -->
          <div class="grid gap-2">
            <Label for="web-source-name">Name</Label>
            <Input id="web-source-name" value="Main website pages" />
          </div>

          <!-- 数据源类型展示 -->
          <div class="grid gap-2">
            <Label>Type</Label>
            <div
              class="flex min-h-10 items-center justify-between rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel-soft) px-3"
            >
              <span
                class="flex items-center gap-2 text-[13px] text-(--text-body)"
              >
                <Globe2 class="text-primary size-4" />
                WEB CRAWL
              </span>
              <Badge
                class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100"
              >
                Processing
              </Badge>
            </div>
          </div>

          <!-- 可见性开关 -->
          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <Label>Public for visitor RAG</Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                Keep enabled only after crawl results are reviewed.
              </p>
            </div>
            <Switch checked aria-label="Web crawl source visibility" />
          </div>
        </section>

        <!-- 网页爬取规则配置 -->
        <section class="grid gap-4 border-t border-(--line-soft) pt-4.5">
          <div>
            <h2 class="console-panel-title">Web crawl config</h2>
            <p class="console-panel-note">
              Static edit fields mirror the future update surface.
            </p>
          </div>

          <!-- 入口类型 -->
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

          <!-- 起始 URL -->
          <div class="grid gap-2">
            <Label for="web-root-url">Root URL</Label>
            <Input id="web-root-url" value="https://docs.example.com/" />
          </div>

          <!-- 限制参数 -->
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

          <!-- 包含路径 -->
          <div class="grid gap-2">
            <Label for="web-include-paths">Include paths</Label>
            <Input id="web-include-paths" value="/docs/, /api/" />
          </div>

          <!-- 排除路径 -->
          <div class="grid gap-2">
            <Label for="web-exclude-paths">Exclude paths</Label>
            <Input id="web-exclude-paths" value="/blog/, /changelog/drafts/" />
          </div>

          <!-- 内容提取选择器 -->
          <div class="grid gap-2">
            <Label for="web-content-selectors">Content selectors</Label>
            <Input
              id="web-content-selectors"
              value="main, article, .docs-content"
            />
          </div>
        </section>
      </div>

      <!-- 底部操作按钮 -->
      <SheetFooter
        class="mt-0 flex-row justify-end border-t border-(--line-soft) p-4.5"
      >
        <SheetClose as-child>
          <Button
            type="button"
            aria-label="Close web crawl source settings"
            variant="outline"
          >
            Close
          </Button>
        </SheetClose>
        <Button
          type="button"
          aria-label="Save web crawl source settings"
          disabled
        >
          Save changes
        </Button>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
