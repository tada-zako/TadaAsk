<script setup lang="ts">
import { Ellipsis, ExternalLink, Link, Unlink } from "@lucide/vue";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
</script>

<template>
  <!-- 项目关联数据源面板 -->
  <section class="console-table-panel">
    <!-- 面板头部操作栏 -->
    <div
      class="flex min-h-12 items-center justify-between gap-4 border-b border-(--line-soft) px-4 max-[760px]:items-start max-[760px]:py-3"
    >
      <p class="text-xs text-(--text-faint)">4 linked</p>
      <div
        class="flex shrink-0 flex-wrap justify-end gap-2 max-[760px]:justify-start"
      >
        <Button
          type="button"
          aria-label="Open global sources"
          variant="outline"
          size="sm"
        >
          <ExternalLink class="size-4" />
          Global sources
        </Button>
        <!-- 导入数据源对话框 -->
        <Dialog>
          <DialogTrigger as-child>
            <Button type="button" aria-label="Import source" size="sm">
              <Link class="size-4" />
              Import
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Import source</DialogTitle>
              <DialogDescription>
                Binds an existing global source to this project.
              </DialogDescription>
            </DialogHeader>
            <div class="grid gap-4">
              <div class="grid gap-2">
                <Label for="source-pick">Source</Label>
                <Input
                  id="source-pick"
                  default-value="Select from global source library"
                />
                <p class="text-xs leading-5 text-muted-foreground">
                  No source creation here. Create and index source items from
                  global Sources.
                </p>
              </div>
              <div
                class="grid grid-cols-[24px_minmax(0,1fr)] gap-3 rounded-lg border border-primary/30 bg-primary/10 p-3"
              >
                <span class="mt-1 size-2 rounded-full bg-primary"></span>
                <div>
                  <strong class="text-sm">Binding only</strong>
                  <p class="mt-1 text-xs leading-5 text-muted-foreground">
                    Import calls the project-source binding API and does not
                    change source content.
                  </p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                aria-label="Cancel import source"
                variant="outline"
              >
                Cancel
              </Button>
              <Button type="button" aria-label="Confirm import source">
                Import
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>

    <!-- 数据源列表表格 -->
    <Table class="console-scrollbar">
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Visibility</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last synced</TableHead>
          <TableHead class="w-16 text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <!-- 数据源行：PDF 文档 -->
        <TableRow>
          <TableCell>
            <strong>Product docs PDF</strong>
          </TableCell>
          <TableCell>Local file</TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
              >Public</Badge
            >
          </TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
              >Indexed</Badge
            >
          </TableCell>
          <TableCell>12 minutes ago</TableCell>
          <TableCell class="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  aria-label="Product docs source actions"
                  variant="outline"
                  size="icon-sm"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <ExternalLink class="size-4" />
                  Open source
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                >
                  <Unlink class="size-4" />
                  Unbind
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
        <!-- 数据源行：网页爬取 -->
        <TableRow>
          <TableCell>
            <strong>Main website pages</strong>
          </TableCell>
          <TableCell>Web crawl</TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
              >Public</Badge
            >
          </TableCell>
          <TableCell>
            <Badge class="border-yellow-300/25 bg-yellow-300/10 text-yellow-100"
              >Processing</Badge
            >
          </TableCell>
          <TableCell>about 1 hour ago</TableCell>
          <TableCell class="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  aria-label="Main website source actions"
                  variant="outline"
                  size="icon-sm"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <ExternalLink class="size-4" />
                  Open source
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                >
                  <Unlink class="size-4" />
                  Unbind
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
        <TableRow>
          <TableCell>
            <strong>Release notes</strong>
          </TableCell>
          <TableCell>Markdown</TableCell>
          <TableCell>
            <Badge variant="outline">Private</Badge>
          </TableCell>
          <TableCell>
            <Badge
              class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
              >Indexed</Badge
            >
          </TableCell>
          <TableCell>yesterday</TableCell>
          <TableCell class="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  aria-label="Release notes source actions"
                  variant="outline"
                  size="icon-sm"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <ExternalLink class="size-4" />
                  Open source
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                >
                  <Unlink class="size-4" />
                  Unbind
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
