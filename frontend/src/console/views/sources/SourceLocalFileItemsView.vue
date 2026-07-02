<script setup lang="ts">
// 导入 source 复用组件
import SourceItemsTablePanel from "@/console/components/sources/SourceItemsTablePanel.vue";
import SourceItemsToolbar from "@/console/components/sources/SourceItemsToolbar.vue";
</script>

<template>
  <!-- 本地文件数据源的文件项管理工作区 -->
  <section class="console-page">
    <!-- 页面头部：展示数据源名称、描述及上传/设置操作 -->
    <header class="flex items-end justify-between gap-5 max-[760px]:grid">
      <div class="console-page-head">
        <p class="console-kicker">Local file source</p>
        <h1 class="console-page-title">Product docs PDF</h1>
        <p class="console-page-subtitle">
          Upload files, review generated source items, and index items when
          ready.
        </p>
      </div>

      <SourceItemsToolbar source-type="local-file" />
    </header>

    <!-- 文件列表及批量操作面板 -->
    <SourceItemsTablePanel source-type="local-file" />
  </section>
</template>
