# TadaWidget 前端架构与代码组织

## 1. 架构目标

前端架构需要让两个产品面独立演进：

- **Admin Console**：完整 Vue SPA，面向站主工作流。
- **Visitor Widget**：嵌入外部站点的 custom element。

二者可以共享 API 契约、小工具函数和流式客户端。默认不共享视觉组件，因为 Widget 对 bundle 体积、样式隔离和宿主兼容性要求更严格。

## 2. 运行时拆分

```txt
frontend/
  src/
    admin/      Vue SPA entry、router、layouts、pages
    widget/     Web Component entry 与隔离的 widget UI
    shared/     API clients、contracts、utilities、transport、common types
```

推荐构建产物：

```txt
dist/
  admin/                 Admin Console 静态资源
  widget/
    tada-widget.iife.js  script-tag 使用的构建
    tada-widget.es.js    可选 ESM 构建
```

MVP 阶段 Admin Console 和 Widget 可以留在同一个 `frontend` package 中。后续如果 Widget 需要更强的体积优化，再拆成 workspace package，但保持公开 `<tada-widget>` API 不变。

## 3. 推荐目录结构

```txt
frontend/src/
  admin/
    main.ts
    router.ts
    routes.ts
    App.vue
    layouts/
      AdminLayout.vue
      AuthLayout.vue
    pages/
      LoginPage.vue
      ProjectListPage.vue
      ProjectDetailPage.vue
      ProjectSettingsPage.vue
      SourceListPage.vue
      SourceDetailPage.vue
      ModelProfilesPage.vue
      AdminChatPage.vue
      ChatSessionsPage.vue
    stores/
      auth.store.ts
      project.store.ts
      stream.store.ts

  widget/
    entry.ts
    TadaWidget.ce.vue
    components/
      WidgetLauncher.vue
      WidgetPanel.vue
      MessageList.vue
      MessageComposer.vue
      CitationList.vue
    composables/
      useWidgetConfig.ts
      useWidgetChat.ts
      useWidgetSession.ts
    styles/
      widget.css

  features/
    auth/
      api.ts
      types.ts
    projects/
      api.ts
      types.ts
      components/
    project-settings/
      api.ts
      types.ts
      components/
    sources/
      api.ts
      types.ts
      components/
    ingestion/
      api.ts
      types.ts
      components/
    model-profiles/
      api.ts
      types.ts
      components/
    chat/
      api.ts
      stream.ts
      types.ts
      components/
    sessions/
      api.ts
      types.ts
      components/

  shared/
    api/
      http.ts
      stream.ts
      endpoints.ts
      errors.ts
      schema.generated.ts
    config/
      env.ts
    lib/
      date.ts
      format.ts
      storage.ts
    ui/
      button/
      dialog/
      dropdown-menu/
      input/
      tabs/
      table/
    styles/
      tokens.css
      admin.css
```

说明：

- `features/*/api.ts` 封装某个业务概念对应的后端 endpoint。
- `features/*/components` 默认是 Admin Console 组件，除非明确标为 headless。
- `shared/ui` 放 shadcn-vue/Reka 风格的后台基础组件。
- Widget 组件固定放在 `widget/components`，避免误引入 admin-only UI 和 CSS。
- `schema.generated.ts` 是生成文件，不手动编辑。

## 4. 依赖方向

保持单向依赖：

```txt
admin/pages -> features -> shared
admin/layouts -> shared
widget -> shared
shared -> 不导入 admin/widget
```

规则：

- `shared` 不导入 `admin`、`widget` 或 `features`。
- `features` 可导入 `shared`，但不导入 pages 或 layouts。
- `admin` 组合 features 和 shared UI。
- `widget` 可导入 `shared/api`、`shared/lib` 和共享类型，但尽量不导入 `shared/ui`。
- API 模块不导入 Vue 组件。

## 5. API Client 组织

### 5.1 Shared HTTP Client

```ts
// shared/api/http.ts
export const adminHttp = createHttpClient({
  baseURL: env.apiBaseUrl,
  getToken: () => authTokenStorage.get(),
})

export function createWidgetHttp(apiBaseUrl: string) {
  return createHttpClient({ baseURL: apiBaseUrl })
}
```

Admin 请求在登录后使用 bearer token。Widget visitor 请求不依赖 admin token。

### 5.2 Feature API Modules

