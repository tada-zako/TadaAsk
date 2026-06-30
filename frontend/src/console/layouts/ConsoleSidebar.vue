<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import {
  BarChart3,
  Bot,
  Check,
  ChevronDown,
  Database,
  KeyRound,
  LayoutDashboard,
  MessageSquare,
  Plus,
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
import { useProjectStore } from "@/console/stores/project";

// 解包响应式对象
const route = useRoute();
const router = useRouter();
const projectStore = useProjectStore();
const { projects, selectedProject } = storeToRefs(projectStore);

// 项目首字作为 selector 标识显示。
const projectInitial = computed(
  () => selectedProject.value?.name.charAt(0) ?? "T",
);

onMounted(async () => {
  if (!getProjectUidFromRoute()) {
    // 当前路由没有指定选中的 project，加载 projects 列表
    await projectStore.loadProjects();
  }
});

watch(
  () => route.params.projectUid,
  async () => {
    // 以 path param 为准，保证刷新页面和侧栏选中状态一致。
    const projectUid = getProjectUidFromRoute();

    if (!projectUid) {
      // projectUid 不存在或被清空，清楚 Project 选中状态
      projectStore.clearSelection();
      return;
    }

    await projectStore.selectProject(projectUid);
  },
  { immediate: true },
);

// 选择 project
async function selectProject(projectUid: string) {
  await projectStore.selectProject(projectUid);
  await router.push({
    name: "project-overview",
    params: { projectUid },
  });
}

function isProjectActive(projectUid: string): boolean {
  return selectedProject.value?.uid === projectUid;
}

async function openProjectHome() {
  await router.push({ name: "project-landing" });
}

/**
 * 打开当前选中项目的根路由（overview）
 */
async function openProjectRoot() {
  if (!selectedProject.value) {
    await openProjectHome();
    return;
  }

  await selectProject(selectedProject.value.uid);
}

async function openProjectChild(child: "ask" | "settings") {
  if (!selectedProject.value) {
    await openProjectHome();
    return;
  }

  await router.push({
    name: child === "ask" ? "project-ask" : "project-settings",
    params: { projectUid: selectedProject.value.uid },
  });
}

/**
 * 从路由 params 中获取 projectUid
 */
function getProjectUidFromRoute(): string | null {
  const value = route.params.projectUid;

  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : null;
  }

  return typeof value === "string" && value ? value : null;
}
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
      <!-- 项目切换菜单触发器 -->
      <DropdownMenuTrigger as-child>
        <Button
          type="button"
          aria-label="Switch project"
          variant="outline"
          class="mb-5 h-13 w-full justify-start gap-2 rounded-(--console-radius-lg) border-(--line-soft) bg-(--surface-panel) px-2.5 text-left hover:border-(--line) hover:bg-(--surface-hover) max-[1180px]:h-11 max-[1180px]:justify-center"
        >
          <span
            class="bg-primary/15 text-primary grid size-8 shrink-0 place-items-center rounded-(--console-radius-md) text-sm font-bold"
          >
            {{ projectInitial }}
          </span>
          <span class="min-w-0 flex-1 max-[1180px]:hidden">
            <span class="block text-[10px] font-normal text-(--text-faint)/75"
              >Current project</span
            >
            <span
              class="block truncate text-[13px] font-semibold text-(--text-strong)"
              >{{ selectedProject?.name ?? "Project home" }}</span
            >
          </span>
          <ChevronDown
            class="text-muted-foreground size-4 max-[1180px]:hidden"
          />
        </Button>
      </DropdownMenuTrigger>
      <!-- 菜单内容 -->
      <DropdownMenuContent
        align="start"
        class="w-72 rounded-(--console-radius-lg) border-(--line) bg-(--surface-shell) p-1.5 shadow-[0_18px_48px_rgba(0,0,0,0.42)]"
      >
        <DropdownMenuLabel
          class="px-2.5 py-1 text-[10px] font-semibold text-(--text-faint) uppercase"
          >Projects</DropdownMenuLabel
        >
        <DropdownMenuItem
          v-for="project in projects"
          :key="project.uid"
          class="min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
          :class="
            isProjectActive(project.uid)
              ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
              : ''
          "
          @select="selectProject(project.uid)"
        >
          <span class="min-w-0 flex-1 truncate">{{ project.name }}</span>
          <Check
            v-if="isProjectActive(project.uid)"
            class="text-primary size-3.5"
          />
        </DropdownMenuItem>
        <DropdownMenuItem
          v-if="projects.length === 0"
          disabled
          class="px-2.5 py-2 text-[13px] font-normal text-(--text-faint)"
        >
          No project yet
        </DropdownMenuItem>
        <DropdownMenuSeparator class="my-1 bg-(--line-soft)" />
        <DropdownMenuItem
          class="min-h-10 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-semibold text-(--text-body) focus:bg-(--surface-hover) focus:text-(--text-strong)"
          @select="openProjectHome"
        >
          <Plus class="text-primary size-4" />
          <span class="grid gap-0.5">
            <span>New project</span>
            <span class="text-[11px] font-normal text-(--text-faint)">
              Return to project landing
            </span>
          </span>
        </DropdownMenuItem>
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
          @click.prevent="openProjectRoot"
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
            @click.prevent="openProjectChild('ask')"
          >
            Ask
          </a>
          <a
            class="flex min-h-8 items-center rounded-(--console-radius-sm) px-2 text-[13px] text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
            href="#"
            @click.prevent="openProjectChild('settings')"
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
