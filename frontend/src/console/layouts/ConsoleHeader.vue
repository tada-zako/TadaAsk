<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";
import { ChevronRight } from "@lucide/vue";

import { useProjectStore } from "@/console/stores/project";

// 面包屑导航项接口
interface BreadcrumbItem {
  key: string;
  label: string;
  active?: boolean; // 当前所在的导航选项
  loading?: boolean;
  navigate?: () => Promise<void>;
}

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const projectStore = useProjectStore();
const { selectedProject } = storeToRefs(projectStore);

// 从当前路由参数中提取项目 UID
const routeProjectUid = computed(() => getProjectUidFromRoute());
// 如果当前选中的项目与路由参数一致，则获取项目名称
const routeProjectName = computed(() =>
  selectedProject.value?.uid === routeProjectUid.value
    ? selectedProject.value.name
    : null,
);

// 动态计算面包屑导航项
const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const items: BreadcrumbItem[] = [
    // 首页
    {
      key: "console",
      label: t("shell.breadcrumb.console"),
      navigate: goProjectLanding,
    },
  ];

  // 全局聊天页面
  if (route.name === "chat") {
    items.push({
      active: true,
      key: "chat",
      label: t("shell.breadcrumb.chat"),
    });
    return items;
  }

  // 全局 Sources 页面与 SourceItem 工作区
  if (
    route.name === "sources" ||
    route.name === "source-local-file-items" ||
    route.name === "source-web-crawl-items"
  ) {
    items.push({
      active: route.name === "sources",
      key: "sources",
      label: t("shell.breadcrumb.sources"),
      navigate: route.name === "sources" ? undefined : goSources,
    });

    if (route.name === "source-local-file-items") {
      items.push({
        active: true,
        key: "source-local-file-items",
        label: t("shell.breadcrumb.localFileItems"),
      });
    }

    if (route.name === "source-web-crawl-items") {
      items.push({
        active: true,
        key: "source-web-crawl-items",
        label: t("shell.breadcrumb.webCrawlItems"),
      });
    }

    return items;
  }

  // project 相关页面配置
  items.push({
    key: "project",
    label: t("shell.breadcrumb.project"),
    navigate: goProjectLanding,
  });

  if (!routeProjectUid.value) {
    items[items.length - 1].active = true;
    return items;
  }

  items.push({
    active: route.name === "project-overview",
    key: "project-name",
    label: routeProjectName.value ?? "",
    loading: !routeProjectName.value,
    navigate: route.name === "project-overview" ? undefined : goProjectOverview,
  });

  if (route.name === "project-ask") {
    items.push({ active: true, key: "ask", label: t("shell.breadcrumb.ask") });
  }

  if (route.name === "project-settings") {
    items.push({
      active: true,
      key: "settings",
      label: t("shell.breadcrumb.settings"),
    });
  }

  return items;
});

// 跳转至项目 Landing 页
async function goProjectLanding() {
  await router.push({ name: "project-landing" });
}

async function goSources() {
  await router.push({ name: "sources" });
}

// 跳转至项目概览页
async function goProjectOverview() {
  if (!routeProjectUid.value) {
    await goProjectLanding();
    return;
  }

  await router.push({
    name: "project-overview",
    params: { projectUid: routeProjectUid.value },
  });
}

// 辅助函数：从路由参数中安全提取项目 UID
function getProjectUidFromRoute(): string | null {
  const value = route.params.projectUid;

  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : null;
  }

  return typeof value === "string" && value ? value : null;
}
</script>

<template>
  <!-- 控制台顶部导航栏 -->
  <header
    class="bg-background/80 sticky top-0 z-30 grid min-h-(--console-header-height) grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center border-b border-(--line-soft) px-7 backdrop-blur-lg max-[760px]:grid-cols-[minmax(0,1fr)_auto] max-[760px]:px-4"
  >
    <nav
      class="col-start-2 flex max-w-[min(54vw,42rem)] min-w-0 items-center justify-self-center text-xs max-[760px]:col-start-1 max-[760px]:max-w-[calc(100vw-5.5rem)] max-[760px]:justify-self-start"
      aria-label="Breadcrumb"
    >
      <ol class="flex min-w-0 items-center gap-1 overflow-hidden">
        <li
          v-for="(item, index) in breadcrumbs"
          :key="item.key"
          class="flex min-w-0 items-center gap-1"
        >
          <ChevronRight
            v-if="index > 0"
            class="size-3.5 shrink-0 text-(--text-disabled)"
          />

          <span
            v-if="item.loading"
            class="tadaask-skeleton h-3 w-24 shrink-0 rounded-sm"
          ></span>
          <button
            v-else-if="item.navigate && !item.active"
            type="button"
            :aria-label="t('shell.breadcrumb.open', { label: item.label })"
            class="min-w-0 truncate rounded-(--console-radius-xs) px-1 py-0.5 text-(--text-muted) transition hover:bg-(--surface-hover) hover:text-(--text-body)"
            @click="item.navigate"
          >
            {{ item.label }}
          </button>
          <span
            v-else
            class="min-w-0 truncate px-1 py-0.5 font-semibold text-(--text-strong)"
          >
            {{ item.label }}
          </span>
        </li>
      </ol>
    </nav>

    <!-- 用户信息 -->
    <div
      class="col-start-3 flex items-center justify-end gap-2 text-xs text-(--text-muted) max-[760px]:col-start-2"
    >
      <span class="max-[520px]:hidden">admin</span>
      <div
        class="grid size-7 place-items-center rounded-full border border-(--line-soft) bg-(--surface-panel) text-xs font-semibold text-(--text-body)"
      >
        A
      </div>
    </div>
  </header>
</template>
