<script setup lang="ts">
import { ExternalLink, FileText, Globe2, Settings2 } from "@lucide/vue";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { useGlobalChatStore } from "@/console/stores/global-chat";
import { useSourceStore } from "@/console/stores/source";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Label } from "@/shared/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/shared/components/ui/sheet";
import { Switch } from "@/shared/components/ui/switch";
import { Textarea } from "@/shared/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

const { compact = false } = defineProps<{
  compact?: boolean;
}>();

const { t, te } = useI18n();
const router = useRouter();
const globalChatStore = useGlobalChatStore();
const sourceStore = useSourceStore();
const { adminSystemPrompt, ragOptions, selectedSourceCount } =
  storeToRefs(globalChatStore);
const { isLoading, sources } = storeToRefs(sourceStore);

// 通过 store action 修改 RAG 模式
function setRagMode(mode: "fast" | "adaptive" | "full") {
  globalChatStore.setRagMode(mode);
}

function setSourceSelected(sourceUid: string, value: unknown) {
  globalChatStore.setSourceSelected(sourceUid, Boolean(value));
}

function openSourceContents(sourceUid: string) {
  void router.push({
    name: "source-items",
    params: { sourceUid },
  });
}

function sourceTypeLabel(sourceType: string): string {
  const key = `sources.service.sourceType.${sourceType}`;
  return te(key) ? t(key) : sourceType;
}

function sourceStatusLabel(status: string): string {
  const key = `sources.service.sourceStatus.${status}`;
  return te(key) ? t(key) : status;
}
</script>

