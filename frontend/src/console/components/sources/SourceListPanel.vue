<script setup lang="ts">
// 导入 Lucide 图标
import { FileText, Funnel, Globe2, Search } from "@lucide/vue";

// 导入 UI 组件
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

// 导入设置抽屉组件
import SourceSettingsSheet from "./SourceSettingsSheet.vue";
</script>

<template>
  <!-- 数据源列表面板 -->
  <section class="console-table-panel">
    <!-- 顶部过滤与搜索栏 -->
    <div
      class="flex min-h-14 items-center justify-between gap-4 border-b border-(--line-soft) px-4 max-[760px]:grid max-[760px]:py-3"
    >
      <!-- 搜索框 -->
      <div class="relative w-[21.5rem] max-w-full">
        <Search
          class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-(--text-faint)"
        />
        <Input class="pl-9" value="Search sources" />
      </div>
      <!-- 类型过滤下拉框 -->
      <Select default-value="all">
        <SelectTrigger
          class="w-[11.25rem] border-(--line) bg-(--surface-panel-soft) text-(--text-body)"
          aria-label="Filter sources by type"
        >
          <Funnel class="size-4 text-(--text-faint)" />
          <SelectValue placeholder="Filter by type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All types</SelectItem>
          <SelectItem value="local-file">Local file</SelectItem>
          <SelectItem value="web-crawl">Web crawl</SelectItem>
        </SelectContent>
      </Select>
    </div>

    <!-- 数据源表格 -->
    <Table class="console-scrollbar">
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Visibility</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last synced</TableHead>
          <TableHead class="text-center">Workspace</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <!-- 示例行 1：本地文件数据源 -->
        <TableRow>
          <TableCell>
            <strong>Product docs PDF</strong>
          </TableCell>
          <TableCell>
            <span class="flex items-center gap-2">
              <span
                class="text-primary grid size-6.5 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <FileText class="size-3.5" />
              </span>
              <span class="text-xs font-semibold tracking-[0.08em]">
                LOCAL FILE
              </span>
            </span>
          </TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
            >
              Public
            </Badge>
          </TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
            >
              Indexed
            </Badge>
          </TableCell>
          <TableCell>12 minutes ago</TableCell>
          <TableCell class="text-center">
            <div class="flex items-center justify-center gap-2">
              <Button
                type="button"
                aria-label="Open local file source items"
                variant="outline"
                size="sm"
                class="w-24 overflow-hidden"
              >
                Items
              </Button>
              <SourceSettingsSheet source-type="local-file" />
            </div>
          </TableCell>
        </TableRow>

        <!-- 示例行 2：网页爬取数据源 -->
        <TableRow>
          <TableCell>
            <strong>Main website pages</strong>
          </TableCell>
          <TableCell>
            <span class="flex items-center gap-2">
              <span
                class="text-primary grid size-6.5 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <Globe2 class="size-3.5" />
              </span>
              <span class="text-xs font-semibold tracking-[0.08em]">
                WEB CRAWL
              </span>
            </span>
          </TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
            >
              Public
            </Badge>
          </TableCell>
          <TableCell>
            <Badge
              class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100"
            >
              Processing
            </Badge>
          </TableCell>
          <TableCell>about 1 hour ago</TableCell>
          <TableCell class="text-center">
            <div class="flex items-center justify-center gap-2">
              <Button
                type="button"
                aria-label="Open web crawl source items"
                variant="outline"
                size="sm"
                class="w-24 overflow-hidden"
              >
                Items
              </Button>
              <SourceSettingsSheet source-type="web-crawl" />
            </div>
          </TableCell>
        </TableRow>

        <!-- 示例行 3：私有/未同步的本地文件数据源 -->
        <TableRow>
          <TableCell>
            <strong>Release notes archive</strong>
          </TableCell>
          <TableCell>
            <span class="flex items-center gap-2">
              <span
                class="text-primary grid size-6.5 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <FileText class="size-3.5" />
              </span>
              <span class="text-xs font-semibold tracking-[0.08em]">
                LOCAL FILE
              </span>
            </span>
          </TableCell>
          <TableCell>
            <Badge
              class="border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)"
            >
              Private
            </Badge>
          </TableCell>
          <TableCell>
            <Badge
              class="border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)"
            >
              Pending
            </Badge>
          </TableCell>
          <TableCell>Not synced</TableCell>
          <TableCell class="text-center">
            <div class="flex items-center justify-center gap-2">
              <Button
                type="button"
                aria-label="Open release notes source items"
                variant="outline"
                size="sm"
                class="w-24 overflow-hidden"
              >
                Items
              </Button>
              <SourceSettingsSheet source-type="local-file" />
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
