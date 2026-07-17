<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { Ellipsis, ExternalLink, Link, Unlink } from "@lucide/vue";

import { Badge } from "@/shared/components/ui/badge";
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
import { Label } from "@/shared/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import type { ProjectSourceRow } from "@/console/services/project-workspace";

const props = defineProps<{
  availableSources: ProjectSourceRow[]; // 可导入的全局 Sources
  isMutating?: boolean; // 是否在进行操作
  sources: ProjectSourceRow[];
}>();

const emit = defineEmits<{
  importSources: [sourceUids: string[]];
  openGlobalSources: [];
  openSource: [sourceUid: string];
  unbindSource: [sourceUid: string];
}>();

const { t } = useI18n();
const importDialogOpen = ref(false);
const selectedSourceUid = ref("");

watch(
  () => props.availableSources,
  (sources) => {
    // 候选列表刷新后，保证 dialog 中的选择仍然有效。
    if (!sources.some((source) => source.uid === selectedSourceUid.value)) {
      selectedSourceUid.value = sources[0]?.uid ?? "";
    }
  },
  { immediate: true },
);

// 触发 source 导入事件
function submitImport() {
  if (!selectedSourceUid.value) {
    return;
  }

  emit("importSources", [selectedSourceUid.value]);
  // 关闭导入对话框
  importDialogOpen.value = false;
}

// 根据 source tone 返回对应的 badge 样式
function badgeClass(
  tone: ProjectSourceRow["statusTone"] | ProjectSourceRow["visibilityTone"],
): string {
  const classes = {
    danger: "border-red-400/25 bg-red-400/10 text-red-100",
    muted: "border-(--line-soft) bg-(--surface-panel-soft) text-(--text-muted)",
    success: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
    warning: "border-yellow-300/25 bg-yellow-300/10 text-yellow-100",
  };

  return classes[tone];
}
</script>

<template>
  <!-- 项目关联数据源面板 -->
  <section class="console-table-panel">
    <!-- 面板头部操作栏 -->
    <div
      class="flex min-h-12 items-center justify-between gap-4 border-b border-(--line-soft) px-4 max-[760px]:items-start max-[760px]:py-3"
    >
      <p class="text-xs text-(--text-faint)">
        {{ t("project.sources.linkedCount", { count: sources.length }) }}
      </p>
      <div
        class="flex shrink-0 flex-wrap justify-end gap-2 max-[760px]:justify-start"
      >
        <Button
          type="button"
          :aria-label="t('project.sources.openGlobalSources')"
          variant="outline"
          size="sm"
          @click="emit('openGlobalSources')"
        >
          <ExternalLink class="size-4" />
          {{ t("project.sources.globalSources") }}
        </Button>
        <!-- 导入数据源对话框 -->
        <Dialog v-model:open="importDialogOpen">
          <DialogTrigger as-child>
            <Button
              type="button"
              :aria-label="t('project.sources.importSource')"
              size="sm"
              :disabled="isMutating || availableSources.length === 0"
            >
              <Link class="size-4" />
              {{ t("common.actions.import") }}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{{ t("project.sources.dialogTitle") }}</DialogTitle>
              <DialogDescription>
                {{ t("project.sources.dialogDescription") }}
              </DialogDescription>
            </DialogHeader>
            <div class="grid gap-4">
              <div class="grid gap-2">
                <Label for="source-pick">
                  {{ t("project.sources.sourceLabel") }}
                </Label>
                <select
                  id="source-pick"
                  v-model="selectedSourceUid"
                  class="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-9 w-full rounded-(--console-radius-md) border px-3 py-1 text-sm text-(--text-body) shadow-xs transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option
                    v-for="source in availableSources"
                    :key="source.uid"
                    :value="source.uid"
                  >
                    {{ source.name }} · {{ source.typeLabel }}
                  </option>
                </select>
                <p class="text-muted-foreground text-xs leading-5">
                  {{ t("project.sources.importHelp") }}
                </p>
              </div>
              <div
                class="border-primary/30 bg-primary/10 grid grid-cols-[24px_minmax(0,1fr)] gap-3 rounded-lg border p-3"
              >
                <span class="bg-primary mt-1 size-2 rounded-full"></span>
                <div>
                  <strong class="text-sm">
                    {{ t("project.sources.bindingOnlyTitle") }}
                  </strong>
                  <p class="text-muted-foreground mt-1 text-xs leading-5">
                    {{ t("project.sources.bindingOnlyBody") }}
                  </p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                :aria-label="t('project.sources.cancelImport')"
                variant="outline"
                @click="importDialogOpen = false"
              >
                {{ t("common.actions.cancel") }}
              </Button>
              <Button
                type="button"
                :aria-label="t('project.sources.confirmImport')"
                :disabled="isMutating || !selectedSourceUid"
                @click="submitImport"
              >
                {{ t("common.actions.import") }}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>

    <!-- 数据源列表表格 -->
    <Table class="console-scrollbar min-w-[54rem] table-fixed">
      <colgroup>
        <col class="w-[13rem]" />
        <col class="w-[9rem]" />
        <col class="w-[8rem]" />
        <col class="w-[8rem]" />
        <col class="w-[8rem]" />
        <col class="w-[5rem]" />
      </colgroup>

      <TableHeader>
        <TableRow>
          <TableHead>{{ t("project.sources.table.source") }}</TableHead>
          <TableHead>{{ t("project.sources.table.type") }}</TableHead>
          <TableHead>{{ t("project.sources.table.visibility") }}</TableHead>
          <TableHead>{{ t("project.sources.table.status") }}</TableHead>
          <TableHead>{{ t("project.sources.table.lastUpdated") }}</TableHead>
          <TableHead class="w-16 text-center">
            {{ t("project.sources.table.actions") }}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="source in sources" :key="source.uid">
          <TableCell class="overflow-hidden">
            <strong class="block truncate">{{ source.name }}</strong>
          </TableCell>
          <TableCell>{{ source.typeLabel }}</TableCell>
          <TableCell>
            <Badge :class="badgeClass(source.visibilityTone)">
              {{ source.visibilityLabel }}
            </Badge>
          </TableCell>
          <TableCell>
            <Badge :class="badgeClass(source.statusTone)">
              {{ source.statusLabel }}
            </Badge>
          </TableCell>
          <TableCell>{{ source.lastUpdatedLabel }}</TableCell>
          <TableCell class="text-center">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button
                  type="button"
                  :aria-label="
                    t('project.sources.sourceActions', { name: source.name })
                  "
                  variant="outline"
                  size="icon-sm"
                  :disabled="isMutating"
                >
                  <Ellipsis class="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem @select="emit('openSource', source.uid)">
                  <ExternalLink class="size-4" />
                  {{ t("project.sources.viewContents") }}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive"
                  @select="emit('unbindSource', source.uid)"
                >
                  <Unlink class="size-4" />
                  {{ t("project.sources.unbind") }}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
        <TableRow v-if="sources.length === 0">
          <TableCell colspan="6" class="h-28 text-center text-(--text-faint)">
            {{ t("project.sources.empty") }}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
