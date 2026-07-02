<script setup lang="ts">
// 导入 Lucide 图标
import { FileText, Settings } from "@lucide/vue";

// 导入 UI 组件
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
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
  <!-- 本地文件数据源的设置抽屉 -->
  <Sheet>
    <SheetTrigger as-child>
      <Button
        type="button"
        aria-label="Open local file source settings"
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
        <SheetTitle class="text-[15px]">Local file settings</SheetTitle>
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
              Edit the container name and visitor visibility for this source.
            </p>
          </div>

          <!-- 数据源名称 -->
          <div class="grid gap-2">
            <Label for="local-source-name">Name</Label>
            <Input id="local-source-name" value="Product docs PDF" />
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
                <FileText class="text-primary size-4" />
                LOCAL FILE
              </span>
              <Badge
                class="border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
              >
                Indexed
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
                Disable while uploading or reviewing imported files.
              </p>
            </div>
            <Switch checked aria-label="Local file source visibility" />
          </div>
        </section>

        <!-- 预留操作区（如保存、删除） -->
        <section class="grid gap-3 border-t border-(--line-soft) pt-4.5">
          <h2 class="console-panel-title">Reserved actions</h2>
          <div class="flex flex-wrap gap-2">
            <Button
              type="button"
              aria-label="Save local file source settings"
              disabled
            >
              Save changes
            </Button>
            <Button
              type="button"
              aria-label="Delete local file source"
              variant="destructive"
              disabled
            >
              Delete source
            </Button>
          </div>
        </section>
      </div>

      <!-- 底部关闭按钮 -->
      <SheetFooter
        class="mt-0 flex-row justify-end border-t border-(--line-soft) p-4.5"
      >
        <SheetClose as-child>
          <Button
            type="button"
            aria-label="Close local file source settings"
            variant="outline"
          >
            Close
          </Button>
        </SheetClose>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>
