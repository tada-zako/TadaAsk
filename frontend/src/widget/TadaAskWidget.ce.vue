<script setup lang="ts">
import { ref, toRef } from "vue";

import { useWidgetChat } from "./composables/use-widget-chat";
import WidgetLauncher from "./components/WidgetLauncher.vue";
import WidgetPanel from "./components/WidgetPanel.vue";

// web component 标签属性传递
const props = withDefaults(
  defineProps<{
    apiBaseUrl?: string;
    projectUid?: string;
    widgetUid?: string;
    title?: string;
    logoUrl?: string;
    placeholder?: string;
    launcherPosition?: "bottom-left" | "bottom-right";
    panelAlign?: "left" | "center" | "right";
  }>(),
  {
    apiBaseUrl: "",
    projectUid: "",
    widgetUid: "",
    title: "TadaAsk Assistant",
    logoUrl: "",
    placeholder: "Ask anything…",
    launcherPosition: "bottom-right",
    panelAlign: "right",
  },
);

// Panel 显隐不影响 chat composable，关闭时 SSE 仍会继续消费。
const isOpen = ref(false);
const chat = useWidgetChat({
  apiBaseUrl: toRef(props, "apiBaseUrl"),
  projectUid: toRef(props, "projectUid"),
  widgetUid: toRef(props, "widgetUid"),
});
</script>

<template>
  <div
    class="widget-root"
    :class="[
      `launcher-${launcherPosition}`,
      `panel-${panelAlign}`,
      { 'panel-open': isOpen },
    ]"
  >
    <WidgetLauncher
      v-show="!isOpen"
      :label="`Open ${title}`"
      @open="isOpen = true"
    />
    <WidgetPanel
      v-show="isOpen"
      :title="title"
      :logo-url="logoUrl"
      :placeholder="placeholder"
      :messages="chat.messages.value"
      :draft="chat.draft.value"
      :phase="chat.phase.value"
      :can-send="chat.canSend.value"
      :error-message="chat.errorMessage.value"
      @update:draft="chat.draft.value = $event"
      @close="isOpen = false"
      @new-chat="chat.startNewChat"
      @send="chat.sendMessage"
      @cancel="chat.cancelGeneration"
      @dismiss-error="chat.dismissError"
    />
  </div>
</template>

<!-- Custom Element 模式会将处理后的 Tailwind CSS 注入当前 Shadow Root。 -->
<style src="./styles/widget.css"></style>
