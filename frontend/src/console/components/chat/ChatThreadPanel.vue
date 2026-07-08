<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowUp,
  ChevronDown,
  Copy,
  LoaderCircle,
  MessageSquarePlus,
  PanelLeftOpen,
  Undo2,
} from "@lucide/vue";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

import ChatCitationsSheet from "./ChatCitationsSheet.vue";
import ChatContextSettingsSheet from "./ChatContextSettingsSheet.vue";
import { useGlobalChatStore } from "@/console/stores/global-chat";
import type { ThinkingLevel } from "@/console/services/chat";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Textarea } from "@/shared/components/ui/textarea";

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
  draft,
  errorMessage,
  isBootstrapping,
  isLoadingMessages,
  messages,
  modelOptionGroups,
  selectedModelLabel,
  selectedModelOption,
  selectedSourceCount,
  thinking,
  threadTitle,
} = storeToRefs(globalChatStore);

// thinking 档位选项
const thinkingOptions: { value: ThinkingLevel; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

// new session 页面，composer 保持在 thread view 中间
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
  t("chat.composer.selectedSources", { count: selectedSourceCount.value }),
);

// 从指定 user message 重新开始（回退并预填草稿）
function restartFromMessage(messageUid: string) {
  void globalChatStore.restartFromMessage(messageUid).catch(() => undefined);
}

function copyMessage(content: string) {
  void navigator.clipboard?.writeText(content);
}

function startNewSession() {
  globalChatStore.startNewSession();
}

function expandSessions() {
  emit("expandSessions");
}
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
            class="absolute inset-0 flex h-9 w-full items-center"
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
            <h1
              v-if="threadTitle"
              class="min-w-0 truncate text-[15px] font-semibold text-(--text-strong)"
            >
              {{ threadTitle }}
            </h1>
          </div>

          <div
            v-else
            key="expanded-header"
            class="chat-thread-rail absolute inset-y-0 left-0 flex h-9 items-center"
          >
            <h1
              v-if="threadTitle"
              class="truncate text-[15px] font-semibold text-(--text-strong)"
            >
              {{ threadTitle }}
            </h1>
          </div>
        </Transition>
      </div>
    </header>

    <div
      class="console-scrollbar min-h-0 flex-1 overflow-y-auto px-6 pt-5"
      :class="isComposerCentered ? 'pb-8' : 'pb-42'"
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
          <article
            v-for="message in messages"
            :key="message.uid"
            class="grid gap-2"
            :class="
              message.role === 'user'
                ? 'justify-items-end'
                : 'justify-items-start'
            "
          >
            <!-- 用户消息：右对齐 -->
            <template v-if="message.role === 'user'">
              <div
                class="max-w-[78%] rounded-[1.15rem] border border-(--line-soft) bg-[#1e2024] px-3 py-2 text-[14px] leading-6 whitespace-pre-wrap text-(--text-strong)"
              >
                {{ message.content }}
              </div>
              <div
                class="flex items-center gap-2 pr-1 text-[12px] text-(--text-faint) opacity-70 transition hover:opacity-100"
              >
                <span>
                  {{ message.provider }} / {{ message.model }} ·
                  {{ message.createdLabel }}
                </span>
                <button
                  type="button"
                  :aria-label="t('chat.thread.restartAria')"
                  class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
                  @click="restartFromMessage(message.uid)"
                >
                  <Undo2 class="size-3.5" />
                </button>
                <button
                  type="button"
                  :aria-label="t('chat.thread.copyMessageAria')"
                  class="grid size-6 place-items-center rounded-(--console-radius-sm) text-(--text-faint) hover:bg-white/[0.05] hover:text-(--text-strong)"
                  @click="copyMessage(message.content)"
                >
                  <Copy class="size-3.5" />
                </button>
              </div>
            </template>

            <!-- AI 回复消息：左对齐，含引用来源 -->
            <template v-else-if="message.role === 'assistant'">
              <div
                class="max-w-[82%] text-[14px] leading-7 whitespace-pre-wrap text-(--text-body)"
              >
                {{ message.content || " " }}
              </div>
              <div v-if="message.citationCount > 0" class="flex">
                <ChatCitationsSheet :message="message" />
              </div>
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
          v-if="errorMessage"
          class="rounded-(--console-radius-lg) border border-red-400/25 bg-red-400/10 px-3 py-2 text-[13px] text-red-100"
        >
          {{ errorMessage }}
        </div>
      </div>
    </div>

    <!-- 底部输入区域：消息输入框 + 模型选择 + thinking 选择 + 发送按钮 -->
    <div
      class="pointer-events-none absolute inset-x-0"
      :class="
        isComposerCentered
          ? 'top-[54%] -translate-y-1/2 px-6'
          : 'bottom-0 bg-linear-to-t from-(--surface-base) via-(--surface-base)/95 to-transparent px-6 pt-10 pb-5'
      "
    >
      <div
        class="chat-thread-rail pointer-events-auto rounded-[1.35rem] border border-(--line-strong) bg-[#24262b] p-2 shadow-[0_22px_80px_rgba(0,0,0,0.42)]"
      >
        <Textarea
          v-model="draft"
          class="min-h-14 border-0 bg-transparent px-2 pt-2 pb-1 text-[14px] shadow-none focus-visible:ring-0"
          :placeholder="t('chat.composer.placeholder')"
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
          >
            {{ selectedSourcesLabel }}
          </span>

          <!-- 发送按钮 -->
          <Button
            type="button"
            :aria-label="t('chat.composer.sendAria')"
            size="icon"
            class="bg-primary text-primary-foreground hover:bg-primary/90 ml-auto size-8 rounded-full disabled:opacity-55"
            :disabled="!canSend"
          >
            <ArrowUp class="size-4" />
          </Button>
        </div>
      </div>
    </div>
  </section>
</template>

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
