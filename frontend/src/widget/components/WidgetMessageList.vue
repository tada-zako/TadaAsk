<script setup lang="ts">
import { ChevronDown, ChevronUp } from "@lucide/vue";
import { nextTick, onBeforeUnmount, ref } from "vue";

import type { WidgetMessageViewModel } from "../services/chat";
import WidgetMarkdownRenderer from "./WidgetMarkdownRenderer.vue";
import WidgetSourcesList from "./WidgetSourcesList.vue";

const props = defineProps<{ messages: WidgetMessageViewModel[] }>();

// message list 根模板引用
const messagesRootRef = ref<HTMLElement | null>(null);
// 记录来源面板展开状态的所有 message
const expandedMessageUids = ref(new Set<string>());
// 记录每条消息当前高亮的 citation id
const activeCitationByMessage = ref<Record<string, number | null>>({});
// 高亮动画计时器
let highlightResetTimer: ReturnType<typeof setTimeout> | null = null;

// 切换单条消息的来源面板展开/折叠
function toggleSources(messageUid: string) {
  const next = new Set(expandedMessageUids.value);
  if (next.has(messageUid)) next.delete(messageUid);
  else next.add(messageUid);
  expandedMessageUids.value = next;

  // 关闭 source list 同时，移除高亮状态记录中的对应 message uid
  if (!next.has(messageUid)) {
    activeCitationByMessage.value = {
      ...activeCitationByMessage.value,
      [messageUid]: null,
    };
  }
}

// 用户点击 message 中的 citation 时：高亮指定 citation，若来源面板未展开则自动展开
async function openCitation(messageUid: string, citationId: number) {
  const message = props.messages.find((item) => item.uid === messageUid);
  if (!message || !citationsAreReady(message)) return;

  resetHighlightTimer();
  activeCitationByMessage.value = {
    [messageUid]: citationId,
  };
  if (!expandedMessageUids.value.has(messageUid)) toggleSources(messageUid);

  await nextTick();
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

  // 基于 data-widget-message-uid 标签属性找到对应的 message element
  const messageElement = Array.from(
    messagesRootRef.value?.querySelectorAll<HTMLElement>(
      "[data-widget-message-uid]",
    ) ?? [],
  ).find((element) => element.dataset.widgetMessageUid === messageUid);
  // 进一步查找对应的 source element
  const sourceElement = Array.from(
    messageElement?.querySelectorAll<HTMLElement>(
      "[data-source-citation-id]",
    ) ?? [],
  ).find((element) => Number(element.dataset.sourceCitationId) === citationId);

  // 平滑滚动并设置高亮计时器
  sourceElement?.scrollIntoView({ behavior: "smooth", block: "center" });
  highlightResetTimer = setTimeout(() => {
    activeCitationByMessage.value = {
      ...activeCitationByMessage.value,
      [messageUid]: null,
    };
    highlightResetTimer = null;
  }, 1600);
}

function citationsAreReady(message: WidgetMessageViewModel) {
  return ["completed", "cancelled", "error"].includes(message.status);
}

/** 重置高亮动画计时器 */
function resetHighlightTimer() {
  if (highlightResetTimer) clearTimeout(highlightResetTimer);
  highlightResetTimer = null;
}

onBeforeUnmount(resetHighlightTimer);
</script>

<template>
  <div ref="messagesRootRef" class="messages-list">
    <article
      v-for="message in messages"
      :key="message.uid"
      class="message"
      :class="`message-${message.role}`"
      :data-widget-message-uid="message.uid"
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
        <template
          v-if="citationsAreReady(message) && message.citationItems.length"
        >
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
