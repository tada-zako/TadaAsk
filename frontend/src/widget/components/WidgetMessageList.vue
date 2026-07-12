<script setup lang="ts">
import { ChevronDown, ChevronUp } from "@lucide/vue";
import { ref } from "vue";

import type { WidgetMessageViewModel } from "../services/chat";
import WidgetMarkdownRenderer from "./WidgetMarkdownRenderer.vue";
import WidgetSourcesList from "./WidgetSourcesList.vue";

defineProps<{ messages: WidgetMessageViewModel[] }>();

// 记录每条消息的来源面板展开/折叠状态
const expandedMessageUids = ref(new Set<string>());
// 记录每条消息当前高亮的 citation id
const activeCitationByMessage = ref<Record<string, number | null>>({});

// 切换单条消息的来源面板展开/折叠
function toggleSources(messageUid: string) {
  const next = new Set(expandedMessageUids.value);
  if (next.has(messageUid)) next.delete(messageUid);
  else next.add(messageUid);
  expandedMessageUids.value = next;
}

// 用户点击 message 中的 citation 时：高亮指定 citation，若来源面板未展开则自动展开
function openCitation(messageUid: string, citationId: number) {
  activeCitationByMessage.value = {
    ...activeCitationByMessage.value,
    [messageUid]: citationId,
  };
  if (!expandedMessageUids.value.has(messageUid)) toggleSources(messageUid);
}
</script>

<template>
  <div class="messages-list">
    <article
      v-for="message in messages"
      :key="message.uid"
      class="message"
      :class="`message-${message.role}`"
    >
      <!-- user message 渲染 -->
      <div v-if="message.role === 'user'">{{ message.content }}</div>

      <!-- assistant message 渲染 -->
      <template v-else>
        <!-- pending 且无内容：显示思考中动画 -->
        <div
          v-if="message.status === 'pending' && !message.content"
          class="stream-status"
        >
          <i></i><span>Thinking</span>
        </div>

        <!-- 助手正文区：Markdown 渲染 + 流式光标 + 终止/错误提示 -->
        <div class="assistant-copy">
          <WidgetMarkdownRenderer
            :content="message.content"
            :streaming="message.status === 'streaming'"
            :citation-items="message.citationItems"
            @open-citation="openCitation(message.uid, $event)"
          />
          <span
            v-if="message.status === 'streaming'"
            class="typing-caret"
            aria-hidden="true"
          ></span>
          <p v-if="message.status === 'cancelled'" class="message-note">
            Response stopped
          </p>
          <p v-if="message.status === 'error'" class="message-note">
            Response interrupted
          </p>
        </div>

        <!-- 引用来源：展开按钮 + 来源列表 -->
        <template v-if="message.citationItems.length">
          <button
            class="sources-toggle"
            type="button"
            :aria-label="`${expandedMessageUids.has(message.uid) ? 'Close' : 'Open'} ${message.citationItems.length} sources`"
            @click="toggleSources(message.uid)"
          >
            <span>{{ message.citationItems.length }}</span>
            sources
            <ChevronUp
              v-if="expandedMessageUids.has(message.uid)"
              aria-hidden="true"
            />
            <ChevronDown v-else aria-hidden="true" />
          </button>
          <WidgetSourcesList
            v-if="expandedMessageUids.has(message.uid)"
            :items="message.citationItems"
            :active-citation-id="activeCitationByMessage[message.uid]"
          />
        </template>
      </template>
    </article>
  </div>
</template>
