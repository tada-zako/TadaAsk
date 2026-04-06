# OpenKapa (暂命名)

定位：轻量级、可定制的开源 AI 知识库助手。

核心价值：通过一行代码将具备 RAG 能力的 Agent 集成至个人静态站点或文档，支持自动化数据同步，且开发者拥有对底层架构的完全控制权。

## 主要功能

### LLM & 核心逻辑 (The "Provider" Layer)
优化建议：抽象 BaseProvider Protocol 提供对不同 LLM 的支持，避免过早绑定特定模型。

模型支持：
    - Gemini
    - OpenAI
    - DeepSeek（国内用户友好）
    - Ollama（支持本地化私有部署）

### RAG 与向量库 (The "Memory" Layer)

#### 向量库集成：

已有：ChromaDB，接口简单，适合快速验证概念。

首选：Qdrant。它有非常出色的 Docker 支持，且自带 UI 界面方便调试，性能比 Chroma 更好。

备选：LanceDB。它是 Serverless 架构，数据直接存为文件（类似 SQLite），极其适合“个人部署”这种不需要维护数据库服务的场景。

#### 数据同步优化：

Sitemap 监听：通过解析 sitemap.xml，比对上次爬取的时间戳，只增量更新变动页面。（尚不清楚，回头研究）

GitHub 逻辑：调用 GitHub API 获取 Repo Tree，直接读取原始 Markdown 代码，实现添加 github repo 作为数据源的功能。

### 存储方案 (The "Persistence" Layer)

元数据/配置：统一使用 SQLite。

大文件/索引文件：支持 Local File System 即可。S3 作为可选的 StorageProtocol 实现，初期不用强求。

### 部署与控制台 (The "Interface" Layer)

#### 网站插件 (Widget)：这是项目的灵魂。

技术选型：建议用 `Web Components` 开发，这样它不依赖任何框架（Vue/React 都能用），且 CSS 样式完全隔离，不会污染用户的博客样式。

#### 控制台 (Admin)：

重点功能：
    - RAG 数据清洗器。用户需要能看到爬下来了哪些 Chunk，并能手动删除垃圾数据（比如“关于我们”、“备案号”等信息）。'
    - 用户对话检查，可以看到用户都问了什么，Agent 是怎么回答的，方便调试和优化。
    - 用户使用统计分析，了解哪些文档被问得最多，哪些功能最受欢迎。
    - 设置模型参数，主要实现默认提示词的配置，后续可以考虑加入温度、top-k 等参数的调整。
    - 调整 Widget 样式，比如颜色、字体、中英文等，满足个性化需求。

### Agent 能力 (The "Intelligence" Layer)

集成的关键点：Agent 不仅仅是 RAG。

用户侧 (Visitor)：主要能力是 "Intent Router" (意图路由)。

如果用户问技术文档，走 RAG。

如果用户问“如何联系作者”，走固定 Action。

管理者侧 (Owner)：可以集成 MCP (Model Context Protocol)。比如通过对话直接更新向量库、清理缓存，甚至让 Agent 帮你分析哪些文档被问得最多。

Web Search：MVP 阶段不建议加入。个人博客 Agent 的目标是“基于已知知识回答”，引入搜索会增加幻觉风险和 API 成本。

## 开发流程

1. 后端重构：
    - 重点重构 SQL Table 设计，明确具体业务逻辑，包括如何接入用户不同的站点、文档等（重点）
    - 抽象 VectorDB 接口，将已有的 ChromaDB 封装通过 VectorDB Protocol 暴露出来，后续方便进一步集成 Qdrant、LanceDB 等其他向量库。
2. 前端开发（重点）：前端的设计最为关键，由于我没有 widget 的开发经验，所以需要非常长的时间进行迭代设计。
    - 首先设计 Widget 的 UI/UX，确保它足够简洁、易用，并且能够无缝集成到各种博客平台。
    - 随后提供简单的 Admin 控制台，提供必要的功能来管理和监控 Agent 的运行状态。
3. 新的能力开发：继续迭代增加更多的后端能力
    - 网络爬取
    - github repo 解析
    - 集成更多的 LLM 模型和向量库
    - Agent MCP 能力等