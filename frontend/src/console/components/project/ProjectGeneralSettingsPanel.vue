<script setup lang="ts">
import { Copy } from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
</script>

<template>
  <!-- 项目通用设置面板：名称、描述、项目 ID 等基础信息 -->
  <section class="console-section">
    <header class="grid gap-1 px-0.5">
      <h2 class="text-xl leading-[1.35] font-bold text-(--text-strong)">
        General
      </h2>
      <p class="text-xs leading-5 text-(--text-faint)">
        Basic project information used throughout the console.
      </p>
    </header>

    <section class="console-panel overflow-hidden">
      <div class="grid gap-5 p-5">
        <div class="grid gap-2">
          <Label for="project-settings-name" class="text-[13px] font-semibold">
            Project name
          </Label>
          <Input
            id="project-settings-name"
            default-value="Docs Assistant"
            class="h-10 border-(--line) bg-black/20 text-[13px] shadow-none"
          />
          <p class="text-xs leading-5 text-(--text-faint)">
            Must be unique. This name appears in the project switcher.
          </p>
        </div>

        <div class="grid gap-2">
          <Label
            for="project-settings-description"
            class="text-[13px] font-semibold"
          >
            Description
          </Label>
          <Textarea
            id="project-settings-description"
            default-value="Answers product and integration questions using the TadaAsk documentation."
            class="min-h-22 border-(--line) bg-black/20 text-[13px] leading-6 shadow-none"
          />
          <p class="text-xs leading-5 text-(--text-faint)">
            Optional context for admins. It is not included in visitor prompts.
          </p>
        </div>

        <div class="grid gap-2">
          <Label for="project-settings-id" class="text-[13px] font-semibold">
            Project ID
          </Label>
          <div class="flex min-w-0">
            <Input
              id="project-settings-id"
              default-value="9ee2c42c-9074-4b82-a0b8-0fb441fc1c12"
              readonly
              class="h-10 min-w-0 rounded-r-none border-(--line) bg-black/20 font-mono text-xs text-(--text-muted) shadow-none"
            />
            <Button
              type="button"
              aria-label="Copy project ID"
              variant="outline"
              class="h-10 rounded-l-none border-l-0 border-(--line) bg-(--surface-raised) px-3 text-xs text-(--text-muted)"
            >
              <Copy class="size-3.5" />
              Copy
            </Button>
          </div>
          <p class="text-xs leading-5 text-(--text-faint)">
            Stable identifier used by project-scoped APIs and widgets.
          </p>
        </div>
      </div>

      <footer
        class="flex min-h-15 items-center justify-between gap-4 border-t border-(--line-soft) bg-black/10 px-4 py-3 pl-5 max-[560px]:flex-col max-[560px]:items-stretch"
      >
        <span class="flex items-center gap-2 text-xs text-(--text-faint)">
          <span class="size-1.5 rounded-full bg-(--text-disabled)"></span>
          Project details are up to date
        </span>
        <Button
          type="button"
          aria-label="Save project changes"
          class="max-[560px]:w-full"
        >
          Save changes
        </Button>
      </footer>
    </section>
  </section>
</template>