<template>
  <Sheet>
    <SheetTrigger as-child>
      <Button
        type="button"
        :aria-label="t('chat.context.openAria')"
        :title="compact ? t('chat.context.title') : undefined"
        :variant="compact ? 'ghost' : 'outline'"
        class="gap-2 hover:bg-(--surface-hover) hover:text-(--text-strong)"
        :class="[
          compact
            ? 'size-8 rounded-(--console-radius-md) px-0'
            : 'h-9 justify-start rounded-(--console-radius-lg) border-(--line-soft) bg-transparent text-[13px] font-medium',
          !compact && selectedSourceCount > 0 ? 'text-primary/80' : '',
        ]"
      >
        <Settings2 class="size-4" />
        <span v-if="!compact">
          {{
            selectedSourceCount > 0
              ? t("chat.context.configured", { count: selectedSourceCount })
              : t("chat.context.configure")
          }}
        </span>
      </Button>
    </SheetTrigger>

    <SheetContent
      class="!right-0 !w-[min(600px,100dvw)] !max-w-[100dvw] min-w-0 gap-0 overflow-hidden border-(--line) bg-[#0d0e10] p-0 sm:max-w-none"
    >
      <SheetHeader class="border-b border-(--line-soft) px-5 py-4">
        <SheetTitle class="text-[15px]">{{
          t("chat.context.title")
        }}</SheetTitle>
      </SheetHeader>

      <div
        class="console-scrollbar grid min-h-0 flex-1 content-start gap-5 overflow-y-auto px-5 py-4"
      >
        <!-- 知识库来源选择 -->
        <section class="grid gap-3">
          <!-- sub header -->
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="text-[13px] font-semibold text-(--text-strong)">
                {{ t("chat.context.sources.title") }}
              </h2>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                {{ t("chat.context.sources.help") }}
              </p>
            </div>
            <span
              class="rounded-full border border-(--line-soft) px-2 py-1 text-[11px] text-(--text-muted)"
            >
              {{
                t("chat.context.sources.selected", {
                  count: selectedSourceCount,
                })
              }}
            </span>
          </div>

          <!-- selector -->
          <div
            class="console-scrollbar max-h-48 overflow-y-auto rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft)"
          >
            <p
              v-if="isLoading"
              class="px-3 py-3 text-[12px] text-(--text-faint)"
            >
              {{ t("chat.context.sources.loading") }}
            </p>
            <p
              v-else-if="sources.length === 0"
              class="px-3 py-3 text-[12px] leading-5 text-(--text-faint)"
            >
              {{ t("chat.context.sources.empty") }}
            </p>
            <template v-else>
              <TooltipProvider :delay-duration="450">
                <div
                  v-for="source in sources"
                  :key="source.uid"
                  class="grid min-h-12 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-(--line-soft) px-3 text-[13px] last:border-b-0 hover:bg-white/[0.025]"
                >
                  <Checkbox
                    :id="`chat-source-${source.uid}`"
                    :aria-label="
                      t('chat.context.sources.selectAria', {
                        name: source.sourceName,
                      })
                    "
                    :model-value="globalChatStore.isSourceSelected(source.uid)"
                    @update:model-value="setSourceSelected(source.uid, $event)"
                  />
                  <Label
                    :for="`chat-source-${source.uid}`"
                    class="min-w-0 cursor-pointer flex-col items-start gap-0.5"
                  >
                    <span
                      class="block w-80 truncate text-[13px] leading-4 font-medium text-(--text-strong)"
                    >
                      {{ source.sourceName }}
                    </span>
                    <span
                      class="block w-full truncate text-[10px] leading-4 font-normal text-(--text-faint)"
                    >
                      {{ sourceTypeLabel(source.sourceType) }} ·
                      {{ sourceStatusLabel(source.status) }}
                    </span>
                  </Label>
                  <div class="flex items-center gap-1">
                    <Globe2
                      v-if="source.sourceType === 'web_crawl'"
                      class="size-3.5 text-(--text-disabled)"
                    />
                    <FileText v-else class="size-3.5 text-(--text-disabled)" />
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <Button
                          type="button"
                          :aria-label="
                            t('chat.context.sources.viewContentsAria', {
                              name: source.sourceName,
                            })
                          "
                          variant="ghost"
                          size="icon-sm"
                          class="ml-0.5 size-7 rounded-(--console-radius-md) text-(--text-faint) hover:bg-white/[0.055] hover:text-(--text-strong)"
                          @click="openSourceContents(source.uid)"
                        >
                          <ExternalLink class="size-3.5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="left">
                        {{ t("chat.context.sources.viewContents") }}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
              </TooltipProvider>
            </template>
          </div>
        </section>

        <!-- RAG 检索模式：Fast / Adaptive / Full -->
        <section class="grid gap-3 border-t border-(--line-soft) pt-4">
          <div>
            <h2 class="text-[13px] font-semibold text-(--text-strong)">
              {{ t("chat.context.ragMode.title") }}
            </h2>
            <p class="mt-1 text-xs leading-5 text-(--text-faint)">
              {{ t("chat.context.ragMode.help") }}
            </p>
          </div>

          <div class="grid gap-2">
            <button
              type="button"
              :aria-label="t('chat.context.ragMode.fastAria')"
              class="grid gap-1 rounded-(--console-radius-lg) border px-3 py-2.5 text-left"
              :class="
                ragOptions.mode === 'fast'
                  ? 'border-primary/35 bg-primary/10'
                  : 'border-(--line-soft) bg-(--surface-panel-soft)'
              "
              @click="setRagMode('fast')"
            >
              <span
                class="text-[13px] font-semibold"
                :class="
                  ragOptions.mode === 'fast'
                    ? 'text-primary'
                    : 'text-(--text-strong)'
                "
              >
                {{ t("chat.context.ragMode.fast") }}
              </span>
              <span class="text-xs leading-5 text-(--text-muted)">
                {{ t("chat.context.ragMode.fastHelp") }}
              </span>
            </button>

            <button
              type="button"
              :aria-label="t('chat.context.ragMode.adaptiveAria')"
              class="grid gap-1 rounded-(--console-radius-lg) border px-3 py-2.5 text-left"
              :class="
                ragOptions.mode === 'adaptive'
                  ? 'border-primary/35 bg-primary/10'
                  : 'border-(--line-soft) bg-(--surface-panel-soft)'
              "
              @click="setRagMode('adaptive')"
            >
              <span
                class="text-[13px] font-semibold"
                :class="
                  ragOptions.mode === 'adaptive'
                    ? 'text-primary'
                    : 'text-(--text-strong)'
                "
              >
                {{ t("chat.context.ragMode.adaptive") }}
              </span>
              <span class="text-xs leading-5 text-(--text-faint)">
                {{ t("chat.context.ragMode.adaptiveHelp") }}
              </span>
            </button>

            <button
              type="button"
              :aria-label="t('chat.context.ragMode.fullAria')"
              class="grid gap-1 rounded-(--console-radius-lg) border px-3 py-2.5 text-left"
              :class="
                ragOptions.mode === 'full'
                  ? 'border-primary/35 bg-primary/10'
                  : 'border-(--line-soft) bg-(--surface-panel-soft)'
              "
              @click="setRagMode('full')"
            >
              <span
                class="text-[13px] font-semibold"
                :class="
                  ragOptions.mode === 'full'
                    ? 'text-primary'
                    : 'text-(--text-strong)'
                "
              >
                {{ t("chat.context.ragMode.full") }}
              </span>
              <span class="text-xs leading-5 text-(--text-faint)">
                {{ t("chat.context.ragMode.fullHelp") }}
              </span>
            </button>
          </div>
        </section>

        <!-- 检索增强开关：重排序 / 独立查询改写 -->
        <section class="grid gap-3 border-t border-(--line-soft) pt-4">
          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <Label class="text-[13px]">
                {{ t("chat.context.options.rerank") }}
              </Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                {{ t("chat.context.options.rerankHelp") }}
              </p>
            </div>
            <Switch
              :model-value="ragOptions.rerankEnabled"
              :aria-label="t('chat.context.options.rerankAria')"
              @update:model-value="
                globalChatStore.setRerankEnabled(Boolean($event))
              "
            />
          </div>

          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-3"
          >
            <div>
              <Label class="text-[13px]">
                {{ t("chat.context.options.standalone") }}
              </Label>
              <p class="mt-1 text-xs leading-5 text-(--text-faint)">
                {{ t("chat.context.options.standaloneHelp") }}
              </p>
            </div>
            <Switch
              :model-value="ragOptions.standaloneEnabled"
              :aria-label="t('chat.context.options.standaloneAria')"
              @update:model-value="
                globalChatStore.setStandaloneEnabled(Boolean($event))
              "
            />
          </div>
        </section>

        <!-- 管理员自定义 system prompt -->
        <section class="grid gap-2 border-t border-(--line-soft) pt-4">
          <div>
            <Label
              for="admin-system-prompt"
              class="text-[13px] font-semibold text-(--text-strong)"
            >
              {{ t("chat.context.prompt.title") }}
            </Label>
            <p class="mt-1 text-xs leading-5 text-(--text-faint)">
              {{ t("chat.context.prompt.help") }}
            </p>
          </div>
          <Textarea
            id="admin-system-prompt"
            class="min-h-28 border-(--line-soft) bg-(--surface-base) text-sm"
            :model-value="adminSystemPrompt"
            :placeholder="t('chat.context.prompt.placeholder')"
            @update:model-value="globalChatStore.setAdminSystemPrompt"
          />
        </section>
      </div>
    </SheetContent>
  </Sheet>
</template>
