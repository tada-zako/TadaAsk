<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import {
  ArrowUp,
  ChevronDown,
  Copy,
  LoaderCircle,
  MessageSquarePlus,
  PanelLeftOpen,
  Undo2,
  Square,
  Check,
} from "@lucide/vue";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

import ChatCitationsSheet from "./ChatCitationsSheet.vue";
import ChatContextSettingsSheet from "./ChatContextSettingsSheet.vue";
import ChatMarkdownRenderer from "./ChatMarkdownRenderer.vue";
import { useGlobalChatStore } from "@/console/stores/global-chat.ts";
import type { ThinkingLevel } from "@/console/services/chat";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Marker, MarkerContent } from "@/shared/components/ui/marker";
import { Textarea } from "@/shared/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

// 距离底部阈值：用于判断是否「钉」在底部（自动跟随滚动）
const BOTTOM_PIN_THRESHOLD = 96;
// 距离顶部阈值：触发加载更早消息
const TOP_LOAD_THRESHOLD = 96;
// 「已复制」提示自动消失延迟
const COPIED_RESET_DELAY_MS = 1400;

// sessionsCollapsed: 左侧会话面板是否折叠，影响 rail 偏移量
const props = withDefaults(
  defineProps<{
    sessionsCollapsed?: boolean;
  }>(),
  {
    sessionsCollapsed: false,
  },
);

const emit = defineEmits<{
  expandSessions: [];
}>();

const { t } = useI18n();
const globalChatStore = useGlobalChatStore();
const {
  activeSessionUid,
  canSend,
  cancelledMessageUids,
  draft,
  errorMessage,
  hasMoreBefore,
  isBootstrapping,
  isCancelling,
  isLoadingMessages,
  isLoadingOlderMessages,
  isStreaming,
  messages,
  modelOptionGroups,
  selectedModelLabel,
  selectedModelOption,
  selectedSourceCount,
  streamingAssistantMessageUid,
  thinking,
  threadTitle,
} = storeToRefs(globalChatStore);

// 消息时间线引用对象
const timelineRef = ref<HTMLElement | null>(null);
// composer 容器引用，用于在页面进入或切换会话后聚焦原生 textarea
const composerRef = ref<HTMLElement | null>(null);
// 当前由正文 citation marker 或摘要 chip 打开的引用面板状态
const citationSheetMessageUid = ref<string | null>(null); // 激活的 citation 面板
const activeCitationId = ref<number | null>(null); // 用户选中的 citation 对象
// 记录当前显示「已复制」提示的消息 uid
const copiedMessageUid = ref<string | null>(null);
// IME 组合输入中，阻止 Enter 误发送
const isComposerComposing = ref(false);
// 消息列表是否「钉」在底部，控制流式输出时自动跟随滚动
const isPinnedToBottom = ref(true);
// 进入/切换 session 后需要等待消息就绪，再强制定位到底部
const shouldForceScrollToBottom = ref(false);
let copiedResetTimer: ReturnType<typeof setTimeout> | null = null;
// 防止加载旧消息时重复触发
let isPreservingOlderScroll = false;

