# TadaWidget 前端 UI 产品范围与约束草案

## 1. 文档定位

本文档记录当前已经明确的前端产品范围、Admin Console 页面组织、Widget 形态和样式边界。

本文档是**轻量约束草案**，不是完整 UI 设计规范，也不是最终技术方案。未在本轮讨论中明确的问题，统一保留为待定，不在本文中推测。

## 2. MVP 产品范围

MVP 阶段只包含两个产品面：

- **Admin Console**
- **Visitor Widget**

MVP 阶段暂不包含：

- 独立 Widget 本地预览页。
- 项目内置 Widget 安装说明页。
- 首屏初始化向导。
- 独立 public demo 页面。

相关说明：

- Widget 可由用户注入到本地静态网站中测试。
- Widget 安装说明后续通过项目说明文档提供，不需要由应用本身提供说明页。
- 首屏初始化向导暂时跳过，由项目文档说明初始化流程。

## 3. Admin Console 范围

MVP 需要的主要页面：

- Admin 登录页面。
- Console SPA。

Console 基本布局参考常见管理后台：

- 左侧 menu。
- 右侧 dashboard/content 区域。
- 顶层 header。

页面布局可参考 `frontend/docs/kapa-sources.png` 的信息组织方式，但不复刻 kapa 的具体实现。

## 4. Admin Console 导航草案

左侧 menu 暂定包含以下分组和入口：

```txt
Project
- Overview / Dashboard（选定 project 后的主工作台）
- Chat（project 上下文下的对话）

Analytics（后端暂未实现，先保留框架）
- Conversations
- Top Questions
- Source Analytics

Configuration
- Sources
- API Keys
- Settings
```

Settings 分为：

- Global：管理 Admin 级配置，例如密码。
- Project：管理当前 Project settings。

约束说明：

- 统计相关页面首轮只保留大致框架，不做真实数据实现。
- GitHub repo ingestion 需要在信息架构中预留入口，但首轮不要求完整实现。
- Admin Console 优先服务 Widget 正常运行，而不是一次性完成完整 dashboard。

## 5. 核心资源关系

当前已经明确：

- **Project 是用户主要工作单元**。
- **Widget 绑定 Project**。
- **Source 是全局资源**。
- **Project 与 Source 是多对多关系**。
- **Model Provider 是全局资源**。

Chat scope：

- Project Chat：默认启用当前 Project scope 下的 sources。
- Global Chat：默认不带 sources，需要用户手动选择 sources。

## 6. MVP 后端对接边界

首轮 MVP 应对接后端已经实现的 RAG 能力。

摄取能力：

- Local file：首轮对接。
- Web crawl：首轮先实现前端框架。
- GitHub repo ingestion：预留入口。

后端 API 对齐：

- 完整 API 对接与字段说明以后端文档为准。
- 后端缺失的 API 允许前端先使用 mock 数据。
- 前端可以基于 OpenAPI 自动生成类型。
- 如果引入类型生成所需依赖，应在实现时补充说明。

## 7. Admin 表单配置边界

已明确：

- Web crawl config 表单在 MVP 阶段展示全部字段。
- RAG 高级配置在 MVP 阶段不暴露。
- 大量配置需要采用“基础 / 高级”分层。

待后续明确：

- 哪些 Project settings 属于基础配置。
- 哪些配置进入高级设置。
- 表单校验由前端承担到什么程度。

## 8. Widget 产品形态

MVP Widget 形态：

- 右下角悬浮按钮。
- 点击后弹出对话框。
- 支持多轮对话。
- 需要显示来源引用。

移动端：

- MVP 暂不支持移动端。
- 检测到移动端时，Widget 不显示，以避免破坏宿主页面布局。

## 9. Widget Public API

Widget public API 暂未确定。

待后续明确：

- HTML tag 名称。
- 必需 attributes。
- 可选 attributes。
- 是否支持 JS 初始化 API。
- 是否支持宿主页面事件监听或主动控制。
- 会话恢复策略。

## 10. Widget CSS 自定义边界

MVP 阶段只开放 **CSS tokens** 作为用户自定义样式入口。

暂不开放：

- 通过普通 CSS 覆盖所有内部部件。
- 完整自定义 CSS 注入。
- 稳定的 `::part()` 覆盖能力。

说明：

- Widget CSS 自定义能力是重要方向，但 MVP 阶段优先保证稳定性。
- 内部 class、DOM 结构和布局实现暂不承诺稳定。
- 后续可再讨论是否开放 `::part()`、主题 preset 或更完整的 CSS 覆盖能力。

## 11. Widget 与 Tailwind

Widget 与 Tailwind 的具体关系暂不在本阶段确定。

待后续实现前明确：

- Widget 内部是否使用 Tailwind 加速开发。
- Widget 是否采用独立 CSS 文件组织。
- Widget public style API 是否只通过 CSS tokens 暴露。
- Admin 与 Widget 是否共享视觉 token。

## 12. 暂未确定的问题

以下问题本轮不做推测，留待后续主题讨论：

- Widget public API 细节。
- Widget CSS token 列表。
- Widget 来源引用的具体展示方式。
- Admin 具体视觉风格和组件组合。
- Analytics 页面真实数据模型。
- API mock 的组织方式。
- OpenAPI 类型生成流程。
- vibe coding 的具体协作边界和审查规则。
- 构建产物与部署方式。
