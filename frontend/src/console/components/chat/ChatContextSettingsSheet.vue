<script setup lang="ts">
import { Database, Settings2 } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Label } from "@/shared/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/shared/components/ui/sheet";
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";
</script>

<template>
  <Sheet>
    <SheetTrigger as-child>
      <Button
        type="button"
        aria-label="Open context settings"
        variant="outline"
        class="h-9 justify-start gap-2 rounded-(--console-radius-lg) border-(--line-soft) bg-transparent text-[13px] font-medium text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
      >
        <Settings2 class="size-4" />
        Context settings
      </Button>
    </SheetTrigger>

    <SheetContent
      class="!right-0 !w-[min(600px,100dvw)] !max-w-[100dvw] min-w-0 gap-0 overflow-hidden border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <SheetHeader class="border-b border-(--line-soft) px-5 py-4">
        <SheetTitle class="text-[15px]">Context settings</SheetTitle>
      </SheetHeader>

      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-5 overflow-y-auto px-5 py-4"
      >
        <!-- 知识库来源选择 -->
        <section class="grid gap-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="text-[13px] font-semibold text-(--text-strong)">
                Sources
              </h2>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                Leave empty to send a normal LLM chat request.
              </p>
            </div>
            <span
              class="rounded-full border border-(--line-soft) px-2 py-1 text-[11px] text-(--text-muted)"
            >
              2 selected
            </span>
          </div>

          <div
            class="console-scrollbar max-h-43 overflow-y-auto rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft)"
          >
            <label
              class="grid min-h-11 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-3 text-[13px]"
            >
              <Checkbox
                :default-value="true"
                aria-label="Select Product docs"
              />
              <span class="min-w-0">
                <span class="block truncate font-medium text-(--text-strong)">
                  Product docs
                </span>
                <span class="block truncate text-[11px] text-(--text-faint)">
                  128 source items
                </span>
              </span>
              <Database class="size-3.5 text-(--text-disabled)" />
            </label>

            <label
              class="grid min-h-11 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-3 text-[13px]"
            >
              <Checkbox
                :default-value="true"
                aria-label="Select Frontend notes"
              />
              <span class="min-w-0">
                <span class="block truncate font-medium text-(--text-strong)">
                  Frontend notes
                </span>
                <span class="block truncate text-[11px] text-(--text-faint)">
                  42 source items
                </span>
              </span>
              <Database class="size-3.5 text-(--text-disabled)" />
            </label>

            <label
              class="grid min-h-11 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-3 text-[13px]"
            >
              <Checkbox aria-label="Select Widget integration" />
              <span class="min-w-0">
                <span class="block truncate font-medium text-(--text-body)">
                  Widget integration
                </span>
                <span class="block truncate text-[11px] text-(--text-faint)">
                  76 source items
                </span>
              </span>
              <Database class="size-3.5 text-(--text-disabled)" />
            </label>

            <label
              class="grid min-h-11 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-3 text-[13px]"
            >
              <Checkbox aria-label="Select API reference" />
              <span class="min-w-0">
                <span class="block truncate font-medium text-(--text-body)">
                  API reference
                </span>
                <span class="block truncate text-[11px] text-(--text-faint)">
                  213 source items
                </span>
              </span>
              <Database class="size-3.5 text-(--text-disabled)" />
            </label>

            <label
              class="grid min-h-11 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-3 text-[13px]"
            >
              <Checkbox aria-label="Select Support archive" />
              <span class="min-w-0">
                <span class="block truncate font-medium text-(--text-body)">
                  Support archive
                </span>
                <span class="block truncate text-[11px] text-(--text-faint)">
                  305 source items
                </span>
              </span>
              <Database class="size-3.5 text-(--text-disabled)" />
            </label>
          </div>
        </section>

        <!-- RAG 检索模式：Fast / Adaptive / Full -->
        <section class="grid gap-3 border-t border-(--line-soft) pt-4">
          <div>
            <h2 class="text-[13px] font-semibold text-(--text-strong)">
              RAG mode
            </h2>
            <p class="mt-1 text-xs leading-5 text-(--text-faint)">
              Controls how much retrieval work is done before answering.
            </p>
          </div>

          <div class="grid gap-2">
            <button
              type="button"
              aria-label="Use fast RAG mode"
              class="border-primary/35 bg-primary/10 grid gap-1 rounded-(--console-radius-lg) border px-3 py-2.5 text-left"
            >
              <span class="text-primary text-[13px] font-semibold">Fast</span>
              <span class="text-xs leading-5 text-(--text-muted)">
                raw FTS + raw vector -> RRF rank -> rerank when enabled.
              </span>
            </button>

            <button
              type="button"
              aria-label="Use adaptive RAG mode"
              class="grid gap-1 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2.5 text-left"
            >
              <span class="text-[13px] font-semibold text-(--text-strong)">
                Adaptive
              </span>
              <span class="text-xs leading-5 text-(--text-faint)">
                Start from raw query and expand only when candidate quality is
                low.
              </span>
            </button>

            <button
              type="button"
              aria-label="Use full RAG mode"
              class="grid gap-1 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2.5 text-left"
            >
              <span class="text-[13px] font-semibold text-(--text-strong)">
                Full
              </span>
              <span class="text-xs leading-5 text-(--text-faint)">
                raw FTS + raw vector + query expansion -> RRF rank -> optional
                rerank.
              </span>
            </button>
          </div>
        </section>

        <!-- 检索增强开关：重排序 / 独立查询改写 -->
        <section class="grid gap-3 border-t border-(--line-soft) pt-4">
          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <Label class="text-[13px]">Rerank retrieved items</Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                Improves order when the selected provider supports rerank.
              </p>
            </div>
            <Switch
              :default-value="true"
              aria-label="Enable rerank retrieved items"
            />
          </div>

          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <Label class="text-[13px]">Standalone query rewrite</Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                Rewrite follow-up questions before retrieval.
              </p>
            </div>
            <Switch
              :default-value="true"
              aria-label="Enable standalone query rewrite"
            />
          </div>
        </section>

        <!-- 管理员自定义 system prompt -->
        <section class="grid gap-2 border-t border-(--line-soft) pt-4">
          <div>
            <Label
              for="admin-system-prompt"
              class="text-[13px] font-semibold text-(--text-strong)"
            >
              Admin system prompt
            </Label>
            <p class="mt-1 text-xs leading-5 text-(--text-faint)">
              Administrator-customized system prompt.
            </p>
          </div>
          <Textarea
            id="admin-system-prompt"
            class="min-h-28 border-(--line-soft) bg-(--surface-base) text-sm"
            default-value="Answer as an internal admin assistant. Prefer concise steps and call out when no source context was used."
          />
        </section>
      </div>
    </SheetContent>
  </Sheet>
</template>
