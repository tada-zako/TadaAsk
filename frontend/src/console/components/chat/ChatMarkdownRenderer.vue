<script setup lang="ts">
import { computed, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";

import { renderChatMarkdown } from "@/shared/services/chat-markdown";
import type { RAGSnapshotItem } from "@/console/services/chat";

import "katex/dist/katex.min.css";
import "./chat-markdown.css";

const props = withDefaults(
  defineProps<{
    /** 待渲染的 Markdown 文本 */
    content?: string;
    /** 是否为流式输出中（用于 CSS 控制光标闪烁等样式） */
    streaming?: boolean;
    /** 当前 message 的 RAG snapshot items */
    citationItems?: RAGSnapshotItem[];
  }>(),
  {
    citationItems: () => [],
    content: "",
    streaming: false,
  },
);

const emit = defineEmits<{
  openCitation: [citationId: number];
}>();

const { t } = useI18n();

/** 当前处于"已复制"状态的按钮引用，同一时刻最多一个 */
let copiedButton: HTMLButtonElement | null = null;
/** 复制状态恢复定时器（1.4s 后按钮文案恢复为"复制"） */
let copiedResetTimer: ReturnType<typeof setTimeout> | null = null;

/** 将 Markdown 转为安全 HTML */
const renderedHtml = computed(() =>
  renderChatMarkdown(props.content, {
    citationAriaLabel: (citationId) =>
      t("chat.markdown.openCitationAria", { id: citationId }),
    citationIds: props.citationItems.map((item) => item.citationId),
    copyCodeLabel: t("chat.markdown.copyCode"),
    streaming: props.streaming,
  }),
);

const copiedCodeLabel = computed(() => t("chat.markdown.copiedCode"));
const copyCodeLabel = computed(() => t("chat.markdown.copyCode"));

/** 事件委托：监听容器内代码复制按钮以及 citation 按钮的点击 */
function handleMarkdownClick(event: MouseEvent) {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }

  // 处理 citation 按钮点击
  const citationButton = target.closest<HTMLButtonElement>(
    "button[data-chat-citation-id]",
  );
  if (citationButton) {
    const citationId = Number(citationButton.dataset.chatCitationId);
    if (Number.isSafeInteger(citationId) && citationId > 0) {
      emit("openCitation", citationId);
    }
    return;
  }

  // 处理 copy 按钮点击
  const copyButton = target.closest<HTMLButtonElement>(
    "button[data-chat-code-copy]",
  );
  if (!copyButton) {
    return;
  }

  const codeBlock = copyButton.closest(".chat-md-code-block");
  const code = codeBlock?.querySelector("code")?.textContent ?? "";
  if (!code) {
    return;
  }

  void navigator.clipboard?.writeText(code).then(() => {
    markCodeCopied(copyButton);
  });
}

/** 标记按钮为"已复制"状态，1.4s 后自动恢复 */
function markCodeCopied(button: HTMLButtonElement) {
  resetCopiedButton();

  copiedButton = button;
  button.dataset.copied = "true";
  button.textContent = copiedCodeLabel.value;

  copiedResetTimer = setTimeout(() => {
    resetCopiedButton();
  }, 1400);
}

/** 清除当前复制状态和定时器，恢复按钮原始文案 */
function resetCopiedButton() {
  if (copiedResetTimer) {
    clearTimeout(copiedResetTimer);
    copiedResetTimer = null;
  }

  if (copiedButton) {
    copiedButton.dataset.copied = "false";
    copiedButton.textContent = copyCodeLabel.value;
    copiedButton = null;
  }
}

onBeforeUnmount(() => {
  resetCopiedButton();
});
</script>

<template>
  <!-- 使用 v-html 渲染 Markdown HTML（XSS 已在 renderChatMarkdown 中过滤） -->
  <div
    class="chat-md"
    :data-streaming="streaming || undefined"
    v-html="renderedHtml"
    @click="handleMarkdownClick"
  />
</template>
