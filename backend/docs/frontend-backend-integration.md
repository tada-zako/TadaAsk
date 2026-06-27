# TadaAsk Backend Notes

这组文档只承担轻量导航作用：帮助前端开发时快速找到 API schema、业务入口和关键源文件。

当前项目仍处于 MVP 快速迭代阶段，后端实现会随前端体验调整而重构。因此本文档不作为严格 SDD 规范，也不承诺冻结具体业务流程；遇到疑问时，以源代码和 `openapi.json` 为准。

## 保留文档

- [tutorial/openapi.json](./tutorial/openapi.json)：FastAPI 生成的接口 schema，适合查看路径、请求体和响应字段。
- [tutorial/source-map.md](./tutorial/source-map.md)：关键业务源文件定位说明，适合开发时快速跳转代码。

开发环境启动后也可以访问：

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- 原生 OpenAPI: `/openapi.json`

## API 入口

- Admin API: `/admin/*`
  用于项目、Widget、模型配置、知识源、索引和管理端对话。需要 Bearer Token。
- Visitor API: `/visitor/*`
  用于嵌入式 Widget 的访客侧流式问答和生成取消。通过 Project、Widget、Origin、限流等规则约束访问。

## 阅读建议

前端开发时优先按这个顺序定位：

1. 用 `openapi.json` 或 `/docs` 确认接口形状。
2. 用 `source-map.md` 找到对应 router / service / schema。
3. 直接阅读源代码确认当前实现细节。

历史规格文档仍可能保留在 [spec/](./spec/) 下，仅作为设计背景参考，不代表全部已经实现。
