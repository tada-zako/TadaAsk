<script setup lang="ts">
// 导入 Lucide 图标
import {
  CirclePlay,
  Database,
  Eye,
  FileText,
  KeyRound,
  Pencil,
  Trash2,
  Upload,
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

// 导入本地文件设置抽屉
import SourceLocalFileSettingsSheet from "./SourceLocalFileSettingsSheet.vue";
</script>

<template>
  <!-- 本地文件数据源的文件项管理工作区 -->
  <section class="console-page">
    <!-- 页面头部：展示数据源名称、描述及上传/设置操作 -->
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">Local file source</p>
        <h1 class="console-page-title">Product docs PDF</h1>
        <p class="console-page-subtitle">
          Upload files, review generated source items, and index items when
          ready.
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-2 pb-0.5">
        <Input class="w-80 max-w-full" value="Search source items" />
        <Button type="button" aria-label="Upload files" size="sm">
          <Upload class="size-4" />
          Upload files
        </Button>
        <SourceLocalFileSettingsSheet />
      </div>
    </header>

    <!-- 文件列表及批量操作面板 -->
    <section class="console-table-panel">
      <!-- 批量操作工具栏 -->
      <div
        class="flex min-h-13 items-center justify-between gap-4 border-b border-(--line-soft) bg-[#111215] px-4 max-[760px]:grid max-[760px]:py-3"
      >
        <div class="flex items-center gap-3">
          <strong class="text-[13px] text-(--text-strong)">
            Selected: 2 files
          </strong>
          <span class="h-5 w-px bg-(--line)"></span>
          <span class="text-xs text-(--text-faint)">
            Batch operations apply to checked rows.
          </span>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            aria-label="Enable selected files"
            variant="outline"
            size="sm"
          >
            <Eye class="size-4" />
            Enable
          </Button>
          <Button
            type="button"
            aria-label="Index selected files"
            variant="outline"
            size="sm"
          >
            <CirclePlay class="size-4" />
            Index
          </Button>
          <Button
            type="button"
            aria-label="Cancel selected file indexing"
            variant="outline"
            size="sm"
          >
            <XCircle class="size-4" />
            Cancel
          </Button>
          <Button
            type="button"
            aria-label="Edit selected file metadata"
            variant="outline"
            size="sm"
          >
            <Database class="size-4" />
            Meta
          </Button>
          <Button
            type="button"
            aria-label="Delete selected files"
            variant="outline"
            size="sm"
            class="border-red-400/35 text-red-100 hover:bg-red-400/10"
          >
            <Trash2 class="size-4" />
            Delete
          </Button>
        </div>
      </div>

      <!-- 文件项表格 -->
      <Table class="console-scrollbar">
        <TableHeader>
          <TableRow>
            <TableHead class="w-11">Pick</TableHead>
            <TableHead>File</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Chunks</TableHead>
            <TableHead>Metadata</TableHead>
            <TableHead>Indexing</TableHead>
            <TableHead class="text-center">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <!-- 示例行 1：待处理文件 -->
          <TableRow>
            <TableCell>
              <Checkbox checked aria-label="Select getting started PDF" />
            </TableCell>
            <TableCell>
              <div class="flex min-w-60 items-center gap-2">
                <FileText class="size-4 text-blue-300" />
                <strong class="truncate">getting-started.pdf</strong>
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
                  aria-label="Index getting started PDF"
                  title="Index"
                  variant="ghost"
                  size="icon-sm"
                >
                  <CirclePlay class="text-primary size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Edit getting started PDF metadata"
                  title="Metadata"
                  variant="ghost"
                  size="icon-sm"
                >
                  <Database class="size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Delete getting started PDF"
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

          <!-- 示例行 2：已完成索引文件 -->
          <TableRow>
            <TableCell>
              <Checkbox checked aria-label="Select API reference PDF" />
            </TableCell>
            <TableCell>
              <div class="flex min-w-60 items-center gap-2">
                <FileText class="size-4 text-blue-300" />
                <strong class="truncate">api-reference.pdf</strong>
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
            <TableCell>24</TableCell>
            <TableCell>3 fields</TableCell>
            <TableCell>
              <span class="text-xs text-emerald-200">Ready</span>
            </TableCell>
            <TableCell>
              <div class="flex items-center justify-center gap-1.5">
                <Button
                  type="button"
                  aria-label="Re-index API reference PDF"
                  title="Re-index"
                  variant="ghost"
                  size="icon-sm"
                >
                  <CirclePlay class="text-primary size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Open API reference PDF permissions"
                  title="Permissions"
                  variant="ghost"
                  size="icon-sm"
                >
                  <KeyRound class="size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Edit API reference PDF"
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
              <Checkbox aria-label="Select release notes Markdown" />
            </TableCell>
            <TableCell>
              <div class="flex min-w-60 items-center gap-2">
                <FileText class="size-4 text-emerald-300" />
                <strong class="truncate">release-notes.md</strong>
              </div>
            </TableCell>
            <TableCell>20/04/2026 15:24</TableCell>
            <TableCell>
              <Badge
                class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100"
              >
                Indexing
              </Badge>
            </TableCell>
            <TableCell>0</TableCell>
            <TableCell>0 fields</TableCell>
            <TableCell>
              <div class="grid w-36 gap-1">
                <div
                  class="h-1.5 overflow-hidden rounded-full bg-(--surface-panel-soft)"
                >
                  <span
                    class="bg-primary block h-full w-[48%] rounded-full"
                  ></span>
                </div>
                <span class="text-[11px] text-(--text-faint)">48%</span>
              </div>
            </TableCell>
            <TableCell>
              <div class="flex items-center justify-center gap-1.5">
                <Button
                  type="button"
                  aria-label="Cancel release notes indexing"
                  title="Cancel"
                  variant="ghost"
                  size="icon-sm"
                >
                  <XCircle class="size-4 text-yellow-100" />
                </Button>
                <Button
                  type="button"
                  aria-label="Preview release notes Markdown"
                  title="Preview"
                  variant="ghost"
                  size="icon-sm"
                >
                  <Eye class="size-4" />
                </Button>
                <Button
                  type="button"
                  aria-label="Delete release notes Markdown"
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
