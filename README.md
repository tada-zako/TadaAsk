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
    - 用户身份鉴权设计：至少需要实现能够确认 Admin 与 Visitor 的身份鉴权逻辑。需要 Admin 权限用于 admin/api/ 的访问控制，以及 visitor 与 admin 之间不同的 API 内部业务处理方式。（MVP 基于 env 驱动实现）
    - 封装 llama.cpp API，提供 embedding 和 hyde/hype 功能
    - 实现基于 breakpoints 的文档切割器
2. 前端开发（重点）：前端的设计最为关键，由于我没有 widget 的开发经验，所以需要非常长的时间进行迭代设计。
    - 首先设计 Widget 的 UI/UX，确保它足够简洁、易用，并且能够无缝集成到各种博客平台。
    - 随后提供简单的 Admin 控制台，提供必要的功能来管理和监控 Agent 的运行状态。
3. 新的能力开发：继续迭代增加更多的后端能力
    - 网络爬取
    - github repo 解析
    - 集成更多的 LLM 模型和向量库
    - Agentic Hybrid Search，不再只是检索 -> 作为 context -> LLM 生成的单项流程，而是引入 Agent 能力，由 LLM 决定是否进一步检索、调用工具等
    - 多向量 collection 召回后的 reranking 逻辑
    - 首次运行网页端的初始化向导（初始化完成后，需要确保 login/ 相关功能锁定，避免安全风险）
    - 考虑分布式/多进程部署情况下，代码的兼容性和逻辑优化

## 未整理的内容

#codebase 请分析当前的整个项目实现，对当前项目的整体设计、系统架构、功能需求以及系统大小有一个清晰的把握。
现在，我希望你站在专业的设计者角度，帮我确定一个后续的RAG开发方向。

### 当前项目功能需求
该项目本质是一个我个人的开源学习项目，没有实际的商业化需求，所以在把握项目的开发方向时，不需要将“重构代价”纳入考量。
此外，该项目的开发目标，是以"kapa.ai"的功能为参考：
- 允许主要的admin用户通过html标签插入到自己的静态网站，以提供具备RAG的AI对话能力
- admin能够通过自己的dashboard对整个部署的项目进行管理和监控；目标是一个dash，能够管理部署到多个不同的网站的服务
- visitor用户能够在部署该服务的网站，和该项目进行对话——RAG检索辅助搜索内容

除了对于 kapa 功能的复刻，我还希望提供一些更加个性化的服务，并尝试学习新的LLM技术：
- 考虑到该项目以个体Admin为主要服务目标，在并发量的控制上不会像是真正的大型平台非常宽容；可以理解为visitor的对话本质只是附加服务（考虑到个人部署者不可能肩负起非常庞大的对话量消耗），所以对于visitor对话功能，需要在费用处理上做出让步和重点优化
- 对于个人的RAG使用（集成在个人控制台中），我希望能够尝试学习实践落地一些前沿的RAG技术：Advanced RAG，Agentic RAG能力，LLM wiki式的允许LLM基于用户的对话和历史检索创建属于自己的WIKI知识库


### 具体开发方向指导
回到当前具体的开发方向指导上，我希望你能够基于上述我的功能需求，给我以一定的方向指导。
当前的RAG实现上，基本完成了对于模块的封装，但是完整的流程编排尚未开始，初步构想是完成基于FTS+embedding search + rerank的hybrid search
除此之外，我还存在一些为解决的困惑：
- RAG技术的落地：目前的RAG系统，应该是将检索到的chunk发送给LLM；那么FTS检索的结果该如何和embedding结果结合？这应该需要重点重构 #file:models.py 中 #sym:DocumentChunk 的设计：chunk应该被保存在SQL中，确保embedding检索后能够拿到需要的chunk content；


### 实际开发需求
- 由于该项目本质是个人学习为主，所以对于LLM开发，没有使用较为重量级的langchain之类的大型开发框架，而是从底层的第三方依赖开始封装，并逐步编排成完整的功能链
