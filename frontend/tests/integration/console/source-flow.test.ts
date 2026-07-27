import { computed } from "vue";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/services/source-workspace", () => ({
  indexSourceItems: vi.fn(),
  listActiveSourceJobs: vi.fn(),
  loadSourceWorkspace: vi.fn(),
  streamRagJobEvents: vi.fn(),
  toSourceItemRow: vi.fn((item) => item),
  toSourceJobViewModel: vi.fn((job) => job),
  toSourceRow: vi.fn((source) => source),
}));

import {
  indexSourceItems,
  listActiveSourceJobs,
  loadSourceWorkspace,
  streamRagJobEvents,
  toSourceJobViewModel,
} from "@/console/services/source-workspace";
import { useSourceItemsRuntime } from "@/console/composables/sources/useSourceItemsRuntime";
import { useSourceStore } from "@/console/stores/source";

async function* events(values: unknown[]) {
  for (const value of values) yield value;
}

describe("source store + runtime integration", () => {
  it("索引任务 SSE 更新 source/item 状态并刷新完成后的 workspace", async () => {
    const sourceStore = useSourceStore();
    sourceStore.sources = [
      {
        uid: "source-1",
        sourceName: "Docs",
        sourceType: "local_file",
        isPublic: true,
        status: "pending",
        createdAt: "2026-07-01T00:00:00Z",
        updatedAt: "2026-07-01T00:00:00Z",
      },
    ] as never;
    sourceStore.setSourceItems("source-1", [
      {
        uid: "item-1",
        title: "guide",
        status: "pending",
        filename: "guide.md",
        originUrl: null,
        storageKey: "guide.md",
        createdAt: "2026-07-01T00:00:00Z",
        updatedAt: "2026-07-01T00:00:00Z",
      },
    ] as never);
    vi.mocked(indexSourceItems).mockResolvedValue({
      jobUid: "job-1",
      jobType: "indexing",
      sourceUid: "source-1",
      status: "queued",
    } as never);
    vi.mocked(toSourceJobViewModel).mockImplementation((job) => job as never);
    vi.mocked(streamRagJobEvents).mockResolvedValue(
      events([
        {
          event: "item_progress",
          sourceUid: "source-1",
          sourceStatus: "processing",
          sourceItemUid: "item-1",
          sourceItemStatus: "processing",
          itemProgress: 0.5,
        },
        {
          event: "item_completed",
          sourceUid: "source-1",
          sourceStatus: "completed",
          sourceItemUid: "item-1",
          sourceItemStatus: "completed",
          itemProgress: 1,
        },
      ]) as never,
    );
    vi.mocked(loadSourceWorkspace).mockResolvedValue({
      source: { ...sourceStore.sources[0], status: "completed" },
      sourceItemRows: [
        {
          sourceItem: {
            ...sourceStore.getSourceItems("source-1")[0],
            status: "completed",
          },
        },
      ],
    } as never);
    vi.mocked(listActiveSourceJobs).mockResolvedValue([]);
    const runtime = useSourceItemsRuntime({
      sourceUid: computed(() => "source-1"),
    });

    await runtime.indexItems(["item-1"]);
    await vi.waitFor(() =>
      expect(sourceStore.getSource("source-1")?.status).toBe("completed"),
    );

    expect(sourceStore.getSourceItems("source-1")).toMatchObject([
      { uid: "item-1", status: "completed" },
    ]);
    expect(loadSourceWorkspace).toHaveBeenCalledWith("source-1");
  });
});
