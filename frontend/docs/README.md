# TadaAsk 前端文档入口

这组文档用于帮助继续维护前端实现，不是冻结的产品规格。当文档与运行行为、后端接口或源代码不一致时，以当前实现和 OpenAPI 为准。

## 当前文档

- [tutorial/frontend-ts-code-style.md](./tutorial/frontend-ts-code-style.md)：TypeScript 代码风格与注释约定。
- [console-ui-code-guidelines.md](./console-ui-code-guidelines.md)：管理控制台的 UI 组件、样式与布局倾向。
- [../../docs/visitor-widget-customization.md](../../docs/visitor-widget-customization.md)：Visitor Widget 的公开定制属性与 CSS variables（英文）。
- [../../docs/visitor-widget-customization.zh.md](../../docs/visitor-widget-customization.zh.md)：Visitor Widget 的公开定制属性与 CSS variables（中文）。
- [tutorial/visitor-widget-rag-chat.md](./tutorial/visitor-widget-rag-chat.md)：Visitor Widget 问答流程的实现边界。
- [../../backend/docs/tutorial/sse-contract.md](../../backend/docs/tutorial/sse-contract.md)：流式事件协议。
- [../../backend/docs/tutorial/source-source-item-flow.md](../../backend/docs/tutorial/source-source-item-flow.md)：知识源与索引流程。

## 前端测试

维护中的核心回归测试位于 [`frontend/tests`](../tests)。默认测试不连接真实后端或外部 Provider。

从 `frontend/` 运行：

```powershell
pnpm test:run
pnpm test:coverage
```

当前测试重点是 Shared 协议与安全渲染、Console service/store、Widget service/composable，以及少量 Router、Pinia 和组件集成路径。测试不是完整业务规格，也不要求冻结尚未稳定的页面结构、视觉样式或所有 API 包装函数。

## 开发建议

1. 先从后端的 OpenAPI 或运行中的 `/docs` 确认接口形状。
2. 再阅读相关的后端流程说明和当前源代码。
3. 前端页面保持 API → service → store / view 的既有边界；不确定的业务规则不要仅根据历史文档补全。

早期设计和实现记录保存在 [docs/archive/](../../docs/archive/README.md)，不作为当前开发依据。
