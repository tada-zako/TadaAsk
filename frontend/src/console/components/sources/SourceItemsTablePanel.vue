<script setup lang="ts">
// 导入 Vue 核心 API
import { computed } from "vue";
// 导入 Lucide 图标
import {
  CirclePlay,
  Download,
  FileText,
  Globe2,
  Pencil,
  Trash2,
  XCircle,
} from "@lucide/vue";

// 导入 UI 组件
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

// 定义组件属性
const props = defineProps<{
  sourceType: "local-file" | "web-crawl"; // source item 类型
}>();

// 辅助计算属性：判断是否为网页爬取类型
const isWebCrawl = computed(() => props.sourceType === "web-crawl");
// 批量操作实体文案
const entityLabel = computed(() => (isWebCrawl.value ? "pages" : "files"));
// 已选中状态文案
const selectedLabel = computed(() =>
  isWebCrawl.value ? "Selected: 3 pages" : "Selected: 2 files",
);
</script>

<template>
  <!-- Source item 统一列表面板：本地文件与网页项共享表格结构和列宽 -->
  <section class="console-table-panel">
    <!-- 批量操作工具栏 -->
    <div
      class="flex min-h-13 items-center justify-between gap-4 border-b border-(--line-soft) bg-[#111215] px-4 max-[760px]:grid max-[760px]:py-3"
    >
      <div class="flex items-center gap-3">
        <strong class="text-[13px] text-(--text-strong)">
          {{ selectedLabel }}
        </strong>
        <span class="h-5 w-px bg-(--line)"></span>
        <span class="text-xs text-(--text-faint)">
          Batch operations apply to checked rows.
        </span>
      </div>
      <div class="flex flex-wrap justify-end gap-2 max-[760px]:justify-start">
        <Button
          type="button"
          :aria-label="`Index selected ${entityLabel}`"
          variant="outline"
          size="sm"
        >
          <CirclePlay class="size-4" />
          Index
        </Button>
        <Button
          type="button"
          :aria-label="`Pause selected ${entityLabel} indexing`"
          variant="outline"
          size="sm"
        >
          <XCircle class="size-4" />
          Pause
        </Button>
        <Button
          type="button"
          :aria-label="`Download selected ${entityLabel}`"
          variant="outline"
          size="sm"
        >
          <Download class="size-4" />
          Download
        </Button>
        <Button
          type="button"
          :aria-label="`Delete selected ${entityLabel}`"
          variant="outline"
          size="sm"
          class="border-red-400/35 text-red-100 hover:bg-red-400/10"
        >
          <Trash2 class="size-4" />
          Delete
        </Button>
      </div>
    </div>

    <!-- Source item 表格 -->
    <Table class="console-scrollbar min-w-[58rem] table-fixed">
      <colgroup>
        <col class="w-12" />
        <col class="w-[34%]" />
        <col class="w-[10.5rem]" />
        <col class="w-[8rem]" />
        <col class="w-[12rem]" />
        <col class="w-[11.5rem]" />
      </colgroup>
      <TableHeader>
        <TableRow>
          <TableHead class="text-center">
            <Checkbox
              :aria-label="`Select all ${entityLabel}`"
              class="mx-auto"
            />
          </TableHead>
          <TableHead>{{ isWebCrawl ? "Page" : "File" }}</TableHead>
          <TableHead>Updated</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Indexing</TableHead>
          <TableHead class="text-center">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <!-- 示例行 1：待处理 item -->
        <TableRow>
          <TableCell class="text-center">
            <Checkbox
              checked
              :aria-label="
                isWebCrawl
                  ? 'Select Getting Started page'
                  : 'Select getting started PDF'
              "
              class="mx-auto"
            />
          </TableCell>
          <TableCell>
            <div class="grid min-w-0 gap-1">
              <div class="flex min-w-0 items-center gap-2">
                <Globe2
                  v-if="isWebCrawl"
                  class="size-4 shrink-0 text-blue-300"
                />
                <FileText v-else class="size-4 shrink-0 text-blue-300" />
                <strong class="truncate">
                  {{ isWebCrawl ? "Getting Started" : "getting-started.pdf" }}
                </strong>
              </div>
              <span
                v-if="isWebCrawl"
                class="truncate text-xs text-(--text-faint)"
              >
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
          <TableCell>
            <span class="text-xs text-(--text-faint)">Not indexed</span>
          </TableCell>
          <TableCell>
            <div class="flex items-center justify-center gap-1">
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Index Getting Started page'
                    : 'Index getting started PDF'
                "
                title="Index"
                variant="ghost"
                size="icon-sm"
              >
                <CirclePlay class="text-primary size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Download Getting Started page'
                    : 'Download getting started PDF'
                "
                title="Download"
                variant="ghost"
                size="icon-sm"
              >
                <Download class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Rename Getting Started page'
                    : 'Rename getting started PDF'
                "
                title="Rename"
                variant="ghost"
                size="icon-sm"
              >
                <Pencil class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Delete Getting Started page'
                    : 'Delete getting started PDF'
                "
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

        <!-- 示例行 2：已完成索引 item -->
        <TableRow>
          <TableCell class="text-center">
            <Checkbox
              checked
              :aria-label="
                isWebCrawl
                  ? 'Select Install TadaAsk page'
                  : 'Select API reference PDF'
              "
              class="mx-auto"
            />
          </TableCell>
          <TableCell>
            <div class="grid min-w-0 gap-1">
              <div class="flex min-w-0 items-center gap-2">
                <Globe2
                  v-if="isWebCrawl"
                  class="size-4 shrink-0 text-blue-300"
                />
                <FileText v-else class="size-4 shrink-0 text-blue-300" />
                <strong class="truncate">
                  {{ isWebCrawl ? "Install TadaAsk" : "api-reference.pdf" }}
                </strong>
              </div>
              <span
                v-if="isWebCrawl"
                class="truncate text-xs text-(--text-faint)"
              >
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
          <TableCell>
            <span class="text-xs text-emerald-200">Ready</span>
          </TableCell>
          <TableCell>
            <div class="flex items-center justify-center gap-1">
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Re-index Install TadaAsk page'
                    : 'Re-index API reference PDF'
                "
                title="Re-index"
                variant="ghost"
                size="icon-sm"
              >
                <CirclePlay class="text-primary size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Download Install TadaAsk page'
                    : 'Download API reference PDF'
                "
                title="Download"
                variant="ghost"
                size="icon-sm"
              >
                <Download class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Rename Install TadaAsk page'
                    : 'Rename API reference PDF'
                "
                title="Rename"
                variant="ghost"
                size="icon-sm"
              >
                <Pencil class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Delete Install TadaAsk page'
                    : 'Delete API reference PDF'
                "
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

        <!-- 示例行 3：正在索引 item -->
        <TableRow>
          <TableCell class="text-center">
            <Checkbox
              :aria-label="
                isWebCrawl
                  ? 'Select API Reference page'
                  : 'Select release notes Markdown'
              "
              class="mx-auto"
            />
          </TableCell>
          <TableCell>
            <div class="grid min-w-0 gap-1">
              <div class="flex min-w-0 items-center gap-2">
                <Globe2
                  v-if="isWebCrawl"
                  class="size-4 shrink-0 text-blue-300"
                />
                <FileText v-else class="size-4 shrink-0 text-emerald-300" />
                <strong class="truncate">
                  {{ isWebCrawl ? "API Reference" : "release-notes.md" }}
                </strong>
              </div>
              <span
                v-if="isWebCrawl"
                class="truncate text-xs text-(--text-faint)"
              >
                https://docs.example.com/api
              </span>
            </div>
          </TableCell>
          <TableCell>{{
            isWebCrawl ? "02/06/2026 15:30" : "20/04/2026 15:24"
          }}</TableCell>
          <TableCell>
            <Badge
              class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100"
            >
              Indexing
            </Badge>
          </TableCell>
          <TableCell>
            <div class="flex w-40 items-center gap-2">
              <div
                class="h-1.5 flex-1 overflow-hidden rounded-full bg-(--surface-panel-soft)"
              >
                <span
                  class="bg-primary block h-full w-[48%] rounded-full"
                ></span>
              </div>
              <span class="w-8 text-right text-[11px] text-(--text-faint)">
                48%
              </span>
            </div>
          </TableCell>
          <TableCell>
            <div class="flex items-center justify-center gap-1">
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Pause API Reference page indexing'
                    : 'Pause release notes indexing'
                "
                title="Pause indexing"
                variant="ghost"
                size="icon-sm"
              >
                <XCircle class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Download API Reference page'
                    : 'Download release notes Markdown'
                "
                title="Download"
                variant="ghost"
                size="icon-sm"
              >
                <Download class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Rename API Reference page'
                    : 'Rename release notes Markdown'
                "
                title="Rename"
                variant="ghost"
                size="icon-sm"
              >
                <Pencil class="size-4" />
              </Button>
              <Button
                type="button"
                :aria-label="
                  isWebCrawl
                    ? 'Delete API Reference page'
                    : 'Delete release notes Markdown'
                "
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
</template>
