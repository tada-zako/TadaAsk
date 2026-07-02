<script setup lang="ts">
// 导入 Lucide 图标
import { FileText, Globe2, Plus } from "@lucide/vue";

// 导入 UI 组件
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
</script>

<template>
  <!-- 创建知识库数据源的侧边栏抽屉 -->
  <Sheet>
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
              class="border-primary/35 bg-primary/10 grid min-h-24 content-start gap-2 rounded-(--console-radius-lg) border p-3 text-left"
              type="button"
              aria-label="Local file source type"
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
              class="grid min-h-24 content-start gap-2 rounded-(--console-radius-lg) border border-(--line) bg-(--surface-panel-soft) p-3 text-left"
              type="button"
              aria-label="Web crawl source type"
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
          <Input id="source-name" value="Product docs PDF" />
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
            <Switch checked aria-label="Public for visitor RAG" />
          </div>
          <p class="text-xs leading-5 text-(--text-faint)">
            Visitor RAG still requires at least one completed source item.
          </p>
        </section>

        <!-- 网页爬取配置面板（仅在选择 Web crawl 时展示） -->
        <section class="console-panel grid gap-4 p-4">
          <div>
            <h2 class="console-panel-title">Web crawl config when selected</h2>
            <p class="console-panel-note">
              These fields appear only for web crawl sources.
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
            <Label for="seed-url">Seed URL</Label>
            <Input id="seed-url" value="https://docs.example.com/" />
          </div>

          <!-- 限制参数 -->
          <div class="grid grid-cols-2 gap-3 max-[560px]:grid-cols-1">
            <div class="grid gap-2">
              <Label for="max-pages">Max pages</Label>
              <Input id="max-pages" value="20" />
            </div>
            <div class="grid gap-2">
              <Label for="max-depth">Max depth</Label>
              <Input id="max-depth" value="3" />
            </div>
          </div>

          <!-- 提取选择器 -->
          <div class="grid gap-2">
            <Label for="content-selectors">Content selectors</Label>
            <Input
              id="content-selectors"
              value="main, article, .docs-content"
            />
          </div>

          <!-- 排除选择器 -->
          <div class="grid gap-2">
            <Label for="exclude-selectors">Exclude selectors</Label>
            <Input id="exclude-selectors" value="nav, footer, .toc" />
          </div>
        </section>
      </div>

      <!-- 底部操作按钮 -->
      <SheetFooter
        class="mt-0 flex-row justify-end border-t border-(--line-soft) p-4.5"
      >
        <Button
          type="button"
          aria-label="Cancel create source"
          variant="outline"
        >
          Cancel
        </Button>
        <Button type="button" aria-label="Confirm create source">
          Create
        </Button>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
