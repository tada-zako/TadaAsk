<script setup lang="ts">
import { RouterView, useRoute } from "vue-router";

import ConsoleHeader from "./ConsoleHeader.vue";
import ConsoleSidebar from "./ConsoleSidebar.vue";

// 通过 route.meta.fullBleed 控制是否为全屏无内边距布局（如 chat 页面）
const route = useRoute();
</script>

<template>
  <!-- 控制台外壳容器 -->
  <div
    class="dark bg-background text-foreground h-dvh overflow-hidden scheme-dark"
  >
    <!-- 渐变背景容器 -->
    <div
      class="h-full overflow-hidden bg-[radial-gradient(circle_at_74%_-12%,rgba(36,211,196,0.14),transparent_30rem),linear-gradient(180deg,#09090a_0%,#050505_48rem)]"
    >
      <!-- 网格布局：侧边栏 + 主内容区 -->
      <div
        class="grid h-full min-h-0 grid-cols-[var(--console-sidebar-width)_minmax(0,1fr)] max-[1180px]:grid-cols-[var(--console-sidebar-collapsed-width)_minmax(0,1fr)] max-[760px]:block"
      >
        <ConsoleSidebar />
      <!-- fullBleed 模式下禁用主区域滚动，由子页面自行控制 -->
        <main
          class="min-h-0 min-w-0"
          :class="route.meta.fullBleed ? 'overflow-hidden' : 'overflow-y-auto'"
        >
          <ConsoleHeader />
          <!-- 页面内容插槽容器：fullBleed 页面撑满剩余高度，常规页面居中限宽 -->
          <div
            :class="
              route.meta.fullBleed
                ? 'h-[calc(100dvh-var(--console-header-height))] min-h-0 overflow-hidden'
                : 'mx-auto grid max-w-340 gap-8 px-(--console-content-x) py-(--console-content-y) max-[760px]:px-4 max-[760px]:py-5'
            "
          >
            <RouterView />
          </div>
        </main>
      </div>
    </div>
  </div>
</template>
