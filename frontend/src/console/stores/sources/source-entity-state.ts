import type { Ref } from "vue";
import type {
  SourceItemProcessStatus,
  SourceItemRead,
  SourceRead,
} from "@/console/api/sources";

export interface SourceEntityStateContext {
  sources: Ref<SourceRead[]>;
  currentSource: Ref<SourceRead | null>;
  itemsBySourceUid: Ref<Record<string, SourceItemRead[]>>;
  pruneItemSelection: (sourceUid: string, items: SourceItemRead[]) => void;
}

// Source 实体状态管理：增删改查、局部 patch、列表同步
export function createSourceEntityState(context: SourceEntityStateContext) {
  const { currentSource, itemsBySourceUid, pruneItemSelection, sources } =
    context;

  function upsertSource(source: SourceRead): void {
    const index = sources.value.findIndex((item) => item.uid === source.uid);

    if (index === -1) {
      sources.value = [source, ...sources.value];
    } else {
      sources.value = sources.value.map((item) =>
        item.uid === source.uid ? source : item,
      );
    }

    if (currentSource.value?.uid === source.uid) {
      currentSource.value = source;
    }
  }

  function syncCurrentSourceFromList(): void {
    if (!currentSource.value) {
      return;
    }

    currentSource.value =
      sources.value.find((source) => source.uid === currentSource.value?.uid) ??
      null;
  }

  function setSourceItems(sourceUid: string, items: SourceItemRead[]): void {
    itemsBySourceUid.value = {
      ...itemsBySourceUid.value,
      [sourceUid]: items,
    };

    pruneItemSelection(sourceUid, items);
  }

  function patchSourceStatus(
    sourceUid: string,
    status: SourceRead["status"],
  ): void {
    const patch = (source: SourceRead): SourceRead =>
      source.uid === sourceUid ? { ...source, status } : source;

    sources.value = sources.value.map(patch);

    if (currentSource.value?.uid === sourceUid) {
      currentSource.value = patch(currentSource.value);
    }
  }

  function patchSourceItem(sourceUid: string, item: SourceItemRead): void {
    setSourceItems(
      sourceUid,
      mergeSourceItems(itemsBySourceUid.value[sourceUid] ?? [], [item]),
    );
  }

  function patchSourceItems(sourceUid: string, items: SourceItemRead[]): void {
    setSourceItems(
      sourceUid,
      mergeSourceItems(itemsBySourceUid.value[sourceUid] ?? [], items),
    );
  }

  function patchSourceItemStatus(
    sourceUid: string,
    sourceItemUid: string,
    status: SourceItemProcessStatus,
  ): void {
    const current = itemsBySourceUid.value[sourceUid] ?? [];
    setSourceItems(
      sourceUid,
      current.map((item) =>
        item.uid === sourceItemUid ? { ...item, status } : item,
      ),
    );
  }

  function removeSourceFromState(sourceUid: string): void {
    sources.value = sources.value.filter((source) => source.uid !== sourceUid);

    if (currentSource.value?.uid === sourceUid) {
      currentSource.value = null;
    }

    const nextItems = { ...itemsBySourceUid.value };
    delete nextItems[sourceUid];
    itemsBySourceUid.value = nextItems;
  }

  function removeSourceItemFromState(
    sourceUid: string,
    sourceItemUid: string,
  ): void {
    setSourceItems(
      sourceUid,
      (itemsBySourceUid.value[sourceUid] ?? []).filter(
        (item) => item.uid !== sourceItemUid,
      ),
    );
  }

  // 批量更新子项状态，支持每条更新的进度回调
  function markSourceItemsStatus(
    sourceUid: string,
    sourceItemUids: string[],
    status: SourceItemProcessStatus,
    onProgress?: (sourceItemUid: string) => void,
  ): void {
    for (const sourceItemUid of sourceItemUids) {
      patchSourceItemStatus(sourceUid, sourceItemUid, status);
      onProgress?.(sourceItemUid);
    }
  }

  return {
    markSourceItemsStatus,
    patchSourceItem,
    patchSourceItems,
    patchSourceItemStatus,
    patchSourceStatus,
    removeSourceFromState,
    removeSourceItemFromState,
    setSourceItems,
    syncCurrentSourceFromList,
    upsertSource,
  };
}

// 合并子项更新列表：已存在的替换，新增的追加到末尾。
function mergeSourceItems(
  current: SourceItemRead[],
  updates: SourceItemRead[],
): SourceItemRead[] {
  const updateMap = new Map(updates.map((item) => [item.uid, item]));
  const merged = current.map((item) => updateMap.get(item.uid) ?? item);
  const currentUidSet = new Set(current.map((item) => item.uid));
  const appended = updates.filter((item) => !currentUidSet.has(item.uid));

  return [...merged, ...appended];
}
