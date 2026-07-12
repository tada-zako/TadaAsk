<script setup lang="ts">
// 消息输入框，包含普通模式和流式生成中的停止模式
import { ArrowUp, Square } from "@lucide/vue";
</script>

<template>
  <div class="composer-dock">
    <!-- 普通输入模式 -->
    <section
      class="widget-composer composer-normal"
      aria-label="Message composer"
    >
      <textarea aria-label="Message" placeholder="Ask a follow-up…"></textarea>
      <div class="composer-footer">
        <span>Enter to send · Shift + Enter for a new line</span>
        <button type="button" aria-label="Send message">
          <ArrowUp aria-hidden="true" />
        </button>
      </div>
    </section>

    <!-- 流式生成中：输入框禁用，显示停止按钮 -->
    <section
      class="widget-composer composer-streaming"
      aria-label="Message composer"
    >
      <textarea aria-label="Message" disabled>
RAG Snapshot 在流式回答中是怎样工作的？</textarea>
      <div class="composer-footer">
        <span>Generating a response…</span>
        <button class="stop-button" type="button" aria-label="Stop generating">
          <Square aria-hidden="true" />
        </button>
      </div>
    </section>
  </div>
</template>
