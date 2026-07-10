<script setup lang="ts">
import { reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { Ellipsis, Pencil, Plus, Trash2, Power } from "@lucide/vue";

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

defineProps<{
  isMutating?: boolean;
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
const editingWidgetUid = ref<string | null>(null);

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
    <Table class="console-scrollbar">
      <TableHeader>
        <TableRow>
          <TableHead>{{ t("project.widgets.table.widget") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.siteOrigin") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.enabled") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.created") }}</TableHead>
          <TableHead>{{ t("project.widgets.table.updated") }}</TableHead>
          <TableHead class="w-16 text-right">
            {{ t("project.widgets.table.actions") }}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="widget in widgets" :key="widget.uid">
          <TableCell>
            <strong>{{ widget.name }}</strong>
          </TableCell>
          <TableCell>{{ widget.siteOrigin }}</TableCell>
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
          <TableCell class="text-right">
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
          <TableCell colspan="6" class="h-28 text-center text-(--text-faint)">
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
  </section>
</template>
