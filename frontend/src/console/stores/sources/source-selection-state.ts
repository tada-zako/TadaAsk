import type { Ref } from "vue";
import type { SourceItemRead } from "@/console/api/sources";

export interface SourceSelectionStateContext {
  selectedItemUidsBySourceUid: Ref<Record<string, string[]>>;
}

// Source 子项选中状态管理：单选/多选切换、清除和无效清理
export function createSourceSelectionState(
  context: SourceSelectionStateContext,
) {
  const { selectedItemUidsBySourceUid } = context;

  function setItemSelection(sourceUid: string, sourceItemUids: string[]): void {
    selectedItemUidsBySourceUid.value = {
      ...selectedItemUidsBySourceUid.value,
      [sourceUid]: Array.from(new Set(sourceItemUids)),
    };
  }

  function toggleItemSelection(sourceUid: string, sourceItemUid: string): void {
    const current = selectedItemUidsBySourceUid.value[sourceUid] ?? [];
    const next = current.includes(sourceItemUid)
      ? current.filter((uid) => uid !== sourceItemUid)
      : [...current, sourceItemUid];

    setItemSelection(sourceUid, next);
  }

  function clearItemSelection(sourceUid: string): void {
    const next = { ...selectedItemUidsBySourceUid.value };
    delete next[sourceUid];
    selectedItemUidsBySourceUid.value = next;
  }

  function pruneItemSelection(
    sourceUid: string,
    items: SourceItemRead[],
  ): void {
    const validItemUids = new Set(items.map((item) => item.uid));
    const selected = selectedItemUidsBySourceUid.value[sourceUid] ?? [];

    setItemSelection(
      sourceUid,
      selected.filter((uid) => validItemUids.has(uid)),
    );
  }

  return {
    clearItemSelection,
    pruneItemSelection,
    setItemSelection,
    toggleItemSelection,
  };
}