```ts
// features/projects/api.ts
export async function listProjects(params: PageParams): Promise<Project[]> {
  return adminHttp.get('/admin/project/list', { params })
}

export async function updateProjectSettings(
  projectUid: string,
  payload: ProjectSettingsUpdate,
): Promise<ProjectSettings> {
  return adminHttp.patch(`/admin/project/${projectUid}/settings`, payload)
}
```

以真实后端 route 为 source of truth。除非展示层确实需要 view model，否则不要创造前端专用 request shape。

### 5.3 Stream Client

共享 stream helper 可以暴露 async iterator 或 callback API：

```ts
for await (const event of postSse<ChatStreamEvent>(url, payload, { headers })) {
  chatStreamMachine.apply(event)
}
```

当前后端 SSE 约定：

- `event` 是 SSE event name。
- `data` 是 JSON，且不包含 event name。
- parser 返回 `{ event, ...JSON.parse(data) }`。

## 6. 状态模型

### 6.1 Admin State

Pinia 只保存需要跨路由存在的状态：

- auth token 与当前登录状态
- 当前选中的 project UID
- 当前活跃的 chat/indexing stream 状态
- 轻量 lookup cache，例如 enabled providers/models

页面局部表格筛选、modal 状态、form 草稿等留在页面组件或 feature composable 中。

### 6.2 Widget State

Widget 状态自包含：

- panel open/closed
- 当前输入框内容
- message list
- assistant generation 状态
- 按 `projectUid` 持久化的 `chatSessionUid`

建议 localStorage key：

```txt
tada-widget:{projectUid}:chat-session
```

即使同一个宿主页面出现多个 Widget 实例，也应该正常工作。每个实例通过 DOM attributes 获得自己的配置。

## 7. Admin 路由骨架

```txt
/login
/projects
/projects/:projectUid
/projects/:projectUid/settings
/sources
/sources/:sourceUid
/models
/projects/:projectUid/chat
/projects/:projectUid/sessions
```

路由守卫：

- 未登录用户只能访问 `/login`
- 已登录用户访问 `/login` 时跳转到默认工作台
- project-scoped route 通过 project API 或 selected project store 校验 `projectUid`

## 8. Feature 边界

### 8.1 Auth

后端 endpoint：

- `POST /admin/auth/login`

前端职责：

- 以 `application/x-www-form-urlencoded` 提交用户名和密码
- 保存返回的 bearer token
- Admin 请求携带 `Authorization: Bearer <token>`
- 401 时清空 token 并返回登录态

### 8.2 Projects

后端 endpoints：

- `POST /admin/project/new`
- `GET /admin/project/list`
- `GET /admin/project/{project_uid}`
- `PATCH /admin/project/{project_uid}`
- `DELETE /admin/project/{project_uid}`

前端职责：

- 项目列表、创建、编辑
- 项目详情壳层
- 项目创建后展示 Widget 部署片段

部署片段示例：

```html
<script src="https://your-domain/widget/tada-widget.iife.js"></script>
<tada-widget project-uid="..." api-base-url="https://your-api"></tada-widget>
```

### 8.3 Project Settings

后端 endpoints：

- `POST /admin/project/{project_uid}/settings`
- `GET /admin/project/{project_uid}/settings`
- `PATCH /admin/project/{project_uid}/settings`
- `DELETE /admin/project/{project_uid}/settings`

前端职责：

- visitor 默认模型选择
- visitor RAG enabled 开关
- system prompt 编辑
- 模型生成参数
- RAG mode 与 retrieval 参数

### 8.4 Model Profiles

后端 endpoints：

- `POST /admin/model-profile/provider/new`
- `GET /admin/model-profile/provider/list`
- `GET /admin/model-profile/provider/list/models`
- `PATCH /admin/model-profile/provider/{provider_uid}`
- `POST /admin/model-profile/provider/{provider_uid}/models/new`
- `GET /admin/model-profile/provider/{provider_uid}/models/{model_uid}`
- `PATCH /admin/model-profile/provider/{provider_uid}/models/{model_uid}`

前端职责：

- provider list
- API key 更新流程
- model profile 创建与编辑
- model enabled/disabled 状态

后端 delete endpoints 目前注释为暂时不要使用，因此第一版 UI 不暴露 destructive delete 动作。

### 8.5 Sources And Ingestion

后端 endpoints：

