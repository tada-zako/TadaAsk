<script setup lang="ts">
import { ExternalLink, FileText, Globe2 } from "@lucide/vue";

import type { RAGSnapshotItem } from "../services/chat";

defineProps<{
  items: RAGSnapshotItem[];
  activeCitationId?: number | null;
}>();

function safeWebUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

// 从 citation 中提取 title
function sourceTitle(item: RAGSnapshotItem) {
  return (
    item.title ||
    item.filename ||
    item.sourceName ||
    `Source ${item.citationId}`
  );
}

// 从 citation 提取 meta 数据
function sourceMeta(item: RAGSnapshotItem) {
  const parts = [item.sourceName];
  if (item.sectionHeader) parts.push(item.sectionHeader);
  if (item.pageNumber != null) parts.push(`Page ${item.pageNumber}`);
  if (safeWebUrl(item.originUrl)) {
    try {
      parts.push(new URL(item.originUrl!).hostname);
    } catch {
      // URL 已通过协议检查，兜底保持 meta 可用
    }
  }
  return parts.filter(Boolean).join(" · ");
}
</script>

<template>
  <section class="sources-panel" aria-label="Sources">
    <header>
      <strong>Sources used in this answer</strong>
      <span>{{ items.length }} references</span>
    </header>

    <!-- citation list -->
    <template v-for="item in items" :key="item.citationId">
      <!-- web crawl source 的网页 page 引用 -->
      <a
        v-if="safeWebUrl(item.originUrl)"
        class="source-row"
        :class="{ 'source-highlighted': activeCitationId === item.citationId }"
        :href="safeWebUrl(item.originUrl) ?? undefined"
        target="_blank"
        rel="noopener noreferrer"
      >
        <span class="source-index">{{ item.citationId }}</span>
        <div class="source-main">
          <div class="source-title">
            <Globe2 aria-hidden="true" /><strong>{{
              sourceTitle(item)
            }}</strong>
          </div>
          <p class="source-meta">{{ sourceMeta(item) }}</p>
        </div>
        <ExternalLink class="source-open" aria-hidden="true" />
      </a>

      <!-- local file source 的文件 citation -->
      <article
        v-else
        class="source-row"
        :class="{ 'source-highlighted': activeCitationId === item.citationId }"
      >
        <span class="source-index">{{ item.citationId }}</span>
        <div class="source-main">
          <div class="source-title">
            <FileText aria-hidden="true" /><strong>{{
              sourceTitle(item)
            }}</strong>
          </div>
          <p v-if="sourceMeta(item)" class="source-meta">
            {{ sourceMeta(item) }}
          </p>
          <p v-if="item.excerpt" class="source-excerpt">{{ item.excerpt }}</p>
        </div>
      </article>
    </template>
  </section>
</template>
