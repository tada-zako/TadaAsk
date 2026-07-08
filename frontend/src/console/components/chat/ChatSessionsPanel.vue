<script setup lang="ts">
import { Archive, PanelLeft, MessageSquarePlus } from "@lucide/vue";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

import ChatContextSettingsSheet from "./ChatContextSettingsSheet.vue";
import { useGlobalChatStore } from "@/console/stores/global-chat";
import { Button } from "@/shared/components/ui/button";

const emit = defineEmits<{
  collapse: [];
}>();

withDefaults(
  defineProps<{
    collapsed?: boolean;
  }>(),
  {
    collapsed: false,
  },
);

const { t } = useI18n();
const globalChatStore = useGlobalChatStore();
const {
  activeSessionUid,
  isLoadingSessions,
  isMutating,
  isStreaming,
  sessions,
} = storeToRefs(globalChatStore);

function openSession(sessionUid: string) {
  void globalChatStore.selectSession(sessionUid).catch(() => undefined);
}

function startNewSession() {
  globalChatStore.startNewSession();
}

// 删除 session：确认后通过 store action 执行，自动处理 active session 切换
function deleteSession(sessionUid: string, title: string) {
  const confirmed = window.confirm(t("chat.sessions.deleteConfirm", { title }));
  if (!confirmed) {
    return;
  }

  void globalChatStore.deleteSession(sessionUid).catch(() => undefined);
}

function collapseSessions() {
  emit("collapse");
}
</script>

<template>
  <!-- 会话列表面板：展示全局聊天会话列表，支持新建会话、归档及上下文设置 -->
  <aside
    class="flex min-h-0 flex-col border-r border-(--line-soft) bg-(--surface-shell)/72 px-3 py-3"
  >
    <div
      class="flex min-h-0 flex-1 flex-col transition-opacity duration-600 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
      :class="collapsed ? 'opacity-0' : 'opacity-100'"
    >
      <!-- 顶部：标题与折叠按钮 -->
      <div class="flex items-center justify-between gap-2">
        <span class="text-[11px] font-semibold text-(--text-faint) uppercase">
          {{ t("chat.globalTitle") }}
        </span>
        <Button
          type="button"
          :aria-label="t('chat.sessions.collapseAria')"
          variant="ghost"
          size="icon"
          class="size-8 text-(--text-muted) hover:bg-(--surface-hover) hover:text-(--text-strong)"
          @click="collapseSessions"
        >
          <PanelLeft class="size-4" />
        </Button>
      </div>

      <!-- 操作区：新建会话 + 上下文设置 -->
      <div class="mt-3 grid gap-2">
        <Button
          type="button"
          :aria-label="t('chat.sessions.newChatAria')"
          class="h-9 justify-start gap-2 rounded-(--console-radius-lg) bg-(--surface-hover) text-[13px] font-semibold text-(--text-strong) hover:bg-[#24272d]"
          :disabled="isStreaming"
          @click="startNewSession"
        >
          <MessageSquarePlus class="size-4" />
          {{ t("chat.sessions.newChat") }}
        </Button>
        <ChatContextSettingsSheet />
      </div>

      <div class="mt-6 flex items-center justify-between px-1">
        <span
          class="text-[11px] font-semibold text-(--text-disabled) uppercase"
        >
          {{ t("chat.sessions.sectionTitle") }}
        </span>
        <span class="text-[11px] text-(--text-disabled)">
          {{ sessions.length }}
        </span>
      </div>

      <!-- 会话历史列表 -->
      <nav
        class="console-scrollbar mt-2 grid min-h-0 flex-1 content-start gap-1 overflow-y-auto pr-1"
        aria-label="Chat sessions"
      >
        <p
          v-if="isLoadingSessions"
          class="px-2.5 py-3 text-[12px] text-(--text-faint)"
        >
          {{ t("chat.sessions.loading") }}
        </p>

        <p
          v-else-if="sessions.length === 0"
          class="px-2.5 py-3 text-[12px] leading-5 text-(--text-faint)"
        >
          {{ t("chat.sessions.empty") }}
        </p>

        <template v-else>
          <div
            v-for="session in sessions"
            :key="session.uid"
            class="group grid min-h-9 grid-cols-[minmax(0,1fr)_auto] items-center gap-1 rounded-(--console-radius-md)"
            :class="
              activeSessionUid === session.uid
                ? 'bg-white/[0.055]'
                : 'hover:bg-white/[0.035]'
            "
          >
            <button
              type="button"
              :aria-label="
                t('chat.sessions.openSessionAria', { title: session.title })
              "
              class="min-w-0 px-2.5 py-2 text-left"
              :disabled="isStreaming"
              :class="
                activeSessionUid === session.uid
                  ? 'text-[13px] font-semibold text-(--text-strong)'
                  : 'text-[13px] font-medium text-(--text-muted) hover:text-(--text-strong)'
              "
              @click="openSession(session.uid)"
            >
              <span class="block truncate">{{ session.title }}</span>
            </button>
            <button
              type="button"
              :aria-label="
                t('chat.sessions.deleteSessionAria', { title: session.title })
              "
              class="mr-1 grid size-7 place-items-center rounded-(--console-radius-sm) text-(--text-disabled) opacity-0 transition group-hover:opacity-80 hover:bg-white/[0.05] hover:text-(--text-muted)"
              :disabled="isMutating || isStreaming"
              @click="deleteSession(session.uid, session.title)"
            >
              <Archive class="size-3.5" />
            </button>
          </div>
        </template>
      </nav>
    </div>
  </aside>
</template>
