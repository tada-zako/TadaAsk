import { client } from "./client";
import type { components } from "@/shared/api/generated/schema";

export type ProjectCreatePayload = components["schemas"]["ProjectCreate"];
export type ProjectUpdatePayload = components["schemas"]["ProjectUpdate"];
export type ProjectSettingsUpdatePayload =
  components["schemas"]["ProjectSettingsUpdate"];
export type ProjectWidgetCreatePayload =
  components["schemas"]["ProjectWidgetCreate"];
export type ProjectWidgetUpdatePayload =
  components["schemas"]["ProjectWidgetUpdate"];

/** Project 管理接口 */
export const projectApi = {
  /** 获取 Admin Console 中的项目列表 */
  list: (query: { limit?: number; offset?: number } = {}) =>
    client.GET("/admin/project/list", {
      params: { query },
    }),

  /** 创建 project */
  create: (body: ProjectCreatePayload) =>
    client.POST("/admin/project/new", {
      body,
    }),

  /** 获取 project 详情 */
  get: (projectUid: string) =>
    client.GET("/admin/project/{project_uid}", {
      params: { path: { project_uid: projectUid } },
    }),

  /** 更新 project 基础信息 */
  update: (projectUid: string, body: ProjectUpdatePayload) =>
    client.PATCH("/admin/project/{project_uid}", {
      params: { path: { project_uid: projectUid } },
      body,
    }),

  /** 删除 project */
  remove: (projectUid: string) =>
    client.DELETE("/admin/project/{project_uid}", {
      params: { path: { project_uid: projectUid } },
    }),

  /** 获取 project settings */
  getSettings: (projectUid: string) =>
    client.GET("/admin/project/{project_uid}/settings", {
      params: { path: { project_uid: projectUid } },
    }),

  /** 更新 project settings */
  updateSettings: (projectUid: string, body: ProjectSettingsUpdatePayload) =>
    client.PATCH("/admin/project/{project_uid}/settings", {
      params: { path: { project_uid: projectUid } },
      body,
    }),

  /** 获取 project 已绑定 sources */
  listSources: (projectUid: string) =>
    client.GET("/admin/project/{project_uid}/sources", {
      params: { path: { project_uid: projectUid } },
    }),

  /** 绑定已有 sources 到 project */
  bindSources: (projectUid: string, sourceUids: string[]) =>
    client.POST("/admin/project/{project_uid}/sources", {
      params: { path: { project_uid: projectUid } },
      body: { sourceUids },
    }),

  /** 解除 project-source 绑定 */
  unbindSources: (projectUid: string, sourceUids: string[]) =>
    client.DELETE("/admin/project/{project_uid}/sources", {
      params: { path: { project_uid: projectUid } },
      body: { sourceUids },
    }),

  /** 获取 project widgets */
  listWidgets: (projectUid: string) =>
    client.GET("/admin/project/{project_uid}/widgets", {
      params: { path: { project_uid: projectUid } },
    }),

  /** 创建 project widget */
  createWidget: (projectUid: string, body: ProjectWidgetCreatePayload) =>
    client.POST("/admin/project/{project_uid}/widgets", {
      params: { path: { project_uid: projectUid } },
      body,
    }),

  /** 更新 project widget */
  updateWidget: (
    projectUid: string,
    widgetUid: string,
    body: ProjectWidgetUpdatePayload,
  ) =>
    client.PATCH("/admin/project/{project_uid}/widgets/{widget_uid}", {
      params: {
        path: { project_uid: projectUid, widget_uid: widgetUid },
      },
      body,
    }),

  /** 删除 project widget */
  removeWidget: (projectUid: string, widgetUid: string) =>
    client.DELETE("/admin/project/{project_uid}/widgets/{widget_uid}", {
      params: {
        path: { project_uid: projectUid, widget_uid: widgetUid },
      },
    }),
};
