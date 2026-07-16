<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  Check,
  Code2,
  Copy,
  Ellipsis,
  ExternalLink,
  Pencil,
  Plus,
  Trash2,
  Power,
} from "@lucide/vue";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Switch } from "@/shared/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import type {
  ProjectWidgetCreate,
  ProjectWidgetRow,
  ProjectWidgetUpdate,
} from "@/console/services/project-workspace";
import { createWidgetDeploymentCode } from "@/console/services/widget-deployment";

// TODO: 正式文档地址确定后，只需替换这一处。
const WIDGET_CUSTOMIZATION_DOCS_URL =
  "https://github.com/tada-zako/ai_widget/blob/main/frontend/docs/tutorial/visitor-widget-customization.md";

const props = defineProps<{
  isMutating?: boolean;
  projectUid: string;
  widgets: ProjectWidgetRow[];
}>();

const emit = defineEmits<{
  createWidget: [input: ProjectWidgetCreate];
  deleteWidget: [widgetUid: string];
  updateWidget: [input: { widgetUid: string; payload: ProjectWidgetUpdate }];
}>();

const { t } = useI18n();
const createDialogOpen = ref(false);
const editDialogOpen = ref(false);
const deploymentDialogOpen = ref(false);
const editingWidgetUid = ref<string | null>(null);
const deployingWidget = ref<ProjectWidgetRow | null>(null);
const copyState = ref<"idle" | "copied" | "failed">("idle");

const deploymentCode = computed(() =>
  deployingWidget.value
    ? createWidgetDeploymentCode({
        projectUid: props.projectUid,
        widgetUid: deployingWidget.value.uid,
      })
    : null,
);

const missingDeploymentConfig = computed(() =>
  deploymentCode.value?.missingConfig
    .map((key) =>
      key === "apiBaseUrl" ? "VITE_API_BASE_URL" : "VITE_WIDGET_SCRIPT_URL",
    )
    .join(", "),
);

// Dialog 表单只维护本地输入，提交时交给页面容器执行 API。
const createForm = reactive<ProjectWidgetCreate>({
  isEnabled: true,
  name: "",
  siteOrigin: "",
});

const editForm = reactive<ProjectWidgetCreate>({
  isEnabled: true,
  name: "",
  siteOrigin: "",
});

function submitCreate() {
  if (!createForm.name.trim() || !createForm.siteOrigin.trim()) {
    return;
  }

  emit("createWidget", { ...createForm });
  createDialogOpen.value = false;
}

function openEdit(widget: ProjectWidgetRow) {
  editingWidgetUid.value = widget.uid;
  editForm.name = widget.name;
  editForm.siteOrigin = widget.siteOrigin;
  editForm.isEnabled = widget.isEnabled;
  editDialogOpen.value = true;
}

function submitEdit() {
  if (
    !editingWidgetUid.value ||
    !editForm.name.trim() ||
    !editForm.siteOrigin.trim()
  ) {
    return;
  }

  emit("updateWidget", {
    payload: { ...editForm },
    widgetUid: editingWidgetUid.value,
  });
  editDialogOpen.value = false;
}

function toggleWidget(widget: ProjectWidgetRow, isEnabled: boolean) {
  emit("updateWidget", {
    payload: { isEnabled },
    widgetUid: widget.uid,
  });
}

function openDeployment(widget: ProjectWidgetRow) {
  deployingWidget.value = widget;
  copyState.value = "idle";
  deploymentDialogOpen.value = true;
}

async function copyDeploymentCode() {
  const code = deploymentCode.value;
  if (!code || code.missingConfig.length > 0) {
    return;
  }

  try {
    await copyText(code.html);
    copyState.value = "copied";
  } catch {
    copyState.value = "failed";
  }
}

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard copy failed");
}
</script>

