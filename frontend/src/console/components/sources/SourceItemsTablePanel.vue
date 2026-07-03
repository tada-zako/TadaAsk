<script setup lang="ts">
import { computed, ref } from "vue";
import {
  CirclePlay,
  Download,
  FileText,
  Globe2,
  Pencil,
  Trash2,
  XCircle,
} from "@lucide/vue";

import type {
  SourceItemRow,
  SourceTone,
} from "@/console/services/source-workspace";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Progress } from "@/shared/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";

// 复选框三态值：全选 / 部分选中 / 全不选
type CheckboxValue = boolean | "indeterminate";

const props = defineProps<{
  sourceType: "local-file" | "web-crawl";
  rows: SourceItemRow[];
  selectedItemUids: string[];
  isLoading?: boolean;
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "updateSelection", itemUids: string[]): void;
  (event: "indexItems", itemUids: string[]): void;
  (event: "pauseItems", itemUids: string[]): void;
  (event: "resumeItems", itemUids: string[]): void;
  (event: "downloadItem", itemUid: string): void;
  (event: "renameItem", itemUid: string, title: string): void;
  (event: "deleteItems", itemUids: string[]): void;
}>();

// 弹窗状态
const renameOpen = ref(false);
const renameTarget = ref<SourceItemRow | null>(null);
const renameTitle = ref("");
const deleteOpen = ref(false);
const deleteTargetUids = ref<string[]>([]);

const isWebCrawl = computed(() => props.sourceType === "web-crawl");
const entityLabel = computed(() => (isWebCrawl.value ? "pages" : "files"));
const selectedUidSet = computed(() => new Set(props.selectedItemUids));
const rowUidSet = computed(() => new Set(props.rows.map((row) => row.uid)));
const selectedRows = computed(() =>
  props.rows.filter((row) => selectedUidSet.value.has(row.uid)),
);
const selectedLabel = computed(
  () => `Selected: ${selectedRows.value.length} ${entityLabel.value}`,
);
// 表头复选框三态：全选 true / 部分 indeterminate / 全不选 false
const headerChecked = computed<CheckboxValue>(() => {
  if (!props.rows.length || !selectedRows.value.length) {
    return false;
  }

  if (selectedRows.value.length === props.rows.length) {
    return true;
  }

  return "indeterminate";
});

// 批量操作按钮启用判定：已选行中只要有一条可操作即启用
const canBulkIndex = computed(() =>
  selectedRows.value.some((row) => row.canIndex),
);
const canBulkDelete = computed(() =>
  selectedRows.value.some((row) => row.canDelete),
);

function toggleAll(value: CheckboxValue): void {
  const next = new Set(props.selectedItemUids);

  if (normalizeChecked(value)) {
    for (const row of props.rows) {
      next.add(row.uid);
    }
  } else {
    for (const rowUid of rowUidSet.value) {
      next.delete(rowUid);
    }
  }

  emit("updateSelection", Array.from(next));
}

function toggleRow(row: SourceItemRow, value: CheckboxValue): void {
  const next = new Set(props.selectedItemUids);

  if (normalizeChecked(value)) {
    next.add(row.uid);
  } else {
    next.delete(row.uid);
  }

  emit("updateSelection", Array.from(next));
}

function handleToggleAll(value: CheckboxValue): void {
  toggleAll(value);
}

function handleToggleRow(row: SourceItemRow, value: CheckboxValue): void {
  toggleRow(row, value);
}

function normalizeChecked(value: CheckboxValue): boolean {
  return value === true;
}

// 对已选行中满足条件的子项执行批量操作，避免重复 emit
function emitForSelected(
  eventName: "indexItems" | "pauseItems" | "resumeItems",
  predicate: (row: SourceItemRow) => boolean,
): void {
  const itemUids = selectedRows.value.filter(predicate).map((row) => row.uid);

  if (!itemUids.length) {
    return;
  }

  if (eventName === "indexItems") {
    emit("indexItems", itemUids);
  } else if (eventName === "pauseItems") {
    emit("pauseItems", itemUids);
  } else {
    emit("resumeItems", itemUids);
  }
}

function openRename(row: SourceItemRow): void {
  renameTarget.value = row;
  renameTitle.value = row.title;
  renameOpen.value = true;
}

