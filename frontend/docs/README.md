# TadaWidget 前端文档入口

## 1. 文档定位

本文档是前端开发的文档入口，用于说明在不同开发场景下应优先阅读哪些说明文档。

重要原则：

- 本项目不是 SDD（Specification-Driven Development）项目。
- 文档用于帮助理解设计意图、历史决策和协作边界，不是不可变的强约束。
- 当文档与实际源代码、后端接口或运行行为冲突时，以实际源代码和真实接口为准。
- 如果实现过程中发现文档过时，应优先修正文档，而不是为了符合文档去扭曲代码。

## 2. 通用阅读顺序

首次参与前端开发时，建议按以下顺序阅读：

1. `../../docs/requirements.md`：理解项目定位、用户角色、Widget-first 方向和 MVP 功能背景。
2. `./tutorial/frontend-ui-scope-constraints.md`：理解当前已确认的前端产品范围、Admin Console 页面组织和 Widget UI 边界。
3. `./tutorial/frontend-ai-collaboration.md`：理解 MVP 阶段 AI / vibe coding 的参与边界和最低验收要求。
4. `../../backend/docs/tutorial/sse-contract.md`：实现聊天、ingestion、web crawl 等流式交互前阅读。
5. `../../backend/docs/tutorial/source-source-item-flow.md`：实现 Source、SourceItem、文件上传、索引流程相关 UI 前阅读。

## 3. 按开发任务阅读

### 3.1 调整前端产品范围或导航

优先阅读：

- `./tutorial/frontend-ui-scope-constraints.md`
- `../../docs/requirements.md`

适用场景：

- 调整 Admin Console 左侧导航。
- 调整 Project / Source / Model Provider 的页面关系。
- 判断某个页面是否属于 MVP。
- 判断统计、GitHub ingestion、数据清洗器等功能是否应该进入首轮实现。

### 3.2 开发 Admin Console 页面

优先阅读：

- `./tutorial/frontend-ui-scope-constraints.md`
- `./tutorial/frontend-ai-collaboration.md`

适用场景：

- 登录页、Console layout、左侧 menu、header、dashboard/content 区域。
- Project、Sources、API Keys、Settings 页面。
- Analytics 占位页面。
- 使用 AI / vibe coding 生成页面布局或组件组合。

### 3.3 开发 Visitor Widget

优先阅读：

- `./tutorial/frontend-ui-scope-constraints.md`
- `./tutorial/frontend-ai-collaboration.md`
- `../../docs/requirements.md`

适用场景：

- 右下角悬浮按钮。
- 弹出式对话框。
- 多轮对话 UI。
- 来源引用展示。
- 移动端隐藏策略。
- Widget CSS tokens 自定义边界。

注意：

- Widget public API 尚未最终确定。
- Widget CSS token 列表尚未最终确定。
- MVP 阶段仅确认“只开放 CSS tokens 作为样式自定义入口”这一方向。

### 3.4 开发请求层、SSE 或流式 UI

优先阅读：

- `../../backend/docs/tutorial/sse-contract.md`
- `../../backend/docs/tutorial/source-source-item-flow.md`

适用场景：

- POST SSE parser。
- Chat stream。
- Document indexing progress。
- Web crawl sync progress。
- SourceItem 状态流转。
- 上传后触发索引的 UI 编排。

说明：

- 前端不额外维护独立的 SSE 协议说明文档。
- 流式协议和 Source/SourceItem 业务流程以后端 tutorial 文档为主要参考。

### 3.5 对接后端 API 或生成类型

优先阅读：

- `../../backend/docs/tutorial/openapi.json`
- `../../backend/docs/tutorial/sse-contract.md`
- `../../backend/docs/tutorial/source-source-item-flow.md`

适用场景：

- 基于 OpenAPI 生成前端类型。
- 对接已有后端 endpoint。
- 判断某个 UI 是否需要 mock 数据。
- 排查前后端字段或事件格式不一致。

说明：

- OpenAPI 文件和后端源代码比前端文档更接近真实接口。
- 如果 OpenAPI、后端文档和后端源代码不一致，应以后端源代码和实际响应为准。

### 3.6 使用 AI / vibe coding 生成前端代码

优先阅读：

- `./tutorial/frontend-ai-collaboration.md`
- `./tutorial/frontend-ui-scope-constraints.md`

适用场景：

- 生成 Admin 页面 UI。
- 生成 Widget UI。
- 修改前端组件、样式、状态或 API 模块。
- 判断 AI 生成代码是否能进入主线。

最低要求：

- 能通过基本冒烟测试。
- 遵守项目 TypeScript 标准开发规范。
- 对核心工程改动说明设计意图和影响范围。

## 4. 当前前端文档列表

当前前端侧保留的主要文档：

- `README.md`：本文档，前端文档入口。
- `./tutorial/frontend-ui-scope-constraints.md`：前端 UI 产品范围与约束草案。
- `./tutorial/frontend-ai-collaboration.md`：前端 AI / vibe coding 协作说明。
- `kapa-sources.png`：Admin Console 信息组织参考图，不作为复刻目标。

后端侧与前端开发强相关的文档：

- `../../backend/docs/tutorial/sse-contract.md`
- `../../backend/docs/tutorial/source-source-item-flow.md`
- `../../backend/docs/tutorial/openapi.json`

## 5. 文档维护原则

后续新增或更新文档时，建议遵循：

- 只把已经明确的决策写成约束。
- 对暂未确定的问题明确标注“待定”。
- 避免把临时实现写成长期规范。
- 避免为了文档完整性提前设计过细。
- 对 Widget public API、CSS tokens、构建产物等外部可见边界保持更谨慎。

如果某个任务需要新的文档，应优先判断它属于：

- 产品范围约束。
- UI / 样式边界。
- API / 流式协议。
- AI 协作规范。
- 构建与发布说明。

不要把所有内容集中到单一大文档中。
