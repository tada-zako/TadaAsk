<script setup lang="ts">
import { MessageSquareText, Plus, X } from "@lucide/vue";
import { ref, watch } from "vue";

import { useWidgetAutoScroll } from "../composables/use-widget-auto-scroll";
import type { WidgetChatPhase } from "../composables/use-widget-chat";
import type { WidgetMessageViewModel } from "../services/chat";
import WidgetComposer from "./WidgetComposer.vue";
import WidgetMessageList from "./WidgetMessageList.vue";

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
const { handleScroll, scrollToLatest } = useWidgetAutoScroll(scrollContainer);

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
        <div><span>Powered by</span><i>T</i><strong>TadaAsk</strong></div>
      </footer>
    </section>
  </div>
</template>
