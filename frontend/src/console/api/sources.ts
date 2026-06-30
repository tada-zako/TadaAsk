import { client } from "./client";

/** Admin Console 数据源接口 */
export const sourceApi = {
  /** 获取全局 sources 列表 */
  list: (query: { limit?: number; offset?: number } = {}) =>
    client.GET("/admin/source/list", {
      params: { query },
    }),
};
