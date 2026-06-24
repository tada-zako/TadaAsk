# TadaWidget 前端技术栈说明

## 1. 前端范围

前端需要同时服务两个产品面：

- **Visitor Widget**：通过一个 HTML 标签嵌入外部站点，是访客实际使用的产品入口。
- **Admin Console**：自托管管理后台，供站主管理项目、知识源、模型配置、摄取流程、对话记录和后续 RAG 工具。

Widget 必须对宿主页面保持框架无关；Admin Console 可以沿用当前 Vue 技术栈。

## 2. 推荐技术栈

| 领域 | 选择 | 说明 |
|------|------|------|
| 语言 | TypeScript | 前后端契约需要明确；后端 Pydantic schema 已经通过 alias 输出 camelCase，前端统一使用 camelCase。 |
| 构建工具 | Vite | 当前已配置；同时支持 SPA 与 library/custom-element 构建。 |
| Admin 框架 | Vue 3 SFC | 已在项目依赖中，适合后台表单、表格、路由和状态管理。 |
| Widget 运行时 | Vue Custom Element (`defineCustomElement`) | 生成真正的 Web Component，并通过 Shadow DOM 隔离样式；MVP 阶段可复用 Vue/TS 能力。 |
| 路由 | Vue Router | 仅用于 Admin Console；Widget 不依赖路由。 |
| 状态管理 | Pinia + composables | Pinia 保存跨页面状态，如 auth、当前项目、活跃 stream；页面局部数据用 composables/API 调用维护。 |
| HTTP JSON/FormData | axios | 已安装，适合 Admin 侧鉴权 CRUD 和文件上传。 |
| POST SSE 流式响应 | `fetch` + stream parser | 当前后端以 POST 返回 `text/event-stream`；浏览器原生 `EventSource` 只支持 GET，因此聊天和 ingestion 需要 `fetch` 读取 `ReadableStream`。推荐增加轻量依赖 `eventsource-parser`。 |
| API 契约 | OpenAPI 生成类型 + 手写轻量 client | 后端运行后从 FastAPI OpenAPI 生成 TS 类型；请求封装保持手写，便于理解和调试。 |
| 样式 | Tailwind CSS v4 + CSS variables | 当前已配置；主题色、Widget token 等统一走 CSS 变量。 |
| Admin UI 基础组件 | shadcn-vue / Reka UI + lucide-vue-next | `components.json` 已存在；适合表单、弹窗、tabs、菜单、表格、tooltip 和图标按钮。 |
| Widget 样式 | Shadow DOM 内部 CSS + CSS variables | 不依赖宿主页面 Tailwind 或 reset，避免污染外部站点。 |
| 图标 | lucide-vue-next | 当前已安装，与 shadcn-vue 风格一致。 |

## 3. 关键技术决策

### 3.1 Admin 使用 Vue SPA，Widget 使用 Web Components

Admin Console 是标准后台应用，需要路由、表单、表格、鉴权请求和跨页面状态，因此使用 Vue SPA。

Widget 对外交付为 custom element：

```ts
import { defineCustomElement } from 'vue'
import TadaWidgetElement from './TadaWidget.ce.vue'

customElements.define('tada-widget', defineCustomElement(TadaWidgetElement))
```

预期嵌入方式：

```html
<script src="https://example.com/widget/tada-widget.iife.js"></script>
<tada-widget
  project-uid="project_xxx"
  api-base-url="https://api.example.com"
  language="zh-CN"
></tada-widget>
```

这能保证宿主站点不需要理解 Vue/React 等框架。后续如果 Widget bundle 体积成为核心问题，可以保持 `<tada-widget>` 对外 API 不变，内部再迁移到原生 Web Components 或 Lit。

### 3.2 流式客户端必须支持 POST SSE

后端聊天与摄取接口都是 `POST` 请求，并返回 `text/event-stream`：

- Visitor chat: `POST /visitor/project/{project_uid}/chat/stream`
- Admin chat: `POST /admin/project/{project_uid}/chat/stream`
- Document indexing: `POST /admin/source/{source_uid}/document/indexing`
- Web crawl sync: `POST /admin/source/{source_uid}/crawl/sync`
- Resume indexing: `POST /admin/source/{source_uid}/document/resume`

因此不要用原生 `EventSource` 处理这些接口。前端应提供一个共享流式工具：

```ts
async function postSse<TEvent>(url: string, body: unknown, options?: RequestInit) {
  // fetch(url, { method: 'POST', body: JSON.stringify(body), ... })
  // 从 response.body 解析 event/data frame
  // yield { event, data } as typed event
}
```

当前 Chat SSE 事件名包括：

- `session_ready`
- `generation_start`
- `delta`
- `cancelled`
- `message_done`
- `error`

当前 Ingestion/Sync SSE 事件名包括：

