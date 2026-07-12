<script setup lang="ts">
import { toRef } from "vue";

import { useWidgetChat } from "./composables/use-widget-chat";
import { useWidgetShell } from "./composables/use-widget-shell";
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

const shell = useWidgetShell(); // 记录 message panel 的状态
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
      { 'panel-open': shell.isOpen.value },
    ]"
  >
    <WidgetLauncher
      v-show="!shell.isOpen.value"
      :label="`Open ${title}`"
      @open="shell.open"
    />
    <WidgetPanel
      v-show="shell.isOpen.value"
      :title="title"
      :logo-url="logoUrl"
      :placeholder="placeholder"
      :messages="chat.messages.value"
      :draft="chat.draft.value"
      :phase="chat.phase.value"
      :can-send="chat.canSend.value"
      :error-message="chat.errorMessage.value"
      @update:draft="chat.draft.value = $event"
      @close="shell.close"
      @new-chat="chat.startNewChat"
      @send="chat.sendMessage"
      @cancel="chat.cancelGeneration"
      @dismiss-error="chat.dismissError"
    />
  </div>
</template>

<!-- Custom Element 模式会将处理后的 Tailwind CSS 注入当前 Shadow Root。 -->
<style src="./styles/widget.css"></style>
