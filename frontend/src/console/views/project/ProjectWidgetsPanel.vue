<script setup lang="ts">
import { reactive, ref } from "vue";
import { Ellipsis, Pencil, Plus, Trash2 } from "@lucide/vue";

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
        {{ widgets.length }} deployments
      </p>
      <!-- 创建 Widget 对话框 -->
      <Dialog v-model:open="createDialogOpen">
        <DialogTrigger as-child>
          <Button
            type="button"
            aria-label="Create widget"
            size="sm"
            :disabled="isMutating"
          >
            <Plus class="size-4" />
            Create
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create widget</DialogTitle>
            <DialogDescription>
              Creates a ProjectWidget deployment instance.
            </DialogDescription>
          </DialogHeader>
          <div class="grid gap-4">
            <!-- Widget 名称 -->
            <div class="grid gap-2">
              <Label for="widget-name">Widget name</Label>
              <Input
                id="widget-name"
                v-model="createForm.name"
                placeholder="Docs production"
              />
            </div>
            <!-- 部署站点域名 -->
            <div class="grid gap-2">
              <Label for="site-origin">Site origin</Label>
              <Input
                id="site-origin"
                v-model="createForm.siteOrigin"
                placeholder="https://docs.example.com"
              />
              <p class="text-muted-foreground text-xs leading-5">
                Normalized origin used by project/widget scoped CORS checks.
              </p>
            </div>
            <!-- 启用状态开关 -->
            <div class="flex items-start gap-3">
              <Switch
                :model-value="createForm.isEnabled"
                aria-label="Enable widget after creation"
                @update:model-value="createForm.isEnabled = Boolean($event)"
              />
              <div class="grid gap-1">
                <strong class="text-sm">Enabled</strong>
                <span class="text-muted-foreground text-xs">
                  Visitor widget requests are allowed from this origin.
                </span>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              aria-label="Cancel widget creation"
              variant="outline"
              @click="createDialogOpen = false"
            >
              Cancel
            </Button>
            <Button
              type="button"
              aria-label="Confirm create widget"
              :disabled="isMutating"
              @click="submitCreate"
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

    <!-- Widget 部署列表表格 -->
    <Table class="console-scrollbar">
      <TableHeader>
        <TableRow>
          <TableHead>Widget</TableHead>
          <TableHead>Site origin</TableHead>
          <TableHead>Enabled</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Updated</TableHead>
          <TableHead class="w-16 text-right">Actions</TableHead>
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
              :aria-label="`${widget.name} widget enabled`"
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
                  :aria-label="`${widget.name} widget actions`"
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
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  @select="toggleWidget(widget, !widget.isEnabled)"
                >
                  {{ widget.enabledActionLabel }}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                  @select="emit('deleteWidget', widget.uid)"
                >
                  <Trash2 class="size-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
        <TableRow v-if="widgets.length === 0">
          <TableCell colspan="6" class="h-28 text-center text-(--text-faint)">
            No widget deployments yet.
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <!-- 编辑 Widget 对话框 -->
    <Dialog v-model:open="editDialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit widget</DialogTitle>
          <DialogDescription>
            Updates the widget deployment used by visitor CORS checks.
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-4">
          <div class="grid gap-2">
            <Label for="edit-widget-name">Widget name</Label>
            <Input id="edit-widget-name" v-model="editForm.name" />
          </div>
          <div class="grid gap-2">
            <Label for="edit-site-origin">Site origin</Label>
            <Input id="edit-site-origin" v-model="editForm.siteOrigin" />
          </div>
          <div class="flex items-start gap-3">
            <Switch
              :model-value="editForm.isEnabled"
              aria-label="Edit widget enabled"
              @update:model-value="editForm.isEnabled = Boolean($event)"
            />
            <div class="grid gap-1">
              <strong class="text-sm">Enabled</strong>
              <span class="text-muted-foreground text-xs">
                Visitor widget requests are allowed from this origin.
              </span>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            aria-label="Cancel widget edit"
            variant="outline"
            @click="editDialogOpen = false"
          >
            Cancel
          </Button>
          <Button
            type="button"
            aria-label="Confirm edit widget"
            :disabled="isMutating"
            @click="submitEdit"
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>
