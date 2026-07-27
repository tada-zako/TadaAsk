import { describe, expect, it, vi } from "vitest";

vi.mock("@/console/router", () => ({
  default: { push: vi.fn() },
}));
vi.mock("@/console/services/project-workspace", () => ({
  createProject: vi.fn(),
  listProjectOptions: vi.fn(),
}));

import router from "@/console/router";
import {
  createProject,
  listProjectOptions,
} from "@/console/services/project-workspace";
import { useProjectStore } from "@/console/stores/project";

describe("project store", () => {
  it("加载项目、保留有效选择并清除已删除选择", async () => {
    const store = useProjectStore();
    vi.mocked(listProjectOptions).mockResolvedValue([
      { uid: "project-1", name: "First", description: null },
      { uid: "project-2", name: "Second", description: "desc" },
    ]);

    await store.loadProjects();
    await expect(store.selectProject("project-2")).resolves.toBe(true);
    expect(store.selectedProject).toMatchObject({ uid: "project-2" });

    vi.mocked(listProjectOptions).mockResolvedValue([
      { uid: "project-1", name: "First", description: null },
    ]);
    await store.refreshProjects();
    expect(store.selectedProjectUid).toBeNull();
    expect(store.selectedProject).toBeNull();
  });

  it("选择不存在项目时报告状态，并在创建后选择和导航", async () => {
    const store = useProjectStore();
    vi.mocked(listProjectOptions).mockResolvedValue([
      { uid: "project-3", name: "New Project", description: null },
    ]);
    await expect(store.selectProject("missing")).resolves.toBe(false);
    expect(store.selectedProjectUid).toBeNull();
    expect(store.errorMessage).toBeTruthy();

    vi.mocked(createProject).mockResolvedValue({
      uid: "project-3",
      name: "New Project",
      description: null,
    } as never);
    await expect(
      store.createProject({ name: " New Project ", description: null }),
    ).resolves.toEqual({
      uid: "project-3",
      name: "New Project",
      description: null,
    });

    expect(store.selectedProjectUid).toBe("project-3");
    expect(router.push).toHaveBeenCalledWith({
      name: "project-overview",
      params: { projectUid: "project-3" },
    });
  });
});
