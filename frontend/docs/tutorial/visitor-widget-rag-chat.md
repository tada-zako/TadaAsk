# Visitor Widget RAG Chat 业务边界

本文面向后续实现 Agent，记录 Visitor Widget 静态设计与前端实现必须保持的业务边界。源码和真实 API 与本文冲突时，以源码和 API 为准。

## 1. 产品形态

- Widget 是嵌入宿主网站的大尺寸 AI 对话面板，强调长内容阅读，不是 Admin Console 的缩小版。
- TadaAsk 默认主题为深色；深色不是固定产品定位。部署方可通过受控主题变量配置完整的浅色或深色外观。
- 桌面端打开后约占页面宽度的 70%，保留宿主页面可见区域。
- 移动端宽度占满，高度保留一段未覆盖区域；点击该区域可关闭 Widget。
- 首屏使用简短欢迎语和 composer，不提供示例问题。

## 2. 会话边界

- Widget 同一时间只维护一轮可见会话，不提供 sessions list。
- 用户可以新建会话；新建后清除上一轮前端消息与 `chatSessionUid`。
- 折叠再打开时保留当前会话。
- 页面刷新后无需恢复 visitor history，也不需要为此补充 history API。
- Visitor 请求只提交 `message` 和可选 `chatSessionUid`；模型、thinking、sources 和 RAG 参数均由项目配置决定，不在 visitor UI 中暴露。

## 3. Chat UI

- 顶部只保留 logo、title、新会话和关闭等必要操作。
- 用户消息使用右侧气泡；assistant 消息左对齐并直接渲染 Markdown，不使用大面积回答气泡。
- Composer 固定在消息区底部；生成期间禁用重复发送，发送按钮切换为停止按钮。
- 必须覆盖 `session_ready`、`generation_start`、`rag_ready`、`delta`、`cancelled`、`message_done` 和 `error` 状态。
- 错误信息面向访客归类展示，不直接暴露后端技术详情，也不设置额外开发模式。

## 4. Markdown 与 Citation

- 沿用 `CITATION_MARKER_TEMPLATE`：`[[citation:N]]`。
- `rag_ready` 先于正文 delta 到达；前端从 assistant message 的 `ragSnapshot.items` 校验 citation ID。
- 按 assistant 正文中有效 citation 首次出现的顺序，选择最多 4 个不重复 source 作为该消息的可见引用集合。
- 只有可见引用集合中的 marker 才渲染为可交互 citation token；其余 marker 在展示层移除，不修改原始 message content。
- 流式阶段需隐藏尚未闭合的 citation marker，避免向访客显示协议文本。
- 点击正文 citation token 后，展开该消息下方的 sources，并定位、高亮对应条目。
- Markdown 的安全过滤、代码块、链接、数学公式和流式渲染行为保持内部固定，不允许部署方覆盖。

参考实现：

- `backend/app/providers/prompts.py`
- `frontend/src/console/services/chat-markdown.ts`

## 5. Sources 展示

- Sources 在对应 assistant message 下方内联展开，不使用 Admin Console 式右侧 citation sheet。
- 每条 assistant message 最多展示 4 个 source，不提供继续展开更多来源的功能。
- 不向访客展示 query、standalone query、rerank/RRF score 或 `usedInContext` 等内部诊断字段。
- 文件来源展示标题或文件名、source 名称、section/page 等元信息，并展示简短 excerpt；当前不提供文件下载或预览操作。
- 网页来源展示标题、站点或域名和外链动作，不展示 excerpt；默认在新标签页打开。
- 网页与文件类型当前可依据 `originUrl`、`filename` 等字段判断；若后端以后提供明确 source type，应改用正式字段。

## 6. 部署时外观配置

- MVP 使用 Web Component 标签属性和 CSS custom properties 进行手动配置，不使用后端 `widget_config`。
- 标签属性用于 title、logo URL、位置等离散配置。
- 语义主题变量至少覆盖 background、surface、foreground、muted foreground、border、accent 和 accent foreground，以支持完整浅色或深色主题。
- 不要求支持外部 CSS 文件、原始 CSS 字符串或任意内部选择器覆盖。
- 部署方不能改变 Markdown、消息结构、流式反馈、citation 规则、sources 上限、关键尺寸下限和交互协议。

## 7. 非目标

- Visitor 选择模型、thinking、source 或 RAG 参数。
- 示例问题配置。
- Visitor 历史会话列表与跨刷新历史恢复。
- Metrics、Toolbar、Row action 或表格化 chat 主界面。
- 展示检索评分、调试快照或后端错误细节。
