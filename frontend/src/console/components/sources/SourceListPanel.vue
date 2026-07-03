<script setup lang="ts">
import { computed, ref } from "vue";
import { FileText, Funnel, Globe2, Search } from "@lucide/vue";

import SourceSettingsSheet from "./SourceSettingsSheet.vue";
import type { SourceRow } from "@/console/services/source-workspace";
import type { SourceUpdatePayload } from "@/console/api/sources";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

// filter by source type
type SourceTypeFilter = "all" | "local_file" | "web_crawl";

const props = defineProps<{
  sources: SourceRow[];
  isLoading?: boolean;
  isMutating?: boolean;
}>();

const emit = defineEmits<{
  (event: "openItems", source: SourceRow): void;
  (event: "updateSource", sourceUid: string, input: SourceUpdatePayload): void;
  (event: "deleteSource", sourceUid: string): void;
}>();

const query = ref("");
const typeFilter = ref<SourceTypeFilter>("all");

const filteredSources = computed(() => {
  // source type 过滤后的 sources
  const normalizedQuery = query.value.trim().toLowerCase();

  return props.sources.filter((source) => {
    const matchesType =
      typeFilter.value === "all" || source.sourceType === typeFilter.value;
    const matchesQuery =
      !normalizedQuery || source.name.toLowerCase().includes(normalizedQuery);

    return matchesType && matchesQuery;
  });
});

// 动态 badge 样式传递
function badgeClass(
  tone: SourceRow["statusTone"] | SourceRow["visibilityTone"],
) {
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
  <section class="console-table-panel">
    <div
      class="flex min-h-14 items-center justify-between gap-4 border-b border-(--line-soft) px-4 max-[760px]:grid max-[760px]:py-3"
    >
      <div class="relative w-[21.5rem] max-w-full">
        <Search
          class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-(--text-faint)"
        />
        <Input
          v-model="query"
          class="pl-9"
          placeholder="Search sources"
          :disabled="isLoading"
        />
      </div>
      <!-- 类型过滤下拉框 -->
      <Select v-model="typeFilter">
        <SelectTrigger
          class="w-[11.25rem] border-(--line) bg-(--surface-panel-soft) text-(--text-body)"
          aria-label="Filter sources by type"
        >
          <Funnel class="size-4 text-(--text-faint)" />
          <SelectValue placeholder="Filter by type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All types</SelectItem>
          <SelectItem value="local_file">Local file</SelectItem>
          <SelectItem value="web_crawl">Web crawl</SelectItem>
        </SelectContent>
      </Select>
    </div>

    <Table class="console-scrollbar">
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Visibility</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last updated</TableHead>
          <TableHead class="text-center">Workspace</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-if="isLoading">
          <TableCell colspan="6" class="h-24 text-center text-(--text-muted)">
            Loading sources...
          </TableCell>
        </TableRow>

        <TableRow v-else-if="filteredSources.length === 0">
          <TableCell colspan="6" class="h-24 text-center text-(--text-muted)">
            No sources found.
          </TableCell>
        </TableRow>

        <TableRow v-for="source in filteredSources" v-else :key="source.uid">
          <TableCell>
            <strong>{{ source.name }}</strong>
          </TableCell>
          <TableCell>
            <span class="flex items-center gap-2">
              <span
                class="text-primary grid size-6.5 place-items-center rounded-(--console-radius-sm) border border-(--line-soft) bg-(--surface-panel-soft)"
              >
                <Globe2
                  v-if="source.sourceType === 'web_crawl'"
                  class="size-3.5"
                />
                <FileText v-else class="size-3.5" />
              </span>
              <span class="text-xs font-semibold tracking-[0.08em]">
                {{ source.typeLabel }}
              </span>
            </span>
          </TableCell>
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
            <div class="flex items-center justify-center gap-2">
              <Button
                type="button"
                :aria-label="`Open ${source.name} source items`"
                variant="outline"
                size="sm"
                class="w-24 overflow-hidden"
                :disabled="!source.itemsRouteName || isMutating"
                @click="emit('openItems', source)"
              >
                Items
              </Button>
              <SourceSettingsSheet
                :is-mutating="isMutating"
                :source="source.source"
                @delete-source="emit('deleteSource', source.uid)"
                @update-source="emit('updateSource', source.uid, $event)"
              />
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
