<script setup lang="ts">
import { MessageSquareText, Plus, X } from "@lucide/vue";
import { nextTick, ref, watch } from "vue";

import type { WidgetChatPhase } from "../composables/use-widget-chat";
import type { WidgetMessageViewModel } from "../services/chat";
import WidgetComposer from "./WidgetComposer.vue";
import WidgetMessageList from "./WidgetMessageList.vue";

// TODO: 官方站点 URL 确认前先指向项目仓库；后续只需替换这一处。
const TADAASK_HOME_URL = "https://github.com/tada-zako/TadaAsk";

const props = withDefaults(
  defineProps<{
    title?: string;
    logoUrl?: string;
    placeholder?: string;
    messages: WidgetMessageViewModel[];
    draft?: string;
    phase: WidgetChatPhase;
    canSend?: boolean;
    errorMessage?: string | null;
  }>(),
  {
    title: "TadaAsk Assistant",
    logoUrl: "",
    placeholder: "Ask anything…",
    draft: "",
    canSend: false,
    errorMessage: null,
  },
);

const emit = defineEmits<{
  close: [];
  newChat: [];
  send: [];
  cancel: [];
  dismissError: [];
  "update:draft": [value: string];
}>();

const scrollContainer = ref<HTMLElement | null>(null);
const emptyComposerRef = ref<InstanceType<typeof WidgetComposer> | null>(null);
const dockComposerRef = ref<InstanceType<typeof WidgetComposer> | null>(null);
const followsOutput = ref(true);
const BOTTOM_THRESHOLD = 72;

/** 监听滚动事件 */
function handleScroll() {
  const element = scrollContainer.value;
  if (!element) return;
  followsOutput.value =
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    BOTTOM_THRESHOLD;
}

/** 滚动到最底部 */
async function scrollToLatest() {
  if (!followsOutput.value) return;
  await nextTick();
  const element = scrollContainer.value;
  if (element) element.scrollTop = element.scrollHeight;
}

watch(
  () => props.messages.length,
  (messageCount) => {
    // New Chat 清空消息后，新会话应重新跟随输出。
    if (messageCount === 0) followsOutput.value = true;
  },
);

watch(
  () => [
    props.messages.length,
    props.messages.at(-1)?.content.length ?? 0,
    props.phase,
  ],
  () => void scrollToLatest(),
  { flush: "post" },
);

const busyPhases: WidgetChatPhase[] = [
  "connecting",
  "thinking",
  "streaming",
  "cancelling",
];

/** 聚焦当前实际渲染的 composer，避免 v-if 切换后焦点落到宿主页面。 */
async function focusComposer() {
  await nextTick();
  const composer = props.messages.length
    ? dockComposerRef.value
    : emptyComposerRef.value;
  composer?.focus({ preventScroll: true });
}

// 继续向上传递 composer.textarea 的聚焦操作
defineExpose({ focusComposer });
</script>

<template>
  <div class="panel-layer">
    <button
      class="mobile-dismiss-area"
      type="button"
      aria-label="Close assistant"
      @click="$emit('close')"
    ></button>

    <section class="widget-panel" aria-label="TadaAsk Assistant">
      <!-- chat panel header -->
      <header class="panel-header">
        <div class="panel-brand">
          <img v-if="logoUrl" class="panel-logo-image" :src="logoUrl" alt="" />
          <span v-else class="panel-logo">T</span>
          <strong>{{ title }}</strong>
        </div>
        <!-- 关闭 panel 以及 new session 按钮 -->
        <div class="panel-actions">
          <button
            type="button"
            aria-label="Start a new chat"
            @click="$emit('newChat')"
          >
            <Plus aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Close assistant"
            @click="$emit('close')"
          >
            <X aria-hidden="true" />
          </button>
        </div>
      </header>

      <!-- message list -->
      <main class="panel-content">
        <!-- empty message 展示内容 -->
        <section v-if="!messages.length" class="panel-state state-empty">
          <div class="empty-center">
            <div class="empty-welcome">
              <span><MessageSquareText aria-hidden="true" /></span>
              <h2>How can I help?</h2>
              <p>Ask a question about this site.</p>
            </div>
            <WidgetComposer
              ref="emptyComposerRef"
              compact
              :model-value="draft"
              :placeholder="placeholder"
              :can-send="canSend"
              @update:model-value="$emit('update:draft', $event)"
              @send="$emit('send')"
            />
          </div>
        </section>

        <!-- history messages 展示 -->
        <section
          v-else
          ref="scrollContainer"
          class="panel-state messages-scroll"
          @scroll="handleScroll"
        >
          <WidgetMessageList :messages="messages" />
        </section>

        <!-- 错误提示 -->
        <div v-if="errorMessage" class="widget-error" role="status">
          <span>{{ errorMessage }}</span>
          <button
            type="button"
            aria-label="Dismiss error"
            @click="$emit('dismissError')"
          >
            Dismiss
          </button>
        </div>

        <div v-if="messages.length" class="composer-dock">
          <WidgetComposer
            ref="dockComposerRef"
            :model-value="draft"
            :placeholder="placeholder"
            :busy="busyPhases.includes(phase)"
            :cancelling="phase === 'cancelling'"
            :can-send="canSend"
            @update:model-value="$emit('update:draft', $event)"
            @send="$emit('send')"
            @cancel="$emit('cancel')"
          />
        </div>
      </main>

      <footer class="panel-footer">
        <a
          :href="TADAASK_HOME_URL"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Visit TadaAsk"
        >
          <span>Powered by</span><i>T</i><strong>TadaAsk</strong>
        </a>
      </footer>
    </section>
  </div>
</template>
