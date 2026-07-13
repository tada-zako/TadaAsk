<script setup lang="ts">
import { computed, onBeforeUnmount } from "vue";

import { renderChatMarkdown } from "@/shared/services/chat-markdown";
import type { WidgetCitationItem } from "../services/chat";

const props = withDefaults(
  defineProps<{
    content?: string;
    streaming?: boolean;
    citationItems?: WidgetCitationItem[];
  }>(),
  { content: "", streaming: false, citationItems: () => [] },
);

const emit = defineEmits<{ openCitation: [citationId: number] }>();

// "Copied" 反馈状态：定时器 + 按钮引用，支持 1.4s 后自动恢复
let resetTimer: ReturnType<typeof setTimeout> | null = null;
let copiedButton: HTMLButtonElement | null = null;

const displayIdByCitationId = computed(
  () =>
    new Map(
      props.citationItems.map((item) => [item.citationId, item.displayId]),
    ),
);

// 将 content 通过共享渲染管道转为安全 HTML，同步传入当前可用的 citation id 集合
const renderedHtml = computed(() =>
  renderChatMarkdown(props.content, {
    citationIds: props.citationItems.map((item) => item.citationId),
    citationAriaLabel: (id) =>
      `Open citation ${displayIdByCitationId.value.get(id) ?? id}`,
    citationLabel: (id) => displayIdByCitationId.value.get(id) ?? id,
    copyCodeLabel: "Copy",
    streaming: props.streaming,
    stripUnknownCitationMarkers: true,
  }),
);

/** 事件委托入口：根据 data 属性分流到 citation 点击或代码复制 */
function handleClick(event: MouseEvent) {
  const target = event.target;
  if (!(target instanceof Element)) return;

  // 处理 citation 点击事件；
  // 通过 widget-message-list 组件传递 event，最终由 widget-sources-list 处理 event
  const citation = target.closest<HTMLButtonElement>("[data-chat-citation-id]");
  if (citation) {
    const id = Number(citation.dataset.chatCitationId);
    if (Number.isSafeInteger(id) && id > 0) emit("openCitation", id);
    return;
  }

  // 处理 copy 点击事件
  const button = target.closest<HTMLButtonElement>("[data-chat-code-copy]");
  const code = button
    ?.closest(".chat-md-code-block")
    ?.querySelector("code")?.textContent;
  if (!button || !code) return;
  void navigator.clipboard?.writeText(code).then(() => markCopied(button));
}

function markCopied(button: HTMLButtonElement) {
  resetCopied();
  copiedButton = button;
  button.dataset.copied = "true";
  button.textContent = "Copied";
  resetTimer = setTimeout(resetCopied, 1400);
}

function resetCopied() {
  if (resetTimer) clearTimeout(resetTimer);
  resetTimer = null;
  if (copiedButton) {
    copiedButton.dataset.copied = "false";
    copiedButton.textContent = "Copy";
  }
  copiedButton = null;
}

// 卸载前清除定时器，避免内存泄漏
onBeforeUnmount(resetCopied);
</script>

<template>
  <div
    class="chat-md"
    :data-streaming="streaming || undefined"
    v-html="renderedHtml"
    @click="handleClick"
  />
</template>
