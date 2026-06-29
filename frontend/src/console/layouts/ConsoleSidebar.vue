<script setup lang="ts">
import {
  BarChart3,
  Bot,
  ChevronDown,
  Database,
  KeyRound,
  LayoutDashboard,
  MessageSquare,
  Settings,
  Sparkles,
  SquareDashed,
} from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
</script>

<template>
  <!-- 控制台侧边栏 -->
  <aside
    class="console-scrollbar sticky top-0 h-screen overflow-y-auto border-r border-(--line-soft) bg-(--surface-shell)/95 px-3.5 py-4 backdrop-blur-xl max-[760px]:hidden"
  >
    <!-- Logo 区域 -->
    <div class="mb-5 flex h-10 items-center gap-2 px-2">
      <div
        class="text-primary grid size-7 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel) text-sm font-bold"
      >
        T
      </div>
      <strong class="text-sm font-semibold max-[1180px]:hidden">TadaAsk</strong>
    </div>

    <!-- 项目切换下拉菜单 -->
    <DropdownMenu>
      <DropdownMenuTrigger as-child>
        <Button
          type="button"
          aria-label="Switch project"
          variant="outline"
          class="mb-5 h-13 w-full justify-start gap-2 rounded-(--console-radius-lg) border-(--line-soft) bg-(--surface-panel) px-2.5 text-left hover:bg-(--surface-hover) max-[1180px]:h-11 max-[1180px]:justify-center"
        >
          <span
            class="bg-primary/15 text-primary grid size-8 shrink-0 place-items-center rounded-(--console-radius-md) text-sm font-bold"
          >
            D
          </span>
          <span class="min-w-0 flex-1 max-[1180px]:hidden">
            <span class="block text-[11px] font-normal text-(--text-faint)"
              >Current project</span
            >
            <span
              class="block truncate text-[13px] font-semibold text-(--text-strong)"
              >Docs Assistant</span
            >
          </span>
          <ChevronDown
            class="text-muted-foreground size-4 max-[1180px]:hidden"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" class="w-60">
        <DropdownMenuLabel>Projects</DropdownMenuLabel>
        <DropdownMenuItem>Docs Assistant</DropdownMenuItem>
        <DropdownMenuItem>Support Sandbox</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Create project</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>

    <!-- 导航菜单 -->
    <nav class="grid gap-5">
      <!-- 项目管理模块 -->
      <section class="grid gap-1">
        <p class="mx-2 h-2 text-[10px] text-transparent uppercase select-none">
          Project
        </p>
        <a
          class="console-nav-link console-nav-link-active max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <LayoutDashboard class="text-primary size-4" />
          <span class="min-w-0 flex-1 max-[1180px]:hidden">Project</span>
          <ChevronDown
            class="text-muted-foreground size-4 max-[1180px]:hidden"
          />
        </a>
        <!-- 子导航 -->
        <div
          class="ml-7 grid gap-1 border-l border-(--line-soft) pl-2 max-[1180px]:hidden"
        >
          <a
            class="flex min-h-8 items-center rounded-(--console-radius-sm) px-2 text-[13px] text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
            href="#"
          >
            Ask
          </a>
          <a
            class="flex min-h-8 items-center rounded-(--console-radius-sm) px-2 text-[13px] text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
            href="#"
          >
            Settings
          </a>
        </div>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <MessageSquare class="size-4" />
          <span class="max-[1180px]:hidden">Chat</span>
        </a>
      </section>

      <!-- 数据分析模块 -->
      <section class="grid gap-1">
        <p class="console-nav-title max-[1180px]:hidden">Analytics</p>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <BarChart3 class="size-4" />
          <span class="max-[1180px]:hidden">Conversations</span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <Sparkles class="size-4" />
          <span class="max-[1180px]:hidden">Top Questions</span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <SquareDashed class="size-4" />
          <span class="max-[1180px]:hidden">Source Analytics</span>
        </a>
      </section>

      <!-- 系统配置模块 -->
      <section class="grid gap-1">
        <p class="console-nav-title max-[1180px]:hidden">Configuration</p>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <Database class="size-4" />
          <span class="max-[1180px]:hidden">Sources</span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <KeyRound class="size-4" />
          <span class="max-[1180px]:hidden">API Keys</span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <Settings class="size-4" />
          <span class="max-[1180px]:hidden">Global Settings</span>
        </a>
      </section>

      <section
        class="mt-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-3 max-[1180px]:hidden"
      >
        <div
          class="mb-2 flex items-center gap-2 text-xs font-semibold text-(--text-body)"
        >
          <Bot class="text-primary size-4" />
          MVP analytics
        </div>
        <div class="grid gap-2">
          <div class="tadaask-skeleton h-2.5 w-11/12 rounded-md"></div>
          <div class="tadaask-skeleton h-2.5 w-7/12 rounded-md"></div>
        </div>
      </section>
    </nav>
  </aside>
</template>
