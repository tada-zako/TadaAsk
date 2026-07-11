<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { LoaderCircle, Trash2, TriangleAlert } from "@lucide/vue";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

const props = defineProps<{
  projectName: string;
  isDeleting: boolean;
  errorMessage: string | null;
}>();
const { t } = useI18n();
const emit = defineEmits<{ confirm: [] }>();
// 删除确认：用户必须在输入框中键入完整项目名才能解锁删除按钮
const open = ref(false);
const confirmation = ref("");
const canDelete = computed(
  () => confirmation.value === props.projectName && !props.isDeleting,
);

// 关闭弹窗时清空输入，防止下次打开残留上次的确认文本
watch(open, (value) => {
  if (!value) confirmation.value = "";
});
</script>

<template>
  <!-- 项目危险区：删除流程 = 点击触发按钮 → AlertDialog 弹窗 → 输入项目名确认 → emit confirm
       删除按钮仅在用户输入与 projectName 完全一致且非删除中时启用 -->
  <section class="console-section">
    <header class="grid gap-1 px-0.5">
      <h2 class="text-xl leading-[1.35] font-bold text-red-200">
        {{ t("project.settings.danger.title") }}
      </h2>
      <p class="text-xs leading-5 text-(--text-faint)">
        {{ t("project.settings.danger.note") }}
      </p>
    </header>

    <section
      class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-6 rounded-(--console-radius-lg) border border-red-400/25 bg-red-400/[0.035] px-5 py-4.5 max-[620px]:grid-cols-1"
    >
      <div class="grid gap-1">
        <h3 class="text-[13px] font-semibold text-(--text-strong)">
          {{ t("project.settings.danger.deleteTitle") }}
        </h3>
        <p class="max-w-2xl text-xs leading-5 text-(--text-faint)">
          {{ t("project.settings.danger.deleteHelp") }}
        </p>
        <!-- 删除失败时展示的错误信息，由 store 的 deleteError 传入 -->
        <p v-if="errorMessage" class="mt-1 text-xs text-red-300">
          {{ errorMessage }}
        </p>
      </div>

      <AlertDialog v-model:open="open">
        <AlertDialogTrigger as-child>
          <Button
            type="button"
            variant="outline"
            class="border-red-400/30 bg-red-400/8 text-red-200 hover:bg-red-400/12 hover:text-red-100 max-[620px]:w-full"
          >
            <Trash2 class="size-3.5" />
            {{ t("project.settings.danger.deleteButton") }}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent
          class="gap-0 overflow-hidden border-(--line-strong) bg-[#0d0e10] p-0 shadow-[0_28px_100px_rgba(0,0,0,0.68)] sm:max-w-[31.25rem]"
        >
          <AlertDialogHeader
            class="border-b border-(--line-soft) px-5 py-4 text-left"
          >
            <AlertDialogTitle
              class="flex items-center gap-3 text-base font-semibold text-(--text-strong)"
            >
              <span
                class="grid size-8 place-items-center rounded-(--console-radius-md) border border-red-400/25 bg-red-400/8 text-red-300"
                ><Trash2 class="size-4"
              /></span>
              {{
                t("project.settings.danger.dialogTitle", {
                  project: projectName,
                })
              }}
            </AlertDialogTitle>
            <AlertDialogDescription class="sr-only">{{
              t("project.settings.danger.dialogDescription", {
                project: projectName,
              })
            }}</AlertDialogDescription>
          </AlertDialogHeader>
          <!-- 弹窗内容区：不可逆警告 + 项目名确认输入 -->
          <div class="grid gap-4 p-5">
            <div
              class="grid gap-2 rounded-(--console-radius-md) border border-red-400/20 bg-red-400/8 p-3"
            >
              <strong class="flex items-center gap-2 text-[13px] text-red-100"
                ><TriangleAlert class="size-4" />{{
                  t("project.settings.danger.warning")
                }}</strong
              >
              <p class="text-xs leading-5 text-red-100/70">
                {{ t("project.settings.danger.warningDetail") }}
              </p>
            </div>
            <!-- 确认输入：v-model 绑定 confirmation，canDelete 实时计算是否匹配 -->
            <div class="grid gap-2">
              <Label
                for="delete-project-confirmation"
                class="text-[13px] font-normal text-(--text-body)"
                >{{
                  t("project.settings.danger.confirmation", {
                    project: projectName,
                  })
                }}</Label
              >
              <Input
                id="delete-project-confirmation"
                v-model="confirmation"
                :disabled="isDeleting"
                class="h-10 border-(--line) bg-black/20 text-[13px] shadow-none"
              />
            </div>
          </div>
          <AlertDialogFooter
            class="border-t border-(--line-soft) bg-black/15 px-5 py-3.5"
          >
            <AlertDialogCancel
              type="button"
              :disabled="isDeleting"
              class="border-(--line) bg-transparent"
              >{{ t("project.settings.danger.cancel") }}</AlertDialogCancel
            >
            <AlertDialogAction
              type="button"
              :disabled="!canDelete"
              class="bg-red-500 text-white hover:bg-red-500/90 disabled:opacity-45"
              @click.prevent="emit('confirm')"
            >
              <LoaderCircle
                v-if="isDeleting"
                class="size-3.5 animate-spin"
              /><Trash2 v-else class="size-3.5" />
              {{
                isDeleting
                  ? t("project.settings.danger.deleting")
                  : t("project.settings.danger.deleteButton")
              }}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  </section>
</template>
