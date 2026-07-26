import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/api/sources", () => ({
  sourceApi: {
    create: vi.fn(),
    update: vi.fn(),
    listActiveJobs: vi.fn(),
  },
}));

import { sourceApi } from "@/console/api/sources";
import {
  createSource,
  updateSource,
} from "@/console/services/sources/source-actions";
import { listActiveSourceJobs } from "@/console/services/sources/source-jobs";
import {
  getSourceItemsRouteName,
  toSourceItemRow,
  toSourceJobViewModel,
} from "@/console/services/sources/source-mappers";

describe("console source services", () => {
  it("创建与更新 source 时只发送规范化的业务载荷", async () => {
    vi.mocked(sourceApi.create).mockResolvedValue({
      data: { uid: "source-1" },
      error: undefined,
    } as never);
    vi.mocked(sourceApi.update).mockResolvedValue({
      data: { uid: "source-1" },
      error: undefined,
    } as never);

    await createSource({
      sourceName: "  Handbook  ",
      sourceType: "local_file",
      isPublic: true,
      syncInterval: undefined,
      webCrawlConfig: undefined,
    } as never);
    await updateSource("source-1", {
      sourceName: "  ",
      isPublic: false,
      webCrawlConfig: undefined,
      ignored: "must not be sent",
    } as never);

    expect(sourceApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceName: "Handbook",
        status: "pending",
        syncInterval: null,
        webCrawlConfig: null,
      }),
    );
    expect(sourceApi.update).toHaveBeenCalledWith("source-1", {
      sourceName: null,
      isPublic: false,
      webCrawlConfig: null,
    });
  });

  it("映射 SourceItem 权限、进度与可下载条件", () => {
    const processing = toSourceItemRow(
      {
        uid: "item-1",
        title: "guide.pdf",
        filename: "guide.pdf",
        originUrl: null,
        storageKey: "objects/guide.pdf",
        status: "processing",
        createdAt: "2026-07-20T10:00:00Z",
        updatedAt: "2026-07-20T10:00:00Z",
      } as never,
      "local_file",
      0.456,
    );
    const paused = toSourceItemRow(
      {
        uid: "item-2",
        title: "page",
        filename: null,
        originUrl: "https://example.com",
        storageKey: null,
        status: "paused",
        createdAt: "2026-07-20T10:00:00Z",
        updatedAt: "2026-07-20T10:00:00Z",
      } as never,
      "web_crawl",
    );

    expect(processing).toMatchObject({
      progress: 46,
      showProgress: true,
      canPause: true,
      canRename: false,
      canDelete: false,
      canDownload: true,
    });
    expect(paused).toMatchObject({
      canResume: true,
      canDownload: false,
      displayOrigin: "https://example.com",
    });
    expect(getSourceItemsRouteName("github_repo")).toBeNull();
  });

  it("映射任务的缺省字段，并转换活跃任务列表", async () => {
    const started = {
      jobUid: "job-1",
      jobType: "index_documents",
      sourceUid: "source-1",
      status: "queued",
    };
    vi.mocked(sourceApi.listActiveJobs).mockResolvedValue({
      data: { jobs: [started] },
      error: undefined,
    } as never);

    expect(toSourceJobViewModel(started as never)).toMatchObject({
      sourceItemUids: [],
      error: null,
      createdLabel: "",
    });
    await expect(listActiveSourceJobs()).resolves.toMatchObject([
      { jobUid: "job-1", status: "queued", statusTone: "warning" },
    ]);
  });
});
