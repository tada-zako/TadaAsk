import { client } from "./client";

/** Project 管理接口 */
export const projectApi = {
  /** 获取 Admin Console 中的项目列表 */
  list: (query: { limit?: number; offset?: number } = {}) =>
    client.GET("/admin/project/list", {
      params: { query },
    }),
};
