<script setup lang="ts">
import WidgetLauncher from "./components/WidgetLauncher.vue";
import WidgetPanel from "./components/WidgetPanel.vue";
</script>

<template>
  <div class="widget-root">
    <WidgetLauncher />
    <WidgetPanel />
  </div>
</template>

<!-- Custom Element 模式会将处理后的 Tailwind CSS 注入当前 Shadow Root。 -->
<style src="./styles/widget.css"></style>
