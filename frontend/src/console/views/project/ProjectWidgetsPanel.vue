<script setup lang="ts">
import { Ellipsis, Pencil, Plus, Trash2 } from "@lucide/vue";

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
import { Switch } from "@/shared/components/ui/switch";
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
  <!-- Widget 部署管理面板 -->
  <section class="console-table-panel">
    <!-- 面板头部操作栏 -->
    <div
      class="flex min-h-12 items-center justify-between gap-4 border-b border-(--line-soft) px-4 max-[760px]:items-start max-[760px]:py-3"
    >
      <p class="text-xs text-(--text-faint)">2 deployments</p>
      <!-- 创建 Widget 对话框 -->
      <Dialog>
        <DialogTrigger as-child>
          <Button type="button" aria-label="Create widget" size="sm">
            <Plus class="size-4" />
            Create
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create widget</DialogTitle>
            <DialogDescription>
              Creates a ProjectWidget deployment instance.
            </DialogDescription>
          </DialogHeader>
          <div class="grid gap-4">
            <!-- Widget 名称 -->
            <div class="grid gap-2">
              <Label for="widget-name">Widget name</Label>
              <Input id="widget-name" default-value="Docs production" />
            </div>
            <!-- 部署站点域名 -->
            <div class="grid gap-2">
              <Label for="site-origin">Site origin</Label>
              <Input
                id="site-origin"
                default-value="https://docs.example.com"
              />
              <p class="text-muted-foreground text-xs leading-5">
                Normalized origin used by project/widget scoped CORS checks.
              </p>
            </div>
            <!-- 启用状态开关 -->
            <div class="flex items-start gap-3">
              <Switch
                :default-value="true"
                aria-label="Enable widget after creation"
              />
              <div class="grid gap-1">
                <strong class="text-sm">Enabled</strong>
                <span class="text-muted-foreground text-xs">
                  Visitor widget requests are allowed from this origin.
                </span>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              aria-label="Cancel widget creation"
              variant="outline"
            >
              Cancel
            </Button>
            <Button type="button" aria-label="Confirm create widget">
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

    <!-- Widget 部署列表表格 -->
    <Table class="console-scrollbar">
      <TableHeader>
        <TableRow>
          <TableHead>Widget</TableHead>
          <TableHead>Site origin</TableHead>
          <TableHead>Enabled</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Updated</TableHead>
          <TableHead class="w-16 text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <!-- 部署项：生产环境 -->
        <TableRow>
          <TableCell>
            <strong>Docs production</strong>
          </TableCell>
          <TableCell>https://docs.example.com</TableCell>
          <TableCell>
            <Switch
              :default-value="true"
              aria-label="Docs production widget enabled"
            />
          </TableCell>
          <TableCell>2026-06-02</TableCell>
          <TableCell>2026-06-27</TableCell>
          <TableCell class="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  aria-label="Docs production widget actions"
                  variant="outline"
                  size="icon-sm"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <Pencil class="size-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem>Disable</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                >
                  <Trash2 class="size-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
        <!-- 部署项：本地预览 -->
        <TableRow>
          <TableCell>
            <strong>Local preview</strong>
          </TableCell>
          <TableCell>http://localhost:4321</TableCell>
          <TableCell>
            <Switch
              :default-value="false"
              aria-label="Local preview widget disabled"
            />
          </TableCell>
          <TableCell>2026-06-14</TableCell>
          <TableCell>2026-06-22</TableCell>
          <TableCell class="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  aria-label="Local preview widget actions"
                  variant="outline"
                  size="icon-sm"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <Pencil class="size-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem>Enable</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                >
                  <Trash2 class="size-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
