<script setup lang="ts">
// 导入 Lucide 图标
import {
  CirclePlay,
  Database,
  Eye,
  Globe2,
  KeyRound,
  Pencil,
  RefreshCw,
  Trash2,
  XCircle,
} from "@lucide/vue";

// 导入 UI 组件
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Input } from "@/shared/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

// 导入网页爬取设置抽屉
import SourceWebCrawlSettingsSheet from "./SourceWebCrawlSettingsSheet.vue";
</script>

<template>
  <!-- 网页爬取数据源的页面项管理工作区 -->
  <section class="console-page">
    <!-- 页面头部：展示数据源名称、描述及同步/设置操作 -->
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">Web crawl source</p>
        <h1 class="console-page-title">Main website pages</h1>
        <p class="console-page-subtitle">
          Sync configured crawl targets to create source items, then index
          selected pages.
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2 pb-0.5">
        <Input class="w-80 max-w-full" value="Search crawled pages" />
        <Button type="button" aria-label="Sync crawl" size="sm">
          <RefreshCw class="size-4" />
          Sync crawl
        </Button>
        <SourceWebCrawlSettingsSheet />
      </div>
    </header>

    <!-- 爬取同步状态流（展示后端 SSE 实时事件） -->
    <section
      class="grid gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-4"
    >
      <div class="flex items-center justify-between gap-4 max-[760px]:grid">
        <div>
          <strong class="text-sm text-(--text-strong)">Sync stream</strong>
          <p class="mt-1 text-xs text-(--text-faint)">
            Detailed crawl events should mirror backend SSE payloads when wired.
          </p>
        </div>
        <Badge
          class="border-(--line-soft) bg-(--surface-panel) text-(--text-muted)"
        >
          Idle
        </Badge>
      </div>
    </section>

    <!-- 页面列表及批量操作面板 -->
    <section class="console-table-panel">
      <!-- 批量操作工具栏 -->
      <div
        class="flex min-h-13 items-center justify-between gap-4 border-b border-(--line-soft) bg-[#111215] px-4 max-[760px]:grid max-[760px]:py-3"
      >
        <div class="flex items-center gap-3">
          <strong class="text-[13px] text-(--text-strong)">
            Selected: 3 pages
          </strong>
          <span class="h-5 w-px bg-(--line)"></span>
          <span class="text-xs text-(--text-faint)">
            Batch operations apply to checked rows.
          </span>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            aria-label="Enable selected pages"
            variant="outline"
            size="sm"
          >
            <Eye class="size-4" />
            Enable
          </Button>
          <Button
            type="button"
            aria-label="Index selected pages"
            variant="outline"
            size="sm"
          >
            <CirclePlay class="size-4" />
            Index
          </Button>
          <Button
            type="button"
            aria-label="Cancel selected page indexing"
            variant="outline"
            size="sm"
          >
            <XCircle class="size-4" />
            Cancel
          </Button>
          <Button
            type="button"
            aria-label="Edit selected page metadata"
            variant="outline"
            size="sm"
          >
            <Database class="size-4" />
            Meta
          </Button>
          <Button
            type="button"
            aria-label="Delete selected pages"
            variant="outline"
            size="sm"
            class="border-red-400/35 text-red-100 hover:bg-red-400/10"
          >
            <Trash2 class="size-4" />
            Delete
          </Button>
        </div>
      </div>

      <!-- 页面项表格 -->
      <Table class="console-scrollbar">
        <TableHeader>
          <TableRow>
            <TableHead class="w-11">Pick</TableHead>
            <TableHead>Page</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Chunks</TableHead>
            <TableHead>Metadata</TableHead>
            <TableHead>Indexing</TableHead>
            <TableHead class="text-center">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <!-- 示例行 1：待处理页面 -->
          <TableRow>
            <TableCell>
              <Checkbox checked aria-label="Select Getting Started page" />
            </TableCell>
            <TableCell>
              <div class="grid min-w-72 gap-1">
                <strong>Getting Started</strong>
                <span class="text-xs text-(--text-faint)">
                  https://docs.example.com/docs/intro
                </span>
              </div>
            </TableCell>
            <TableCell>03/06/2026 18:51</TableCell>
            <TableCell>
              <Badge
                class="border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)"
              >
                Pending
              </Badge>
            </TableCell>
            <TableCell>0</TableCell>
            <TableCell>0 fields</TableCell>
            <TableCell>
              <span class="text-xs text-(--text-faint)">Not indexed</span>
            </TableCell>
            <TableCell>
              <div class="flex items-center justify-center gap-1.5">
                <Button
                  type="button"
                  aria-label="Index Getting Started page"
                  title="Index"
                  variant="ghost"
                  size="icon-sm"
                >
                  <CirclePlay class="text-primary size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Open Getting Started page"
                  title="Preview"
                  variant="ghost"
                  size="icon-sm"
                >
                  <Globe2 class="size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Delete Getting Started page"
                  title="Delete"
                  variant="ghost"
                  size="icon-sm"
                  class="text-red-100 hover:bg-red-400/10 hover:text-red-100"
                >
                  <Trash2 class="size-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell>
              <Checkbox checked aria-label="Select Install TadaAsk page" />
            </TableCell>
            <TableCell>
              <div class="grid min-w-72 gap-1">
                <strong>Install TadaAsk</strong>
                <span class="text-xs text-(--text-faint)">
                  https://docs.example.com/docs/install
                </span>
              </div>
            </TableCell>
            <TableCell>03/06/2026 18:50</TableCell>
            <TableCell>
              <Badge
                class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
              >
                Completed
              </Badge>
            </TableCell>
            <TableCell>18</TableCell>
            <TableCell>2 fields</TableCell>
            <TableCell>
              <span class="text-xs text-emerald-200">Ready</span>
            </TableCell>
            <TableCell>
              <div class="flex items-center justify-center gap-1.5">
                <Button
                  type="button"
                  aria-label="Re-index Install TadaAsk page"
                  title="Re-index"
                  variant="ghost"
                  size="icon-sm"
                >
                  <CirclePlay class="text-primary size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Open Install TadaAsk permissions"
                  title="Permissions"
                  variant="ghost"
                  size="icon-sm"
                >
                  <KeyRound class="size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Edit Install TadaAsk page"
                  title="Edit"
                  variant="ghost"
                  size="icon-sm"
                >
                  <Pencil class="size-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell>
              <Checkbox checked aria-label="Select API Reference page" />
            </TableCell>
            <TableCell>
              <div class="grid min-w-72 gap-1">
                <strong>API Reference</strong>
                <span class="text-xs text-(--text-faint)">
                  https://docs.example.com/api
                </span>
              </div>
            </TableCell>
            <TableCell>02/06/2026 15:30</TableCell>
            <TableCell>
              <Badge class="border-red-400/25 bg-red-400/10 text-red-100">
                Failed
              </Badge>
            </TableCell>
            <TableCell>0</TableCell>
            <TableCell>0 fields</TableCell>
            <TableCell>
              <span class="text-xs text-red-100">Fetch failed</span>
            </TableCell>
            <TableCell>
              <div class="flex items-center justify-center gap-1.5">
                <Button
                  type="button"
                  aria-label="Retry API Reference page"
                  title="Retry"
                  variant="ghost"
                  size="icon-sm"
                >
                  <CirclePlay class="text-primary size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Preview API Reference page"
                  title="Preview"
                  variant="ghost"
                  size="icon-sm"
                >
                  <Eye class="size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Delete API Reference page"
                  title="Delete"
                  variant="ghost"
                  size="icon-sm"
                  class="text-red-100 hover:bg-red-400/10 hover:text-red-100"
                >
                  <Trash2 class="size-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  </section>
</template>
