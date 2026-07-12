import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@/shared/api/generated/schema";

interface CreateApiClientOptions {
  /** Widget 可在运行时指向不同后端；Console 省略时继续读取 Vite 环境变量。 */
  baseUrl?: string;
  middlewares?: Middleware[];
}

/**
 * 创建 OpenAPI client 实例。
 *
 * shared 层只负责提供基础工厂，不承载 console/widget 业务策略。
 */
export function createApiClient(options: CreateApiClientOptions = {}) {
  const client = createClient<paths>({
    baseUrl: options.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? "",
  });

  // 挂载 middleware
  for (const middleware of options.middlewares ?? []) {
    client.use(middleware);
  }

  return client;
}