- `POST /admin/source/new`
- `GET /admin/source/list`
- `POST /admin/source/{source_uid}/items/upload`
- `POST /admin/source/{source_uid}/document/indexing`
- `POST /admin/source/{source_uid}/document/pause`
- `POST /admin/source/{source_uid}/document/resume`
- `POST /admin/source/{source_uid}/crawl/sync`

前端职责：

- 创建 local file source
- 创建 web crawl source 与配置表单
- 上传一个或多个文件
- 对选中的已上传 items 触发 indexing
- 根据 SSE 渲染 ingest/sync 进度
- 暂停/恢复处理

在后端暴露 source item list 前，不实现完整 source item table。上传接口返回的数据可用于展示当前会话刚上传的 items。

### 8.6 Chat

后端 endpoints：

- `POST /visitor/project/{project_uid}/chat/stream`
- `POST /admin/project/{project_uid}/chat/stream`

前端职责：

- 渲染 stream lifecycle
- `generation_start` 后追加 user message 与 assistant placeholder
- `delta` 时增量更新 assistant message
- `message_done` 时用后端持久化 message 替换 placeholder
- 出现 stream error 时保留输入和已有消息
- completed message 中有 `ragSnapshot` 时展示检索来源

### 8.7 Sessions

后端 endpoints：

- `GET /admin/project/{project_uid}/sessions`
- `GET /admin/session/{chat_session_uid}/messages`
- `DELETE /admin/session/{chat_session_uid}`

前端职责：

- 列出某个 project 下的 admin sessions
- 查看 message history
- 必要时删除 admin session

Visitor session 由 Widget 和后端 chat flow 内部管理。

## 9. Stream 状态机

Chat stream 建议用小型状态机统一处理，避免事件处理散落在组件里：

```ts
type StreamStatus = 'idle' | 'starting' | 'streaming' | 'done' | 'error' | 'cancelled'

function applyChatEvent(event: ChatStreamEvent) {
  switch (event.event) {
    case 'session_ready':
      // store session uid
      break
    case 'generation_start':
      // append user and assistant placeholder messages
      break
    case 'delta':
      // append text to assistant message
      break
    case 'message_done':
      // replace placeholder with persisted backend message
      break
    case 'error':
      // set recoverable error state
      break
  }
}
```

Ingestion stream 使用同样思路：

```ts
type IngestStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed'

function applyIngestEvent(event: RAGSyncEvent) {
  // update source status, item status, counters, and progress bars
}
```

组件只负责渲染状态；composables 或 stores 负责事件归约。

## 10. UI 组件策略

Admin Console：

- 使用 shadcn-vue/Reka primitives：dialog、dropdown、tabs、table、input、select、switch、tooltip。
- 使用 lucide icons 做图标按钮和常见 action。
- 页面信息密度适中，优先清晰的分区标题和紧凑控件。
- 优先使用全宽页面区域和表格，不把页面 section 做成装饰性卡片。

Widget：

- 组件集合保持小而隔离。
- 使用 Shadow DOM CSS variables 做主题：

```css
:host {
  --tada-color-primary: #2563eb;
  --tada-color-surface: #ffffff;
  --tada-color-text: #111827;
}
```

- 先暴露稳定 attributes，再把后端项目设置映射到相同的内部 config model。

## 11. 开发顺序

1. 将 `frontend/src` 重组为 `admin`、`widget`、`features`、`shared`。
2. 实现 shared `http.ts`、`stream.ts`、auth storage 和基础 API modules。
3. 实现 Admin login 与 protected layout。
4. 实现 project/model/settings 页面，因为 Widget chat 依赖项目默认配置。
5. 实现 Widget custom element 与 visitor chat streaming。
6. 实现 source creation、upload、indexing progress UI。
7. 实现 admin chat 与 session review。
8. 后端 API 补齐后再加 chunk cleaner、project-source binding UI、statistics、widget theme persistence。

## 12. 需要确认的产品问题

以下问题会影响 UI 行为，进入细化实现前需要确认：

- 一个 Source 在 Admin UI 中是否允许跨多个 Project 复用，还是默认在某个 Project 内创建？
- Widget visitor session 是长期保存在 localStorage，还是需要配置过期时间？
- 第一版 MVP Widget 是否直接向访客展示 citations，还是放进可展开的来源/debug 面板？

这些问题不阻塞技术骨架，但会影响最终产品流和信息架构。
