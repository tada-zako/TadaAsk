<script setup lang="ts">
// 浮动启动按钮，点击后展开 Widget 面板
import { MessageSquareText } from "@lucide/vue";
</script>

<template>
  <button
    class="widget-launcher"
    type="button"
    aria-label="Open TadaAsk Assistant"
  >
    <MessageSquareText aria-hidden="true" />
  </button>
</template>