<template>
  <!-- Widget 部署管理面板 -->
  <section class="console-table-panel">
    <!-- 面板头部操作栏 -->
    <div
      class="flex min-h-12 items-center justify-between gap-4 border-b border-(--line-soft) px-4 max-[760px]:items-start max-[760px]:py-3"
    >
      <p class="text-xs text-(--text-faint)">
        {{ t("project.widgets.deploymentCount", { count: widgets.length }) }}
      </p>
      <!-- 创建 Widget 对话框 -->
      <Dialog v-model:open="createDialogOpen">
        <DialogTrigger as-child>
          <Button
            type="button"
            :aria-label="t('project.widgets.createWidget')"
            size="sm"
            :disabled="isMutating"
          >
            <Plus class="size-4" />
            {{ t("common.actions.create") }}
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{{
              t("project.widgets.dialogCreateTitle")
            }}</DialogTitle>
            <DialogDescription>
              {{ t("project.widgets.dialogCreateDescription") }}
            </DialogDescription>
          </DialogHeader>
          <div class="grid gap-4">
            <!-- Widget 名称 -->
            <div class="grid gap-2">
              <Label for="widget-name">
                {{ t("project.widgets.nameLabel") }}
              </Label>
              <Input
                id="widget-name"
                v-model="createForm.name"
                :placeholder="t('project.widgets.namePlaceholder')"
              />
            </div>
            <!-- 部署站点域名 -->
            <div class="grid gap-2">
              <Label for="site-origin">
                {{ t("project.widgets.siteOriginLabel") }}
              </Label>
              <Input
                id="site-origin"
                v-model="createForm.siteOrigin"
                :placeholder="t('project.widgets.siteOriginPlaceholder')"
              />
              <p class="text-muted-foreground text-xs leading-5">
                {{ t("project.widgets.siteOriginHelp") }}
              </p>
            </div>
            <!-- 启用状态开关 -->
            <div class="flex items-start gap-3">
              <Switch
                :model-value="createForm.isEnabled"
                :aria-label="t('project.widgets.enableAfterCreation')"
                @update:model-value="createForm.isEnabled = Boolean($event)"
              />
              <div class="grid gap-1">
                <strong class="text-sm">{{
                  t("project.widgets.enabled")
                }}</strong>
                <span class="text-muted-foreground text-xs">
                  {{ t("project.widgets.enabledHelp") }}
                </span>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              :aria-label="t('project.widgets.cancelCreate')"
              variant="outline"
              @click="createDialogOpen = false"
            >
              {{ t("common.actions.cancel") }}
            </Button>
            <Button
              type="button"
              :aria-label="t('project.widgets.confirmCreate')"
              :disabled="isMutating"
              @click="submitCreate"
            >
              {{ t("common.actions.create") }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

    <!-- Widget 部署列表表格 -->
    <Table class="console-scrollbar min-w-[68rem] table-fixed">
      <colgroup>
        <col />
        <col />
        <col class="w-[7rem]" />
        <col class="w-[9rem]" />
        <col class="w-[9rem]" />
        <col class="w-40" />
        <col class="w-24" />
      </colgroup>

      <TableHeader>
        <TableRow>
          <TableHead>{{ t("project.widgets.table.widget") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.siteOrigin") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.enabled") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.created") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.updated") }}</TableHead>
          <TableHead class="w-40 px-5 text-center">
            {{ t("project.widgets.table.deploy") }}
          </TableHead>
          <TableHead class="w-24 px-4 text-center">
            {{ t("project.widgets.table.actions") }}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="widget in widgets" :key="widget.uid">
          <TableCell class="overflow-hidden">
            <strong class="block truncate">{{ widget.name }}</strong>
          </TableCell>
          <TableCell class="overflow-hidden">
            <span class="block truncate">{{ widget.siteOrigin }}</span>
          </TableCell>
          <TableCell>
            <Switch
              :model-value="widget.isEnabled"
              :aria-label="
                t('project.widgets.widgetEnabled', { name: widget.name })
              "
              :disabled="isMutating"
              @update:model-value="toggleWidget(widget, Boolean($event))"
            />
          </TableCell>
          <TableCell>{{ widget.createdLabel }}</TableCell>
          <TableCell>{{ widget.updatedLabel }}</TableCell>
          <TableCell class="w-40 px-5 text-center">
            <Button
              type="button"
              :aria-label="
                t('project.widgets.deployWidget', { name: widget.name })
              "
              variant="ghost"
              size="sm"
              class="h-8 border-(--line) bg-(--surface-panel-soft) px-2.5 text-xs text-(--text-body) hover:bg-(--surface-hover) hover:text-(--text-strong)"
              :disabled="isMutating"
              @click="openDeployment(widget)"
            >
              <Code2 class="size-4" />
              <!-- {{ t("project.widgets.deploy") }} -->
            </Button>
          </TableCell>
          <TableCell class="w-24 px-4 text-center">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  :aria-label="
                    t('project.widgets.widgetActions', { name: widget.name })
                  "
                  variant="outline"
                  size="icon-sm"
                  :disabled="isMutating"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem @select="openEdit(widget)">
                  <Pencil class="size-4" />
                  {{ t("common.actions.edit") }}
                </DropdownMenuItem>
                <DropdownMenuItem
                  @select="toggleWidget(widget, !widget.isEnabled)"
                >
                  <Power class="size-4" />
                  {{ widget.enabledActionLabel }}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                  @select="emit('deleteWidget', widget.uid)"
                >
                  <Trash2 class="size-4" />
                  {{ t("common.actions.delete") }}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
        <TableRow v-if="widgets.length === 0">
          <TableCell colspan="7" class="h-28 text-center text-(--text-faint)">
            {{ t("project.widgets.empty") }}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <!-- 编辑 Widget 对话框 -->
    <Dialog v-model:open="editDialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t("project.widgets.dialogEditTitle") }}</DialogTitle>
          <DialogDescription>
            {{ t("project.widgets.dialogEditDescription") }}
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-4">
          <div class="grid gap-2">
            <Label for="edit-widget-name">
              {{ t("project.widgets.nameLabel") }}
            </Label>
            <Input id="edit-widget-name" v-model="editForm.name" />
          </div>
          <div class="grid gap-2">
            <Label for="edit-site-origin">
              {{ t("project.widgets.siteOriginLabel") }}
            </Label>
            <Input id="edit-site-origin" v-model="editForm.siteOrigin" />
          </div>
          <div class="flex items-start gap-3">
            <Switch
              :model-value="editForm.isEnabled"
              :aria-label="t('project.widgets.editEnabled')"
              @update:model-value="editForm.isEnabled = Boolean($event)"
            />
            <div class="grid gap-1">
              <strong class="text-sm">{{
                t("project.widgets.enabled")
              }}</strong>
              <span class="text-muted-foreground text-xs">
                {{ t("project.widgets.enabledHelp") }}
              </span>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            :aria-label="t('project.widgets.cancelEdit')"
            variant="outline"
            @click="editDialogOpen = false"
          >
            {{ t("common.actions.cancel") }}
          </Button>
          <Button
            type="button"
            :aria-label="t('project.widgets.confirmEdit')"
            :disabled="isMutating"
            @click="submitEdit"
          >
            {{ t("common.actions.save") }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 部署代码只依赖当前 project/widget 标识与构建环境地址。 -->
    <Dialog v-model:open="deploymentDialogOpen">
      <DialogContent
        class="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl"
      >
        <DialogHeader class="shrink-0 border-b border-(--line-soft) px-6 py-5">
          <div class="flex items-start gap-3 pr-8">
            <span
              class="border-primary/25 text-primary grid size-9 shrink-0 place-items-center rounded-(--console-radius-md) border"
            >
              <Code2 class="size-4" />
            </span>
            <div class="grid gap-1">
              <DialogTitle>{{ t("project.widgets.deployTitle") }}</DialogTitle>
              <DialogDescription>
                {{ t("project.widgets.deployDescription") }}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div
          v-if="deployingWidget && deploymentCode"
          class="console-scrollbar grid min-h-0 flex-1 gap-4 overflow-y-auto overscroll-contain p-6 max-[620px]:p-4"
        >
          <div
            class="flex min-w-0 items-center justify-between gap-4 border-b border-(--line-soft) px-0.5 pb-4"
          >
            <div class="min-w-0">
              <strong class="block truncate text-[13px] text-(--text-strong)">
                {{ deployingWidget.name }}
              </strong>
              <span
                class="mt-0.5 block truncate text-[11px] text-(--text-faint)"
              >
                {{ deployingWidget.siteOrigin }}
              </span>
            </div>
            <span
              class="w-fit rounded-full border px-2.5 py-1 text-[11px] font-semibold"
              :class="
                deployingWidget.isEnabled
                  ? 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200'
                  : 'border-yellow-300/25 bg-yellow-300/10 text-yellow-100'
              "
            >
              {{
                deployingWidget.isEnabled
                  ? t("project.widgets.deployEnabled")
                  : t("project.widgets.deployDisabled")
              }}
            </span>
          </div>

          <!-- Embed code 是部署流程的主要操作区。 -->
          <section
            class="grid gap-3 rounded-(--console-radius-lg) border border-(--line-soft) bg-(--surface-panel-soft) p-4"
          >
            <div class="flex items-center justify-between gap-3">
              <div>
                <h3 class="text-sm font-semibold text-(--text-strong)">
                  {{ t("project.widgets.embedCode") }}
                </h3>
                <p class="mt-1 text-xs text-(--text-faint)">
                  {{ t("project.widgets.embedCodeHelp") }}
                </p>
              </div>
              <Button
                type="button"
                :aria-label="t('project.widgets.copyCode')"
                variant="outline"
                size="sm"
                :disabled="deploymentCode.missingConfig.length > 0"
                @click="copyDeploymentCode"
              >
                <Check v-if="copyState === 'copied'" class="size-3.5" />
                <Copy v-else class="size-3.5" />
                {{
                  copyState === "copied"
                    ? t("project.widgets.copied")
                    : t("project.widgets.copy")
                }}
              </Button>
            </div>

            <!-- 配置提示与代码放在同一区域，避免用户找不到关键操作。 -->
            <div
              v-if="deploymentCode.missingConfig.length > 0"
              class="rounded-(--console-radius-md) border border-yellow-300/25 bg-yellow-300/10 px-3 py-2.5 text-xs leading-5 text-yellow-100"
            >
              {{
                t("project.widgets.deployMissingConfig", {
                  config: missingDeploymentConfig,
                })
              }}
            </div>
            <pre
              class="console-scrollbar max-h-56 overflow-auto rounded-(--console-radius-md) border border-(--line-soft) bg-[#070809] p-4 text-[12px] leading-6 text-cyan-50 shadow-inner"
            ><code>{{ deploymentCode.html }}</code></pre>
            <p v-if="copyState === 'failed'" class="text-xs text-red-300">
              {{ t("project.widgets.copyFailed") }}
            </p>
          </section>
        </div>

        <footer
          class="flex shrink-0 items-center justify-between gap-4 border-t border-(--line-soft) bg-(--surface-panel-soft) px-6 py-4 max-[620px]:items-start max-[620px]:px-4"
        >
          <div class="min-w-0">
            <strong class="block text-[12px] text-(--text-body)">
              {{ t("project.widgets.customizationDocsTitle") }}
            </strong>
            <span class="mt-0.5 block text-[11px] text-(--text-faint)">
              {{ t("project.widgets.customizationDocsHelp") }}
            </span>
          </div>
          <a
            :href="WIDGET_CUSTOMIZATION_DOCS_URL"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="t('project.widgets.openCustomizationDocs')"
            class="inline-flex shrink-0 items-center gap-1.5 rounded-(--console-radius-sm) px-2 py-1.5 text-[12px] font-medium text-(--text-muted) transition-colors hover:bg-(--surface-hover) hover:text-(--text-strong) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--accent)"
          >
            {{ t("project.widgets.viewCustomizationDocs") }}
            <ExternalLink class="size-3.5" />
          </a>
        </footer>
      </DialogContent>
    </Dialog>
  </section>
</template>
