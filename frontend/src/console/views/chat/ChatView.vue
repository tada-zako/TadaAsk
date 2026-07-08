<script setup lang="ts">
import ChatSessionsPanel from "@/console/components/chat/ChatSessionsPanel.vue";
import ChatThreadPanel from "@/console/components/chat/ChatThreadPanel.vue";
</script>

<template>
  <!-- 全局聊天视图：左侧会话列表 + 右侧消息线程，fullBleed 全屏布局 -->
  <section
    class="grid h-[calc(100dvh-var(--console-header-height))] min-h-0 grid-cols-[228px_minmax(0,1fr)] overflow-hidden bg-(--surface-base) max-[900px]:grid-cols-1"
  >
    <ChatSessionsPanel class="max-[900px]:hidden" />
    <ChatThreadPanel />
  </section>
</template>