function submitRename(): void {
  const title = renameTitle.value.trim();

  if (renameTarget.value && title) {
    emit("renameItem", renameTarget.value.uid, title);
  }

  renameOpen.value = false;
}

function openDelete(itemUids: string[]): void {
  deleteTargetUids.value = itemUids;
  deleteOpen.value = itemUids.length > 0;
}

function submitDelete(): void {
  if (deleteTargetUids.value.length) {
    emit("deleteItems", deleteTargetUids.value);
  }

  deleteOpen.value = false;
  deleteTargetUids.value = [];
}

// 状态徽标色调映射
function badgeClass(tone: SourceTone): string {
  if (tone === "success") {
    return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  }

  if (tone === "warning") {
    return "border-yellow-300/25 bg-yellow-300/10 text-yellow-100";
  }

  if (tone === "danger") {
    return "border-red-400/25 bg-red-400/10 text-red-100";
  }

  return "border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)";
}
</script>

<template>
  <TooltipProvider>
    <!-- source item table 主体 -->
    <section class="console-table-panel">
      <!-- 批操作栏 -->
      <div
        class="flex min-h-13 items-center justify-between gap-4 border-b border-(--line-soft) bg-[#111215] px-4 max-[760px]:grid max-[760px]:py-3"
      >
        <div class="flex items-center gap-3">
          <strong class="text-[13px] text-(--text-strong)">
            {{ selectedLabel }}
          </strong>
          <span class="h-5 w-px bg-(--line)"></span>
          <span class="text-xs text-(--text-faint)">
            Batch operations apply to checked rows.
          </span>
        </div>
        <div class="flex flex-wrap justify-end gap-2 max-[760px]:justify-start">
          <Button
            type="button"
            :aria-label="`Index selected ${entityLabel}`"
            variant="outline"
            size="sm"
            :disabled="isMutating || !canBulkIndex"
            @click="emitForSelected('indexItems', (row) => row.canIndex)"
          >
            <CirclePlay class="size-4" />
            Index
          </Button>
          <Button
            type="button"
            :aria-label="`Delete selected ${entityLabel}`"
            variant="outline"
            size="sm"
            class="border-red-400/35 text-red-100 hover:bg-red-400/10"
            :disabled="isMutating || !canBulkDelete"
            @click="
              openDelete(
                selectedRows
                  .filter((row) => row.canDelete)
                  .map((row) => row.uid),
              )
            "
          >
            <Trash2 class="size-4" />
            Delete
          </Button>
        </div>
      </div>

      <Table class="console-scrollbar min-w-[58rem] table-fixed">
        <colgroup>
          <col class="w-12" />
          <col class="w-[34%]" />
          <col class="w-[10.5rem]" />
          <col class="w-[8rem]" />
          <col class="w-[12rem]" />
          <col class="w-[11.5rem]" />
        </colgroup>

        <!-- table header -->
        <TableHeader>
          <TableRow>
            <TableHead class="text-center">
              <Checkbox
                :model-value="headerChecked"
                :aria-label="`Select all ${entityLabel}`"
                class="mx-auto"
                :disabled="isLoading || rows.length === 0"
                @update:model-value="handleToggleAll"
              />
            </TableHead>
            <TableHead>{{ isWebCrawl ? "Page" : "File" }}</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Indexing</TableHead>
            <TableHead class="text-center">Actions</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          <!-- 加载进度条 -->
          <TableRow v-if="isLoading">
            <TableCell colspan="6" class="h-24 text-center text-(--text-muted)">
              Loading source items...
            </TableCell>
          </TableRow>

          <TableRow v-else-if="rows.length === 0">
            <TableCell colspan="6" class="h-24 text-center text-(--text-muted)">
              No source items found.
            </TableCell>
          </TableRow>

          <TableRow v-for="row in rows" v-else :key="row.uid">
            <TableCell class="text-center">
              <Checkbox
                :model-value="selectedUidSet.has(row.uid)"
                :aria-label="`Select ${row.title}`"
                class="mx-auto"
                @update:model-value="handleToggleRow(row, $event)"
              />
            </TableCell>
            <TableCell>
              <div class="grid min-w-0 gap-1">
                <div class="flex min-w-0 items-center gap-2">
                  <Globe2
                    v-if="isWebCrawl"
                    class="size-4 shrink-0 text-blue-300"
                  />
                  <FileText v-else class="size-4 shrink-0 text-blue-300" />
                  <strong class="truncate">{{ row.title }}</strong>
                </div>
                <span
                  v-if="isWebCrawl"
                  class="truncate text-xs text-(--text-faint)"
                >
                  {{ row.displayOrigin }}
                </span>
              </div>
            </TableCell>
            <TableCell>{{ row.updatedLabel }}</TableCell>
            <TableCell>
              <Badge :class="badgeClass(row.statusTone)">
                {{ row.statusLabel }}
              </Badge>
            </TableCell>
            <TableCell>
              <div v-if="row.showProgress" class="flex w-40 items-center gap-2">
                <Progress
                  class="h-1.5 bg-(--surface-panel-soft)"
                  :model-value="row.progress ?? 0"
                />
                <span class="w-8 text-right text-[11px] text-(--text-faint)">
                  {{ row.progress ?? 0 }}%
                </span>
              </div>
              <span
                v-else-if="row.status === 'completed'"
                class="text-xs text-emerald-200"
              >
                Ready
              </span>
              <span v-else class="text-xs text-(--text-faint)">
                Not indexed
              </span>
            </TableCell>
            <TableCell>
              <!-- Action 栏 -->
              <div class="flex items-center justify-center gap-1">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      :aria-label="`${row.canPause ? 'Pause' : row.canResume ? 'Resume' : 'Index'} ${row.title}`"
                      variant="ghost"
                      size="icon-sm"
                      :disabled="
                        isMutating ||
                        (!row.canIndex && !row.canPause && !row.canResume)
                      "
                      @click="
                        row.canPause
                          ? emit('pauseItems', [row.uid])
                          : row.canResume
                            ? emit('resumeItems', [row.uid])
                            : emit('indexItems', [row.uid])
                      "
                    >
                      <XCircle v-if="row.canPause" class="size-4" />
                      <CirclePlay v-else class="text-primary size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {{
                      row.canPause
                        ? "Pause"
                        : row.canResume
                          ? "Resume"
                          : "Index"
                    }}
                  </TooltipContent>
                </Tooltip>

                <Tooltip v-if="row.canDownload">
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      :aria-label="`Download ${row.title}`"
                      variant="ghost"
                      size="icon-sm"
                      :disabled="isMutating"
                      @click="emit('downloadItem', row.uid)"
                    >
                      <Download class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Download</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      :aria-label="`Rename ${row.title}`"
                      variant="ghost"
                      size="icon-sm"
                      :disabled="isMutating || !row.canRename"
                      @click="openRename(row)"
                    >
                      <Pencil class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Rename</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      :aria-label="`Delete ${row.title}`"
                      variant="ghost"
                      size="icon-sm"
                      class="text-red-100 hover:bg-red-400/10 hover:text-red-100"
                      :disabled="isMutating || !row.canDelete"
                      @click="openDelete([row.uid])"
                    >
                      <Trash2 class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Delete</TooltipContent>
                </Tooltip>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  </TooltipProvider>

  <!-- 重命名弹窗 -->
  <Dialog v-model:open="renameOpen">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Rename source item</DialogTitle>
      </DialogHeader>
      <div class="grid gap-2 py-2">
        <Label for="source-item-title">Title</Label>
        <Input
          id="source-item-title"
          v-model="renameTitle"
          @keyup.enter="submitRename"
        />
      </div>
      <DialogFooter>
        <Button
          type="button"
          aria-label="Cancel rename source item"
          variant="outline"
          @click="renameOpen = false"
        >
          Cancel
        </Button>
        <Button
          type="button"
          aria-label="Confirm rename source item"
          :disabled="isMutating || !renameTitle.trim()"
          @click="submitRename"
        >
          Rename
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- 删除确认弹窗 -->
  <AlertDialog v-model:open="deleteOpen">
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>Delete selected item?</AlertDialogTitle>
        <AlertDialogDescription>
          This removes the source item and cleans up related file/vector data
          when supported by the backend.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <AlertDialogAction
          class="bg-red-500 text-white hover:bg-red-500/90"
          @click="submitDelete"
        >
          Delete
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