// thinking 档位选项
const thinkingOptions: { value: ThinkingLevel; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

// 新会话或无消息时，composer 居中显示而非固定底部
const isComposerCentered = computed(
  () =>
    !isBootstrapping.value &&
    !isLoadingMessages.value &&
    messages.value.length === 0,
);

const emptyTitle = computed(() =>
  activeSessionUid.value
    ? // 一般不会出现没有 empty session
      t("chat.thread.emptySession")
    : t("chat.thread.newChat"),
);

const selectedSourcesLabel = computed(() =>
  selectedSourceCount.value > 0
    ? t("chat.composer.selectedSources", { count: selectedSourceCount.value })
    : t("chat.composer.selectSources"),
);

const showCenteredError = computed(
  () => isComposerCentered.value && Boolean(errorMessage.value),
);

const showTimelineError = computed(
  () => !isComposerCentered.value && Boolean(errorMessage.value),
);

const showScrollToBottom = computed(
  () =>
    !isComposerCentered.value &&
    messages.value.length > 0 &&
    !isPinnedToBottom.value,
);

// 从指定 user message 重新开始（回退并预填草稿）
function restartFromMessage(messageUid: string) {
  void globalChatStore.restartFromMessage(messageUid).catch(() => undefined);
}

// 复制消息内容到剪贴板，并显示「已复制」提示
function copyMessage(messageUid: string, content: string) {
  void navigator.clipboard?.writeText(content).then(() => {
    copiedMessageUid.value = messageUid;
    if (copiedResetTimer) {
      clearTimeout(copiedResetTimer);
    }
    // 设置已复制状态归位计时器
    copiedResetTimer = setTimeout(() => {
      copiedMessageUid.value = null;
      copiedResetTimer = null;
    }, COPIED_RESET_DELAY_MS);
  });
}

// 发送消息 → store action 触发 SSE stream
function sendMessage() {
  void globalChatStore.sendMessage().catch(() => undefined);
}

// 取消当前正在生成的回复
function cancelGeneration() {
  void globalChatStore.cancelGeneration().catch(() => undefined);
}

function startNewSession() {
  globalChatStore.startNewSession();
  void focusComposer();
}

function expandSessions() {
  emit("expandSessions");
}

// 判断消息是否已被用户取消生成
function isMessageCancelled(messageUid: string) {
  return cancelledMessageUids.value.includes(messageUid);
}

/** citation bottom 点击事件 */
function openCitation(messageUid: string, citationId: number) {
  const message = messages.value.find((item) => item.uid === messageUid);
  if (!message?.sourcesReady) return;

  activeCitationId.value = citationId;
  citationSheetMessageUid.value = messageUid;
}

/** 打开 sheet 后刷新状态 */
function handleCitationSheetOpenChange(messageUid: string, open: boolean) {
  if (open) {
    if (citationSheetMessageUid.value !== messageUid) {
      activeCitationId.value = null;
    }
    citationSheetMessageUid.value = messageUid;
    return;
  }

  if (citationSheetMessageUid.value === messageUid) {
    // 关闭页面，刷新状态
    citationSheetMessageUid.value = null;
    activeCitationId.value = null;
  }
}

// composer Enter 发送：排除 Shift+Enter 换行、IME 组合输入中
function handleComposerKeydown(event: KeyboardEvent) {
  if (
    event.key !== "Enter" ||
    event.shiftKey ||
    event.isComposing ||
    isComposerComposing.value
  ) {
    return;
  }

  event.preventDefault();
  sendMessage();
}

// 消息列表滚动处理：更新底部 pin 状态 + 顶部触发加载更早消息
function handleTimelineScroll() {
  const element = timelineRef.value;
  if (!element) {
    return;
  }

  updatePinnedToBottom();

  // 向上滚动到顶部附近时加载更早消息
  if (
    !isPinnedToBottom.value &&
    element.scrollTop <= TOP_LOAD_THRESHOLD &&
    hasMoreBefore.value &&
    !isLoadingMessages.value &&
    !isLoadingOlderMessages.value
  ) {
    void loadOlderMessagesPreservingScroll();
  }
}

// 加载更早消息并保持当前滚动位置不变
async function loadOlderMessagesPreservingScroll() {
  const element = timelineRef.value;
  if (!element || isPreservingOlderScroll) {
    return;
  }

  isPreservingOlderScroll = true;
  const previousScrollHeight = element.scrollHeight;
  const previousScrollTop = element.scrollTop;

  try {
    const loaded = await globalChatStore.loadOlderMessages();
    if (!loaded) {
      return;
    }

    await nextTick();
    // 补偿因上方插入旧消息导致的滚动偏移
    element.scrollTop =
      element.scrollHeight - previousScrollHeight + previousScrollTop;
    updatePinnedToBottom();
  } finally {
    isPreservingOlderScroll = false;
  }
}

// 根据当前滚动位置更新 isPinnedToBottom 状态
function updatePinnedToBottom() {
  const element = timelineRef.value;
  if (!element) {
    return;
  }

  // 计算聊天窗口最底部距离当前滚动位置的距离
  const distanceToBottom =
    element.scrollHeight - element.scrollTop - element.clientHeight;
  isPinnedToBottom.value = distanceToBottom <= BOTTOM_PIN_THRESHOLD;
}

// 滚动到消息列表底部
async function scrollToBottom(behavior: ScrollBehavior = "auto") {
  await nextTick();
  const element = timelineRef.value;
  if (!element) {
    return;
  }

  element.scrollTo({
    behavior,
    top: element.scrollHeight,
  });
  isPinnedToBottom.value = true;
}

/** 用户主动返回最新消息，使用平滑滚动并恢复自动跟随。 */
function handleScrollToBottom() {
  void scrollToBottom("smooth");
}

/** 聚焦 composer，不让浏览器因此改变 timeline 滚动位置。 */
async function focusComposer() {
  if (isBootstrapping.value || isLoadingMessages.value) {
    return;
  }

  await nextTick();
  composerRef.value
    ?.querySelector<HTMLTextAreaElement>("textarea")
    ?.focus({ preventScroll: true });
}

/** 请求强制滚动到底部 */
function requestForceScrollToBottom() {
  shouldForceScrollToBottom.value = true;
  isPinnedToBottom.value = true;
  void flushForceScrollToBottom();
}

async function flushForceScrollToBottom() {
  if (
    !shouldForceScrollToBottom.value ||
    isBootstrapping.value ||
    isLoadingMessages.value ||
    isPreservingOlderScroll
  ) {
    return;
  }

  await scrollToBottom();
  shouldForceScrollToBottom.value = false;
}

// 切换会话时等待消息就绪后滚到底部
watch(activeSessionUid, () => {
  citationSheetMessageUid.value = null;
  activeCitationId.value = null;
  requestForceScrollToBottom();
  void focusComposer();
});

// 页面进入或消息加载完成后，补齐从其他页面进入 chat 时的底部定位
watch([isBootstrapping, isLoadingMessages], async () => {
  if (shouldForceScrollToBottom.value) {
    await flushForceScrollToBottom();
  }

  if (!isBootstrapping.value && !isLoadingMessages.value) {
    await focusComposer();
  }
});

// 消息内容/引用数量变化时，若钉在底部则自动跟随滚动（流式输出场景）
watch(messages, () => {
  if (shouldForceScrollToBottom.value) {
    void flushForceScrollToBottom();
    return;
  }

  if (
    !isLoadingOlderMessages.value &&
    !isPreservingOlderScroll &&
    isPinnedToBottom.value
  ) {
    void scrollToBottom();
  }
});

onMounted(() => {
  // 进入 /chat 强制进行滚动到底
  requestForceScrollToBottom();
  void focusComposer();
});

onBeforeUnmount(() => {
  if (copiedResetTimer) {
    clearTimeout(copiedResetTimer);
  }
});
</script>

<template>
  <!-- 聊天消息线程面板：展示对话消息列表与底部输入区域 -->
  <section
    class="chat-thread-panel relative flex min-h-0 min-w-0 flex-col overflow-hidden"
    :data-sessions-collapsed="props.sessionsCollapsed"
  >
    <!-- 顶部标题栏 -->
    <header class="shrink-0 px-6 py-1.5">
      <div class="relative h-9">
        <Transition
          enter-active-class="transition-opacity duration-1000 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
          enter-from-class="opacity-0"
          enter-to-class="opacity-100"
          leave-active-class="transition-opacity duration-120 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <div
            v-if="props.sessionsCollapsed"
            key="collapsed-header"
            class="absolute inset-y-0 left-0 z-10 flex h-9 items-center"
          >
            <div class="mr-2 flex shrink-0 items-center gap-1">
              <button
                type="button"
                :aria-label="t('chat.sessions.expandAria')"
                class="grid size-8 place-items-center rounded-(--console-radius-md) text-(--text-faint) hover:bg-white/[0.045] hover:text-(--text-strong)"
                @click="expandSessions"
              >
                <PanelLeftOpen class="size-4" />
              </button>
              <button
                type="button"
                :aria-label="t('chat.sessions.newChatAria')"
                class="grid size-8 place-items-center rounded-(--console-radius-md) text-(--text-faint) hover:bg-white/[0.045] hover:text-(--text-strong)"
                @click="startNewSession"
              >
                <MessageSquarePlus class="size-4" />
              </button>
              <ChatContextSettingsSheet compact />
            </div>
          </div>
        </Transition>

        <div
          class="chat-thread-rail chat-thread-title-rail pointer-events-none absolute inset-y-0 left-0 flex h-9 items-center"
        >
          <h1
            v-if="threadTitle"
            class="truncate text-[15px] font-semibold text-(--text-strong)"
          >
            {{ threadTitle }}
          </h1>
        </div>
      </div>
    </header>

    <div
      ref="timelineRef"
      class="console-scrollbar min-h-0 flex-1 overflow-y-auto px-6 pt-5"
      :class="isComposerCentered ? 'pb-8' : 'pb-42'"
      @scroll="handleTimelineScroll"
    >
      <!-- 消息列表 -->
      <div class="chat-thread-rail grid gap-8">
        <!-- 加载中 -->
        <div
          v-if="isBootstrapping || isLoadingMessages"
          class="flex items-center gap-2 pt-16 text-[13px] text-(--text-faint)"
        >
          <LoaderCircle class="text-primary size-4 animate-spin" />
          {{ t("chat.thread.loading") }}
        </div>

        <!-- 空状态：无会话或新会话 -->
        <div
          v-else-if="messages.length === 0"
          class="grid justify-items-center gap-2 pt-[18dvh] text-center"
        >
          <h2 class="text-[26px] font-semibold text-(--text-strong)">
            {{ emptyTitle }}
          </h2>
        </div>

        <!-- messages list 区域 -->
        <template v-else>
          <!-- 加载更早消息中的 loading 指示器 -->
          <div
            v-if="isLoadingOlderMessages"
            class="flex items-center justify-center gap-2 py-2 text-[12px] text-(--text-faint)"
          >
            <LoaderCircle class="text-primary size-3.5 animate-spin" />
            {{ t("chat.thread.loadingOlder") }}
          </div>

          <article
            v-for="message in messages"
            :key="message.uid"
            class="group grid gap-1.5"
            :class="
              message.role === 'user'
                ? 'justify-items-end'
                : 'justify-items-start'
            "
          >
            <!-- 用户消息：右对齐 -->
            <template v-if="message.role === 'user'">
              <div
                class="max-w-[78%] rounded-[1rem] border border-(--line-soft) bg-[#1e2024] px-3 py-1.5 text-[14px] leading-6 whitespace-pre-wrap text-(--text-strong)"
              >
                {{ message.content }}
              </div>
              <div
                class="flex min-h-6 items-center gap-2 pr-1 text-[12px] text-(--text-faint) opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100"
              >
                <span>
                  {{ message.provider }} / {{ message.model }} ·
                  {{ message.createdLabel }}
                </span>
                <button
                  type="button"
                  :aria-label="t('chat.thread.restartAria')"
                  class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
                  :disabled="isStreaming"
                  @click="restartFromMessage(message.uid)"
                >
                  <Undo2 class="size-3.5" />
                </button>
                <button
                  type="button"
                  :aria-label="t('chat.thread.copyMessageAria')"
                  class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
                  @click="copyMessage(message.uid, message.content)"
                >
                  <Copy
                    v-if="copiedMessageUid !== message.uid"
                    class="size-3.5"
                  />
                  <Check v-else class="size-3.5" />
                </button>
                <!-- 「已复制」提示 -->
                <!-- <span
                  v-if="copiedMessageUid === message.uid"
                  class="text-[11px] text-(--text-muted)"
                >
                  {{ t("chat.thread.copied") }}
                </span> -->
              </div>
            </template>

            <!-- AI 回复消息：左对齐，含引用来源 -->
            <template v-else-if="message.role === 'assistant'">
              <div class="max-w-[92%] text-[14px] leading-7 text-(--text-body)">
                <!-- 后端 assistant 消息尚未响应时渲染加载信息 -->
                <span
                  v-if="
                    !message.content &&
                    message.uid === streamingAssistantMessageUid
                  "
                  class="inline-flex items-center gap-2 text-(--text-faint)"
                >
                  <LoaderCircle class="text-primary size-3.5 animate-spin" />
                  {{ t("chat.thread.thinking") }}
                </span>
                <ChatMarkdownRenderer
                  v-else
                  :citation-items="message.citationItems"
                  :content="message.content || ' '"
                  :streaming="message.uid === streamingAssistantMessageUid"
                  @open-citation="openCitation(message.uid, $event)"
                />
              </div>
              <div
                v-if="message.sourcesReady && message.citationCount > 0"
                class="flex"
              >
                <ChatCitationsSheet
                  :active-citation-id="
                    citationSheetMessageUid === message.uid
                      ? activeCitationId
                      : null
                  "
                  :message="message"
                  :open="citationSheetMessageUid === message.uid"
                  @update:open="
                    handleCitationSheetOpenChange(message.uid, $event)
                  "
                />
              </div>
              <!-- assistant 消息底部操作栏：模型信息 / 复制 -->
              <div class="flex min-h-6 items-center gap-2 text-[12px]">
                <div
                  class="flex items-center gap-2 text-(--text-faint) opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100"
                >
                  <button
                    type="button"
                    :aria-label="t('chat.thread.copyMessageAria')"
                    class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
                    @click="copyMessage(message.uid, message.content)"
                  >
                    <Copy
                      v-if="copiedMessageUid !== message.uid"
                      class="size-3.5"
                    />
                    <Check v-else class="size-3.5" />
                  </button>
                  <!-- 「已复制」提示 -->
                  <!-- <span
                  v-if="copiedMessageUid === message.uid"
                  class="text-[11px] text-(--text-muted)"
                  >
                  {{ t("chat.thread.copied") }}
                </span> -->
                  <span>
                    {{ message.provider }} / {{ message.model }} ·
                    {{ message.createdLabel }}
                  </span>
                </div>
              </div>
              <!-- cancelled 仅为当前前端运行时状态，后端持久化状态补齐后可直接复用此 Marker。 -->
              <Marker
                v-if="isMessageCancelled(message.uid)"
                variant="separator"
                class="mt-1 max-w-[92%] gap-2 text-[11px] text-(--text-faint) before:bg-(--line-soft) after:bg-(--line-soft)"
              >
                <MarkerContent>{{ t("chat.thread.stopped") }}</MarkerContent>
              </Marker>
            </template>

            <template v-else>
              <div
                class="max-w-[82%] rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) px-3 py-2 text-[13px] leading-6 whitespace-pre-wrap text-(--text-muted)"
              >
                {{ message.content }}
              </div>
            </template>
          </article>
        </template>

        <!-- 错误提示 -->
        <div
          v-if="showTimelineError"
          class="rounded-(--console-radius-lg) border border-red-400/25 bg-red-400/10 px-3 py-2 text-[13px] text-red-100"
        >
          {{ errorMessage }}
        </div>
      </div>
    </div>

    <!-- 底部输入区域：消息输入框 + 模型选择 + thinking 选择 + 发送按钮 -->
    <div
      class="pointer-events-none absolute"
      :class="
        isComposerCentered
          ? 'inset-x-0 top-[40%] px-6'
          : 'right-4 bottom-0 left-0 bg-linear-to-t from-(--surface-base) via-(--surface-base)/95 to-transparent px-6 pt-10 pb-5'
      "
    >
      <Transition
        enter-active-class="transition duration-180 ease-out motion-reduce:transition-none"
        enter-from-class="translate-y-1 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-120 ease-in motion-reduce:transition-none"
        leave-from-class="translate-y-0 opacity-100"
        leave-to-class="translate-y-1 opacity-0"
      >
        <div
          v-if="showScrollToBottom"
          class="chat-thread-rail pointer-events-auto mb-3 flex justify-center"
        >
          <TooltipProvider :delay-duration="350">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  type="button"
                  :aria-label="t('chat.thread.scrollToBottomAria')"
                  variant="outline"
                  size="icon"
                  class="size-8 rounded-full border-(--line-strong) bg-[#1b1d21]/95 text-(--text-muted) shadow-[0_10px_28px_rgba(0,0,0,0.34)] backdrop-blur-md hover:bg-[#24272c] hover:text-(--text-strong)"
                  @click="handleScrollToBottom"
                >
                  <ChevronDown class="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top">
                {{ t("chat.thread.scrollToBottom") }}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </Transition>

      <div
        v-if="showCenteredError"
        class="chat-thread-rail pointer-events-auto mb-3 rounded-(--console-radius-lg) border border-red-400/25 bg-red-400/10 px-3 py-2 text-[13px] text-red-100 shadow-[0_12px_36px_rgba(0,0,0,0.28)]"
      >
        {{ errorMessage }}
      </div>
      <div
        ref="composerRef"
        class="chat-thread-rail pointer-events-auto rounded-[1.35rem] border border-(--line-strong) bg-[#24262b] p-2 shadow-[0_22px_80px_rgba(0,0,0,0.42)]"
      >
        <Textarea
          v-model="draft"
          class="composer-textarea-scrollbar max-h-44 min-h-14 resize-none overflow-y-auto border-0 bg-transparent px-2 pt-2 pb-1 text-[14px] shadow-none focus-visible:ring-0"
          :placeholder="t('chat.composer.placeholder')"
          @compositionstart="isComposerComposing = true"
          @compositionend="isComposerComposing = false"
          @keydown="handleComposerKeydown"
        />

        <!-- 模型选择 -->
        <div class="flex items-center gap-2 px-1 pt-2 pb-1">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <button
                type="button"
                :aria-label="t('chat.composer.selectModelAria')"
                class="flex h-7 min-w-0 items-center gap-1.5 rounded-(--console-radius-md) px-1.5 text-[13px] text-(--text-body) hover:bg-white/[0.045] hover:text-(--text-strong)"
              >
                <span class="max-w-48 truncate">{{ selectedModelLabel }}</span>
                <ChevronDown class="size-3.5 shrink-0 text-(--text-faint)" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              class="max-h-82 w-72 overflow-y-auto rounded-(--console-radius-lg) border-(--line) bg-(--surface-shell) p-1.5"
            >
              <DropdownMenuItem
                v-if="modelOptionGroups.length === 0"
                disabled
                class="text-[13px] text-(--text-faint)"
              >
                {{ t("chat.composer.noEnabledModel") }}
              </DropdownMenuItem>
              <template
                v-for="(group, groupIndex) in modelOptionGroups"
                :key="group.providerUid"
              >
                <!-- <DropdownMenuSeparator
                  v-if="groupIndex > 0"
                  class="my-1 bg-(--line-soft)"
                /> -->
                <DropdownMenuLabel
                  class="px-1.5 pb-0.5 text-[11px] font-semibold text-(--text-faint) uppercase"
                  :class="groupIndex > 0 ? 'pt-2.5' : 'pt-1.5'"
                >
                  {{ group.providerDisplayName }}
                </DropdownMenuLabel>
                <DropdownMenuItem
                  v-for="option in group.options"
                  :key="`${option.providerUid}-${option.modelUid}`"
                  class="min-h-8 rounded-(--console-radius-md) text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                  :class="
                    selectedModelOption?.modelUid === option.modelUid
                      ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                      : ''
                  "
                  @select="
                    globalChatStore.setProviderModel(
                      option.providerUid,
                      option.modelUid,
                    )
                  "
                >
                  <span class="min-w-0 flex-1 truncate">
                    {{ option.modelName }}
                  </span>
                </DropdownMenuItem>
              </template>
            </DropdownMenuContent>
          </DropdownMenu>

          <!-- thinking 选择 -->
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <button
                type="button"
                :aria-label="t('chat.composer.selectThinkingAria')"
                class="flex h-7 items-center gap-1.5 rounded-(--console-radius-md) px-1.5 text-[13px] text-(--text-body) hover:bg-white/[0.045] hover:text-(--text-strong)"
              >
                {{ thinking }}
                <ChevronDown class="size-3.5 text-(--text-faint)" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              class="w-32 rounded-(--console-radius-lg) border-(--line) bg-(--surface-shell) p-1.5"
            >
              <DropdownMenuItem
                v-for="option in thinkingOptions"
                :key="String(option.value)"
                class="min-h-8 rounded-(--console-radius-md) text-[13px] text-(--text-muted) focus:bg-(--surface-hover) focus:text-(--text-strong)"
                :class="
                  thinking === option.value
                    ? 'bg-primary/10 text-primary focus:bg-primary/15 focus:text-primary'
                    : ''
                "
                @select="globalChatStore.setThinking(option.value)"
              >
                {{ option.label }}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <!-- composer 中 sources 选中状态显示 -->
          <span
            class="ml-1 hidden text-[12px] text-(--text-faint) sm:inline-flex"
            :class="selectedSourceCount > 0 ? 'text-primary/70' : ''"
          >
            {{ selectedSourcesLabel }}
          </span>

          <!-- 发送按钮 -->
          <Button
            v-if="!isStreaming"
            type="button"
            :aria-label="t('chat.composer.sendAria')"
            size="icon"
            class="bg-primary text-primary-foreground hover:bg-primary/90 ml-auto size-8 rounded-full disabled:opacity-55"
            :disabled="!canSend"
            @click="sendMessage"
          >
            <ArrowUp class="size-4" />
          </Button>
          <Button
            v-else
            type="button"
            :aria-label="t('chat.composer.cancelAria')"
            size="icon"
            class="ml-auto size-8 rounded-full bg-white/[0.08] text-(--text-strong) hover:bg-white/[0.12] disabled:opacity-55"
            :disabled="isCancelling"
            @click="cancelGeneration"
          >
            <LoaderCircle v-if="isCancelling" class="size-4 animate-spin" />
            <Square v-else class="size-3" fill="white" />
          </Button>
        </div>
      </div>
    </div>
  </section>
</template>

<!--
  chat-thread-rail 布局：消息流居中限宽，偏移量随 sessions 面板折叠/展开动态变化。
  --chat-rail-offset 由 data-sessions-collapsed 控制：展开=228px，折叠=0。
-->
<style scoped>
.chat-thread-panel {
  --chat-sessions-width: 228px;
  --chat-rail-gutter: 2rem;
  --chat-rail-max-width: 820px;
  --chat-rail-offset: var(--chat-sessions-width);
  --chat-rail-width: min(
    var(--chat-rail-max-width),
    calc(100% - var(--chat-sessions-width) - var(--chat-rail-gutter))
  );
  --chat-rail-left: calc(
    var(--chat-rail-offset) +
      (100% - var(--chat-rail-offset) - var(--chat-rail-width)) / 2
  );
}

.chat-thread-panel[data-sessions-collapsed="true"] {
  --chat-rail-offset: 0px;
}

.chat-thread-rail {
  width: var(--chat-rail-width);
  margin-left: var(--chat-rail-left);
  transition: margin-left 880ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: margin-left;
}

.chat-thread-title-rail {
  transition:
    margin-left 880ms cubic-bezier(0.22, 1, 0.36, 1),
    padding-left 880ms cubic-bezier(0.22, 1, 0.36, 1);
}

.chat-thread-panel[data-sessions-collapsed="true"] .chat-thread-title-rail {
  padding-left: max(0px, calc(7.5rem - var(--chat-rail-left)));
}

.console-scrollbar {
  scrollbar-gutter: stable;
}

.composer-textarea-scrollbar {
  scrollbar-width: thin;
  scrollbar-color: rgba(154, 164, 180, 0.34) transparent;
}

.composer-textarea-scrollbar::-webkit-scrollbar {
  width: 8px;
}

.composer-textarea-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.composer-textarea-scrollbar::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: rgba(154, 164, 180, 0.28);
  background-clip: padding-box;
}

.composer-textarea-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(178, 187, 202, 0.46);
  background-clip: padding-box;
}

@media (max-width: 900px) {
  .chat-thread-panel {
    --chat-sessions-width: 0px;
    --chat-rail-offset: 0px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chat-thread-rail {
    transition: none;
  }
}
</style>
