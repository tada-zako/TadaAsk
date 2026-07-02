<script setup lang="ts">
import SourceCreateSheet from "@/console/components/sources/SourceCreateSheet.vue";
import SourceListPanel from "@/console/components/sources/SourceListPanel.vue";
</script>

<template>
  <!-- 全局数据源管理视图 -->
  <section class="console-page">
    <header
      class="flex items-end justify-between gap-5 max-[760px]:grid max-[760px]:gap-4"
    >
      <div class="console-page-head">
        <p class="console-kicker">Knowledge sources</p>
        <h1 class="console-page-title">Sources</h1>
        <p class="console-page-subtitle">
          Create source containers, review visibility, and open each source item
          workspace when upload, crawl, or indexing work is needed.
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-2 pb-0.5">
        <SourceCreateSheet />
      </div>
    </header>

    <SourceListPanel />
  </section>
</template>