- `sync_start`
- `sync_progress`
- `sync_complete`
- `sync_paused`
- `sync_failed`
- `item_discovered`
- `item_fetched`
- `item_upserted`
- `item_progress`
- `item_skipped`
- `item_indexing`
- `item_completed`
- `item_paused`
- `item_failed`

后端把 SSE event name 放在事件字段里，JSON `data` 中不再包含 `event`。前端 parser 应把二者合并成可判别联合类型，例如 `{ event, ...JSON.parse(data) }`。

### 3.3 API Client 保持薄封装

前端不要复制后端 service 逻辑。API client 只负责：

- URL 组装
- 鉴权 header 注入
- request/response shape 适配
- stream 解析
- 统一错误格式

RAG mode 降级、source 可见性、ingestion 生命周期、模型/provider 校验等业务规则仍归后端负责。

### 3.4 类型契约生成，但隔离使用

推荐生成文件：

```txt
frontend/src/shared/api/schema.generated.ts
```

只有 API client 层直接依赖生成类型。Vue 页面和组件消费 feature-level types 或 view models，避免后端 schema 变动扩散到每个组件。

## 4. Admin UX 方向

Admin Console 是工作台，不是营销页。登录后的默认体验应直接可操作：

- 左侧导航：Projects、Sources、Chat、Models、Settings
- 项目、数据源、数据项、会话使用紧凑表格
- 编辑动作使用侧边面板、弹窗或详情页
- ingestion/sync 使用持续进度区
- 视觉风格克制、密度适中，优先可扫读性

避免 hero、装饰性大卡片和落地页式布局。站主需要快速查看状态并执行管理动作。

## 5. Widget UX 方向

Widget 是项目的核心产品入口，应优先实现。

核心交互：

- 折叠态 launcher button
- Chat panel 与消息历史
- assistant 流式回复
- retry/error 状态
- 通过 localStorage 保持会话连续性
- 当 `ragSnapshot` 存在时，展示轻量来源/引用信息

嵌入要求：

- Shadow DOM 样式隔离
- 不使用全局 CSS reset
- 不依赖宿主页面字体、Tailwind 或 CSS 变量
- 通过 attributes 或后端项目设置配置主题
- 移动端与桌面端均可用

## 6. MVP 功能开发方向

### Phase 0：前端基础设施

- 替换 Vite starter，建立 Admin entry 与 Widget custom-element entry。
- 增加 shared API client、auth token 处理、POST SSE stream parser。
- 建立 OpenAPI 生成类型或手写契约文件。
- 增加基础 layout、路由守卫、loading/error 状态组件。

### Phase 1：Visitor Widget

- 渲染 `<tada-widget>` 为 launcher + chat panel。
- 支持 `projectUid`、`apiBaseUrl`、`language`、theme attributes。
- 调用 visitor stream endpoint 并渲染流式 delta。
- 按 project 持久化 `chatSessionUid`。
- 完成消息最终态、错误恢复和重试入口。

### Phase 2：Admin Core

- 登录：`/admin/auth/login`。
- 项目列表、创建、编辑、settings。
- Provider 与 model profile 管理。
- Project visitor settings：默认模型、RAG mode、topK、rerank、prompt、timeout、temperature/topP。

### Phase 3：Source 与 Ingestion 管理

- Source list/create，支持 `local_file` 与 `web_crawl`。
- 文件上传：`FormData` 到 `/admin/source/{source_uid}/items/upload`。
- 触发 document indexing 并展示 SSE 进度。
- 暂停/恢复 indexing。
- 触发 web crawl sync 并展示 SSE 进度。

### Phase 4：Admin Chat 与对话检查

- Admin RAG chat，支持选择 source。
- Chat session list 与 message history。
- 当消息包含 RAG snapshot/citation metadata 时展示检索来源。
- 将该页面作为第一版回答质量调试面板。

### Phase 5：后续管理工具

这些功能重要，但需要后端 API 先补齐：

- 按 source 列出 source items
- 浏览 document chunks
- 删除或禁用噪声 chunks
- 通过公开 API bind/unbind project sources
- 使用统计、query/document 命中频率图表
- 持久化 Widget theme editor

## 7. 前端规划中的后端 API 缺口

后端已有部分内部 CRUD，但尚未暴露成 Admin endpoint。实现对应 UI 前，需要新增或确认：

- `ProjectSourceLink` 管理：bind/unbind/list project sources。
- Source item list：按 source 列出上传或爬取的数据项。
- Chunk 清洗：按 item/source 列出 chunk，删除或禁用 chunk。
- Source 删除与更新：当前公开接口主要是 create/list 和处理动作。
- 使用统计：query 数、document hit 数、模型/token 成本汇总。
- Widget 自定义持久化：主题色、语言、launcher 文案、placeholder 文案。

在这些接口存在前，相关前端页面只适合做导航占位或设计原型，不应作为可用 MVP 功能承诺。
