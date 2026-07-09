<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import ChatSessionsPanel from "@/console/components/chat/ChatSessionsPanel.vue";
import ChatThreadPanel from "@/console/components/chat/ChatThreadPanel.vue";
import { useGlobalChatStore } from "@/console/stores/global-chat";

const route = useRoute();
const router = useRouter();
const globalChatStore = useGlobalChatStore();
const { activeRouteSessionUid, isBootstrapping } = storeToRefs(globalChatStore);
// 左侧会话面板折叠状态，由 ChatSessionsPanel / ChatThreadPanel 双向控制
const isSessionsPanelCollapsed = ref(false);

// 页面挂载时根据 URL query 初始化 store
onMounted(() => {
  void globalChatStore.bootstrap(getRouteSessionUid()).catch(() => undefined);
});

// URL query 变化 → 同步到 store（切换/新建 session）
watch(
  () => route.query.sessionUid,
  (value) => {
    if (isBootstrapping.value) {
      return;
    }

    const sessionUid = normalizeSessionQuery(value);
    if (sessionUid && sessionUid !== activeRouteSessionUid.value) {
      void globalChatStore.selectSession(sessionUid).catch(() => undefined);
      return;
    }

    if (!sessionUid && activeRouteSessionUid.value) {
      globalChatStore.startNewSession();
    }
  },
);

// store 中真实 active session uid 变化 → 同步到 URL query
watch(activeRouteSessionUid, (sessionUid) => {
  if (getRouteSessionUid() === sessionUid) {
    return;
  }

  void router.replace({
    name: "chat",
    query: sessionUid ? { sessionUid } : {},
  });
});

function getRouteSessionUid(): string | null {
  return normalizeSessionQuery(route.query.sessionUid);
}

// 规范化 query 参数：支持 string / string[] 两种形式
function normalizeSessionQuery(value: unknown): string | null {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" && value[0] ? value[0] : null;
  }

  return typeof value === "string" && value ? value : null;
}
</script>

<template>
  <!-- 全局聊天视图：sessions 面板绝对定位叠加 + thread 全宽，通过 translate-x 控制显隐 -->
  <section
    class="relative h-[calc(100dvh-var(--console-header-height))] min-h-0 overflow-hidden bg-(--surface-base)"
  >
    <!-- sessions 面板：绝对定位，折叠时 translate-x 滑出视口 -->
    <ChatSessionsPanel
      :collapsed="isSessionsPanelCollapsed"
      class="absolute top-0 left-0 z-20 h-full w-[228px] transition-transform duration-[880ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none max-[900px]:hidden"
      :aria-hidden="isSessionsPanelCollapsed"
      :class="
        isSessionsPanelCollapsed
          ? 'pointer-events-none -translate-x-full'
          : 'translate-x-0'
      "
      @collapse="isSessionsPanelCollapsed = true"
    />
    <ChatThreadPanel
      class="h-full w-full"
      :sessions-collapsed="isSessionsPanelCollapsed"
      @expand-sessions="isSessionsPanelCollapsed = false"
    />
  </section>
</template>
