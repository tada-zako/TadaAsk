<script setup lang="ts">
// 导入网页爬取设置抽屉组件
import SourceWebCrawlSettingsSheet from "./SourceWebCrawlSettingsSheet.vue";
</script>

<template>
  <!-- 兼容旧引用；新代码应按 source type 使用独立 settings sheet。 -->
  <SourceWebCrawlSettingsSheet />
</template>
