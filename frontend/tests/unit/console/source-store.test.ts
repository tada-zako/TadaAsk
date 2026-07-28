import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/services/source-workspace", () => ({
  createSource: vi.fn(),
  deleteSource: vi.fn(),
  deleteSourceItem: vi.fn(),
  downloadSourceItem: vi.fn(),
  indexSourceItems: vi.fn(),
  listActiveSourceJobs: vi.fn(),
  loadSourceItems: vi.fn(),
  loadSourcesWorkspace: vi.fn(),
  loadSourceWorkspace: vi.fn(),
  pauseSourceItems: vi.fn(),
  renameSourceItem: vi.fn(),
  resumeSourceItems: vi.fn(),
  syncWebCrawlSource: vi.fn(),
  toSourceJobViewModel: vi.fn((job) => job),
  toSourceRow: vi.fn((source) => source),
  updateSource: vi.fn(),
  uploadLocalSourceItems: vi.fn(),
}));

import {
  deleteSource,
  indexSourceItems,
  listActiveSourceJobs,
  loadSourceItems,
  loadSourcesWorkspace,
  pauseSourceItems,
  resumeSourceItems,
  toSourceJobViewModel,
  uploadLocalSourceItems,
} from "@/console/services/source-workspace";
import { useSourceStore } from "@/console/stores/source";

function source(uid: string, status = "pending") {
  return {
    uid,
    sourceName: uid,
    sourceType: "local_file",
    isPublic: true,
    status,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  };
}

function item(uid: string, status = "pending") {
  return {
    uid,
    title: uid,
    status,
    filename: `${uid}.txt`,
    originUrl: null,
    storageKey: `${uid}.txt`,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  };
}

describe("source store", () => {
  it("加载 source/items/jobs 并按 source UID 聚合", async () => {
    const store = useSourceStore();
    vi.mocked(loadSourcesWorkspace).mockResolvedValue({
      sources: [source("source-1"), source("source-2")],
      sourceRows: [],
    } as never);
    vi.mocked(loadSourceItems).mockResolvedValue([item("item-1")] as never);
    vi.mocked(listActiveSourceJobs).mockResolvedValue([
      { jobUid: "job-1", sourceUid: "source-1", status: "running" },
      { jobUid: "job-2", sourceUid: "source-1", status: "queued" },
    ] as never);

    await store.loadSources();
    await store.loadSourceItems("source-1");
    await store.loadActiveJobs();

    expect(store.sources.map((entry) => entry.uid)).toEqual([
      "source-1",
      "source-2",
    ]);
    expect(store.getSourceItems("source-1")).toMatchObject([{ uid: "item-1" }]);
    expect(store.activeJobsBySourceUid["source-1"]).toHaveLength(2);
    expect(store.isLoading).toBe(false);
  });

  it("上传合并 item，索引/暂停/恢复时收敛状态与 active job", async () => {
    const store = useSourceStore();
    store.sources = [source("source-1") as never];
    store.setSourceItems("source-1", [item("item-1"), item("item-2")] as never);
    vi.mocked(uploadLocalSourceItems).mockResolvedValue([
      { ...item("item-1", "completed"), title: "updated" },
      item("item-3"),
    ] as never);
    vi.mocked(indexSourceItems).mockResolvedValue({
      jobUid: "job-index",
      sourceUid: "source-1",
      status: "queued",
    } as never);
    vi.mocked(pauseSourceItems).mockResolvedValue([
      { sourceItemUid: "item-1", processStatus: "paused" },
    ] as never);
    vi.mocked(resumeSourceItems).mockResolvedValue({
      jobUid: "job-resume",
      sourceUid: "source-1",
      status: "queued",
    } as never);
    vi.mocked(toSourceJobViewModel).mockImplementation((job) => job as never);

    await store.uploadItems("source-1", []);
    await store.indexItems("source-1", ["item-1", "item-2"]);
    expect(store.getSource("source-1")?.status).toBe("processing");
    expect(store.getSourceItems("source-1")).toMatchObject([
      { uid: "item-1", title: "updated", status: "processing" },
      { uid: "item-2", status: "processing" },
      { uid: "item-3", status: "pending" },
    ]);

    await store.pauseItems("source-1", ["item-1"]);
    expect(store.getSourceItems("source-1")[0]?.status).toBe("paused");
    await store.resumeItems("source-1", ["item-1"]);
    expect(store.getSourceItems("source-1")[0]?.status).toBe("processing");
    expect(
      store.activeJobsBySourceUid["source-1"].map((job) => job.jobUid),
    ).toEqual(["job-index", "job-resume"]);
  });

  it("失败时重置 loading，并保留可观察错误状态", async () => {
    const store = useSourceStore();
    vi.mocked(loadSourcesWorkspace).mockRejectedValue(
      new Error("source offline"),
    );

    await expect(store.loadSources()).rejects.toThrow("source offline");
    expect(store).toMatchObject({
      isLoading: false,
      isMutating: false,
      errorMessage: "source offline",
    });
  });

  it("删除 source 时一并移除缓存 items 与 active jobs", async () => {
    const store = useSourceStore();
    store.sources = [source("source-1"), source("source-2")] as never;
    store.setSourceItems("source-1", [item("item-1")] as never);
    store.activeJobsBySourceUid = {
      "source-1": [
        { jobUid: "job-1", sourceUid: "source-1", status: "running" },
      ],
    } as never;
    vi.mocked(deleteSource).mockResolvedValue({
      sourceUid: "source-1",
    } as never);

    await store.deleteSource("source-1");

    expect(store.sources).toMatchObject([{ uid: "source-2" }]);
    expect(store.getSourceItems("source-1")).toEqual([]);
    expect(store.activeJobsBySourceUid["source-1"]).toBeUndefined();
  });
});
