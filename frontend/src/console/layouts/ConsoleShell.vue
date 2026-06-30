<script setup lang="ts">
import { RouterView } from "vue-router";

import ConsoleHeader from "./ConsoleHeader.vue";
import ConsoleSidebar from "./ConsoleSidebar.vue";
</script>

<template>
  <!-- 控制台外壳容器 -->
  <div class="dark bg-background text-foreground min-h-screen scheme-dark">
    <!-- 渐变背景容器 -->
    <div
      class="min-h-screen bg-[radial-gradient(circle_at_74%_-12%,rgba(36,211,196,0.14),transparent_30rem),linear-gradient(180deg,#09090a_0%,#050505_48rem)]"
    >
      <!-- 网格布局：侧边栏 + 主内容区 -->
      <div
        class="grid min-h-screen grid-cols-[var(--console-sidebar-width)_minmax(0,1fr)] max-[1180px]:grid-cols-[var(--console-sidebar-collapsed-width)_minmax(0,1fr)] max-[760px]:block"
      >
        <ConsoleSidebar />
        <main class="min-w-0">
          <ConsoleHeader />
          <!-- 页面内容插槽容器 -->
          <div
            class="mx-auto grid max-w-340 gap-8 px-(--console-content-x) py-(--console-content-y) max-[760px]:px-4 max-[760px]:py-5"
          >
            <RouterView />
          </div>
        </main>
      </div>
    </div>
  </div>
</template>
