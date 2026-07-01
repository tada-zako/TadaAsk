<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";
import {
  BarChart3,
  Check,
  ChevronDown,
  Database,
  KeyRound,
  Languages,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Monitor,
  Moon,
  Plus,
  Settings,
  Sparkles,
  SquareDashed,
  Sun,
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
import { setConsoleLocale, type ConsoleLocale } from "@/console/i18n";
import { useAuthStore } from "@/console/stores/auth";
import { useProjectStore } from "@/console/stores/project";

// 解包响应式对象
const route = useRoute();
const router = useRouter();
const { locale, t } = useI18n();
const authStore = useAuthStore();
const projectStore = useProjectStore();
const { projects, selectedProject } = storeToRefs(projectStore);

// 项目首字作为 selector 标识显示。
const projectInitial = computed(
  () => selectedProject.value?.name.charAt(0) ?? "+",
);

onMounted(async () => {
  if (!getProjectUidFromRoute()) {
    // 当前路由没有指定选中的 project，加载 projects 列表
    await projectStore.loadProjects();
  }
});

// 监听路由参数中的项目 UID 变化，保持侧栏选中状态与路由一致
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

// 选择并切换当前项目
async function selectProject(projectUid: string) {
  await projectStore.selectProject(projectUid);
  await router.push({
    name: "project-overview",
    params: { projectUid },
  });
}

// 判断项目是否处于激活状态
function isProjectActive(projectUid: string): boolean {
  return selectedProject.value?.uid === projectUid;
}

// 打开项目 Landing 页面
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

// 打开项目的子功能页面（如 Ask 或 Settings）
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

// 退出登录
async function signOut() {
  authStore.logout();
  await router.replace({ name: "login" });
}

// 切换控制台语言
function selectLocale(nextLocale: ConsoleLocale) {
  setConsoleLocale(nextLocale);
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
    class="sticky top-0 flex h-screen flex-col overflow-hidden border-r border-(--line-soft) bg-(--surface-shell)/95 px-3.5 pt-4 backdrop-blur-xl max-[760px]:hidden"
  >
    <!-- Logo 区域 -->
    <div class="mb-5 flex h-10 items-center gap-2 px-2">
      <div
        class="text-primary grid size-7 place-items-center rounded-(--console-radius-md) border border-(--line-soft) bg-(--surface-panel) text-sm font-bold"
      >
        T
      </div>
      <strong class="text-sm font-semibold max-[1180px]:hidden">
        {{ t("shell.appName") }}
      </strong>
    </div>

    <!-- 项目切换下拉菜单 -->
    <DropdownMenu>
      <!-- 项目切换菜单触发器 -->
      <DropdownMenuTrigger as-child>
        <Button
          type="button"
          :aria-label="t('shell.sidebar.switchProject')"
          variant="outline"
          class="mb-5 h-13 w-full justify-start gap-2 rounded-(--console-radius-lg) border-(--line-soft) bg-(--surface-panel) px-2.5 text-left hover:border-(--line) hover:bg-(--surface-hover) max-[1180px]:h-11 max-[1180px]:justify-center"
        >
          <span
            class="bg-primary/15 text-primary grid size-8 shrink-0 place-items-center rounded-(--console-radius-md) text-sm font-bold"
          >
            {{ projectInitial }}
          </span>
          <span class="min-w-0 flex-1 max-[1180px]:hidden">
            <span class="block text-[10px] font-normal text-(--text-faint)/75">
              {{ t("shell.sidebar.currentProject") }}
            </span>
            <span
              class="block truncate text-[13px] font-semibold text-(--text-strong)"
            >
              {{ selectedProject?.name ?? t("shell.sidebar.projectHome") }}
            </span>
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
          >{{ t("shell.sidebar.projects") }}</DropdownMenuLabel
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
          {{ t("shell.sidebar.noProject") }}
        </DropdownMenuItem>
        <DropdownMenuSeparator class="my-1 bg-(--line-soft)" />
        <DropdownMenuItem
          class="min-h-10 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-semibold text-(--text-body) focus:bg-(--surface-hover) focus:text-(--text-strong)"
          @select="openProjectHome"
        >
          <Plus class="text-primary size-4" />
          <span class="grid gap-0.5">
            <span>{{ t("shell.sidebar.newProject") }}</span>
            <span class="text-[11px] font-normal text-(--text-faint)">
              {{ t("shell.sidebar.returnProjectLanding") }}
            </span>
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>

    <!-- 导航菜单 -->
    <nav
      class="console-scrollbar grid min-h-0 flex-1 content-start gap-5 overflow-y-auto pb-4"
    >
      <section class="grid gap-1">
        <p class="mx-2 h-2 text-[10px] text-transparent uppercase select-none">
          {{ t("shell.sidebar.project") }}
        </p>
        <!-- 项目管理模块 -->
        <a
          class="console-nav-link console-nav-link-active max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
          @click.prevent="openProjectRoot"
        >
          <LayoutDashboard class="text-primary size-4" />
          <span class="min-w-0 flex-1 max-[1180px]:hidden">
            {{
              selectedProject
                ? t("shell.sidebar.overview")
                : t("shell.sidebar.project")
            }}
          </span>
          <ChevronDown
            class="size-4 text-(--text-faint) transition duration-150 max-[1180px]:hidden"
            :class="selectedProject ? 'opacity-100' : 'opacity-0'"
          />
        </a>
        <!-- 子导航 -->
        <Transition
          enter-active-class="overflow-hidden transition-[max-height,opacity,transform] duration-150 ease-out"
          enter-from-class="max-h-0 -translate-y-1 opacity-0"
          enter-to-class="max-h-20 translate-y-0 opacity-100"
          leave-active-class="overflow-hidden transition-[max-height,opacity,transform] duration-150 ease-in"
          leave-from-class="max-h-20 translate-y-0 opacity-100"
          leave-to-class="max-h-0 -translate-y-1 opacity-0"
        >
          <div
            v-if="selectedProject"
            class="ml-7 grid gap-1 border-l border-(--line-soft) pl-2 max-[1180px]:hidden"
          >
            <a
              class="flex min-h-8 items-center rounded-(--console-radius-sm) px-2 text-[13px] text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
              href="#"
              @click.prevent="openProjectChild('ask')"
            >
              {{ t("shell.sidebar.ask") }}
            </a>
            <a
              class="flex min-h-8 items-center rounded-(--console-radius-sm) px-2 text-[13px] text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
              href="#"
              @click.prevent="openProjectChild('settings')"
            >
              {{ t("shell.sidebar.settings") }}
            </a>
          </div>
        </Transition>

        <!-- 全局 chat item -->
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <MessageSquare class="size-4" />
          <span class="max-[1180px]:hidden">{{ t("shell.sidebar.chat") }}</span>
        </a>
      </section>

      <!-- 数据分析模块 -->
      <section class="grid gap-1">
        <p class="console-nav-title max-[1180px]:hidden">
          {{ t("shell.sidebar.analytics") }}
        </p>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <BarChart3 class="size-4" />
          <span class="max-[1180px]:hidden">
            {{ t("shell.sidebar.conversations") }}
          </span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <Sparkles class="size-4" />
          <span class="max-[1180px]:hidden">
            {{ t("shell.sidebar.topQuestions") }}
          </span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <SquareDashed class="size-4" />
          <span class="max-[1180px]:hidden">
            {{ t("shell.sidebar.sourceAnalytics") }}
          </span>
        </a>
      </section>

      <!-- 系统配置模块 -->
      <section class="grid gap-1">
        <p class="console-nav-title max-[1180px]:hidden">
          {{ t("shell.sidebar.configuration") }}
        </p>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <Database class="size-4" />
          <span class="max-[1180px]:hidden">
            {{ t("shell.sidebar.sources") }}
          </span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <KeyRound class="size-4" />
          <span class="max-[1180px]:hidden">
            {{ t("shell.sidebar.apiKeys") }}
          </span>
        </a>
        <a
          class="console-nav-link max-[1180px]:justify-center max-[1180px]:px-0"
          href="#"
        >
          <Settings class="size-4" />
          <span class="max-[1180px]:hidden">
            {{ t("shell.sidebar.globalSettings") }}
          </span>
        </a>
      </section>
    </nav>

    <!-- 侧边栏底部操作区 -->
    <section
      class="sticky bottom-0 -mx-3.5 border-t border-(--line-soft) bg-(--surface-shell)/95 px-3.5 py-3 backdrop-blur-xl"
    >
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <Button
            type="button"
            :aria-label="t('shell.admin.openMenu')"
            :title="t('shell.admin.settings')"
            variant="outline"
            class="h-11 w-full justify-start gap-2 rounded-(--console-radius-lg) border-(--line-soft) bg-(--surface-panel-soft) px-2.5 text-left hover:border-(--line) hover:bg-(--surface-hover) max-[1180px]:justify-center max-[1180px]:px-0"
          >
            <span
              class="grid size-7 shrink-0 place-items-center rounded-full border border-(--line-soft) bg-(--surface-panel) text-xs font-semibold text-(--text-body)"
            >
              A
            </span>
            <span class="min-w-0 flex-1 max-[1180px]:hidden">
              <span
                class="block truncate text-[13px] font-semibold text-(--text-body)"
              >
                {{ t("shell.admin.name") }}
              </span>
              <span class="block text-[10px] font-normal text-(--text-faint)">
                {{ t("shell.admin.settings") }}
              </span>
            </span>
            <ChevronDown
              class="size-4 text-(--text-faint) max-[1180px]:hidden"
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          side="top"
          class="w-72 rounded-(--console-radius-lg) border-(--line) bg-(--surface-shell) p-1.5 shadow-[0_18px_48px_rgba(0,0,0,0.42)]"
        >
          <DropdownMenuLabel
            class="px-2.5 py-1 text-[10px] font-semibold text-(--text-faint) uppercase"
          >
            {{ t("shell.admin.theme") }}
          </DropdownMenuLabel>
          <DropdownMenuItem
            class="text-primary focus:bg-primary/15 focus:text-primary min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium"
          >
            <Moon class="text-primary size-4" />
            <span class="min-w-0 flex-1">
              {{ t("shell.admin.themes.dark") }}
            </span>
            <Check class="text-primary size-3.5" />
          </DropdownMenuItem>
          <DropdownMenuItem
            class="min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
          >
            <Monitor class="size-4" />
            {{ t("shell.admin.themes.system") }}
          </DropdownMenuItem>
          <DropdownMenuItem
            class="min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
          >
            <Sun class="size-4" />
            {{ t("shell.admin.themes.light") }}
          </DropdownMenuItem>

          <DropdownMenuSeparator class="my-1 bg-(--line-soft)" />
          <DropdownMenuLabel
            class="px-2.5 py-1 text-[10px] font-semibold text-(--text-faint) uppercase"
          >
            {{ t("shell.admin.language") }}
          </DropdownMenuLabel>
          <DropdownMenuItem
            class="min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
            :class="
              locale === 'en'
                ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                : ''
            "
            @select="selectLocale('en')"
          >
            <Languages class="size-4" />
            <span class="min-w-0 flex-1">
              {{ t("shell.admin.languages.en") }}
            </span>
            <Check v-if="locale === 'en'" class="text-primary size-3.5" />
          </DropdownMenuItem>
          <DropdownMenuItem
            class="min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
            :class="
              locale === 'zh-CN'
                ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                : ''
            "
            @select="selectLocale('zh-CN')"
          >
            <Languages class="size-4" />
            <span class="min-w-0 flex-1">
              {{ t("shell.admin.languages.zhCN") }}
            </span>
            <Check v-if="locale === 'zh-CN'" class="text-primary size-3.5" />
          </DropdownMenuItem>

          <DropdownMenuSeparator class="my-1 bg-(--line-soft)" />
          <DropdownMenuItem
            class="min-h-9 rounded-(--console-radius-md) px-2.5 py-2 text-[13px] font-medium text-red-200 focus:bg-red-400/10 focus:text-red-100"
            @select="signOut"
          >
            <LogOut class="size-4 text-red-200" />
            {{ t("shell.admin.signOut") }}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </section>
  </aside>
</template>
