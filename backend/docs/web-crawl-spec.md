# TadaAsk Web Crawl Development Spec

## 1. Context

TadaAsk 的核心场景是个人部署、轻量级知识库问答，以及可嵌入静态站点的 RAG Widget。下一阶段的 web crawl 需要服务于这些目标：

- 抓取个人静态博客、文档站、项目说明页、依赖库/框架文档等静态页面。
- 将网页内容转为可检索、可引用的 Markdown 文本。
- 支持定时校验和增量更新，避免每次全量重建索引。
- 在 RAG 引用卡片中提供 `title + chunk content`，HTML 来源可跳转到原页面及 heading anchor。

Web crawl 的设计会影响底层 ORM、service 编排、解析器输出和 RAG 引用展示，因此在重构表结构前需要先确定 crawl 的基础边界。

---

## 2. Scope

### MVP Scope

MVP 阶段支持静态网页抓取，不处理复杂浏览器环境：

- 支持手动 URL 列表、sitemap URL、站点根路径递归发现。
- 支持同域名/指定路径范围内的链接发现。
- 支持固定同步间隔的重新抓取与变更检测。
- 支持 HTML 正文抽取并转为 Markdown。
- 支持解析已有 `id` 的 heading anchor，用于跳转到原网页段落。
- 支持将网页结果进入现有 RAG ingestion 流程：parse -> split -> FTS -> embedding -> vector index。

### Non-Goals

MVP 不实现：

- JS 渲染、浏览器自动化、Playwright/Puppeteer 抓取。
- 复杂反爬虫绕过、登录态抓取、验证码处理。
- 大规模通用爬虫队列。
- 完整网页快照渲染或页面镜像。
- 对外部网页内容的强一致历史归档。

---

## 3. Technical Direction

### Preferred Stack

当前阶段不引入 Scrapy 这类完整爬虫框架作为主路径。推荐使用轻量组件组合。

For TadaAsk's MVP, the primary HTML parsing path should be **BeautifulSoup4 + lxml + markdownify**. `trafilatura` and `parsel` can remain optional helpers, but they should not be the default content extraction path.

| Responsibility                      | Preferred Choice                                             |
| ----------------------------------- | ------------------------------------------------------------ |
| HTTP requests                       | `httpx.AsyncClient`                                          |
| HTML parsing and cleanup            | `beautifulsoup4` with the `lxml` parser                      |
| HTML to Markdown                    | `markdownify`                                                |
| Link discovery                      | BeautifulSoup selectors; `parsel` optional later             |
| Sitemap discovery                   | lightweight XML parsing with `lxml`; `parsel` optional later |
| Link normalization                  | standard URL utilities plus project rules                    |
| Scheduling                          | lightweight service-level scheduler / manual sync endpoint   |
| Generic article extraction fallback | `trafilatura`, optional                                      |

### Rationale

TadaAsk 的目标不是大规模网页采集，而是为个人知识库和文档站建立可控的 RAG 数据源。完整爬虫框架会引入额外 runtime、pipeline、调度和 FastAPI 集成复杂度。MVP 更需要保留业务编排控制权：URL 如何归一化、如何映射到 `SourceItem`、如何判断变更、如何重建索引，都和本项目的 ORM/RAG pipeline 强绑定。

For HTML parsing, TadaAsk should prefer DOM-level control over black-box article extraction:

- Most target pages are static blogs, project docs, and documentation sites.
- The crawler needs to remove navigation, sidebars, footers, copy buttons, scripts, styles, and other repeated noise.
- The parser needs to preserve document structure for Markdown-based splitting.
- Heading anchors must be read from real DOM `id` attributes and carried into chunk metadata.
- Future admin-side Markdown rendering should use the same parsed Markdown stored in `DocumentContent`.

BeautifulSoup4 is better suited for this MVP path because it supports direct DOM mutation and straightforward tree traversal. `markdownify` also fits naturally after BS4 cleanup. `parsel` is useful for selector-style extraction and XML/link discovery, but its read-oriented model is less suitable as the main cleanup and Markdown preparation layer. `trafilatura` is useful as a fallback for generic article extraction, but defaulting to it would reduce control over documentation structure and anchor mapping.

未来如果出现大量页面、多域名、复杂重试、暂停恢复、爬虫统计等需求，再考虑引入 Scrapy 或专用 crawler runtime。

---

## 4. Crawl Model

### Source-Level Strategy

抓取策略应由 `Source.source_type` 决定，而不是在 `SourceItem` 上堆叠展示或处理策略。推荐的 source 类型方向：

- `local_file`: 上传 PDF/Markdown/code 等文件。
- `web_crawl`: 抓取网页或文档站。
- `github_repo`: 后续接入 GitHub repo 的 Markdown/code。
- `custom_content`: 后续支持手写 Markdown 或自定义知识条目。

`Source` 应承担数据源级别配置，例如 crawl root、sitemap、URL 列表、include/exclude、同步间隔、最大页数等。`SourceItem` 只表示一次同步中发现并维护的具体页面或文件条目。

For web crawl, one `Source` represents one crawl scope, not necessarily one physical website. In most cases this scope is a documentation site or a site path. For manual pages, the scope can be a user-provided URL list. All pages in that scope share the same source-level sync policy, parser options, public visibility, project links, and vector collection.

### Crawl Entry Types

Web crawl 应支持三种入口。`single_url` should not be a separate MVP entry type; a single page is represented as `url_list` with one URL.

| Entry Type    | Purpose                                                          |
| ------------- | ---------------------------------------------------------------- |
| `url_list`    | 抓取用户显式提供的一个或多个页面；单页抓取是长度为 1 的 URL list |
| `sitemap_url` | 根据 sitemap 发现文档页，优先推荐                                |
| `site_root`   | 从指定根路径递归发现同范围链接                                   |

MVP should require exactly one `entry_type` per `Source.config_json` to avoid ambiguous discovery behavior. Recommended discovery preference for UI guidance:

```text
sitemap_url > site_root recursive crawl > url_list
```

Example `url_list` config:

```json
{
  "entry_type": "url_list",
  "urls": [
    "https://example.com/docs/intro",
    "https://example.com/docs/install"
  ]
}
```

### Scope Rules

Crawl 必须有范围控制，避免爬出目标文档站：

- allowed domains
- include path patterns
- exclude path patterns
- max pages
- max depth
- request delay / concurrency
- respect robots.txt, default true

这些配置适合放在 `Source.config_json` 一类的配置字段中，而不是拆成大量表字段。

### Config Ownership and Defaults

Crawl URLs and user-adjustable crawl rules are configured from the admin/frontend side and persisted in `Source.config_json`. The backend must still validate, normalize, and merge them with safe defaults and hard limits before execution.

Recommended `config_json` shape:

```json
{
  "entry_type": "sitemap_url",
  "sitemap_url": "https://example.com/sitemap.xml",
  "site_root": null,
  "urls": [],
  "allowed_domains": ["example.com"],
  "include_paths": ["/docs/"],
  "exclude_paths": ["/docs/internal/"],
  "content_selector": "main",
  "exclude_selectors": [".sidebar", ".toc", ".copy-button"],
  "max_pages": 200,
  "max_depth": 3,
  "concurrency": 4,
  "request_delay_ms": 500,
  "respect_robots_txt": true
}
```

If fields are omitted, backend defaults should be conservative:

- `allowed_domains`: derive exact hostnames from `sitemap_url`, `site_root`, or `urls`.
- `include_paths`: for `site_root`, derive from the root URL path; for `sitemap_url` and `url_list`, default to no extra include filter beyond domain checks.
- `exclude_paths`: default empty.
- `content_selector`: default to configured selector when present, then common content containers such as `main`, `article`, and documentation content wrappers.
- `exclude_selectors`: default to common noise selectors and tags such as `script`, `style`, `noscript`, `nav`, `footer`, and `aside`.
- `max_pages`, `max_depth`, `concurrency`, and `request_delay_ms`: use centralized settings with backend-enforced upper/lower bounds.
- `respect_robots_txt`: default true.

Defaults must not imply unrestricted crawling. Even when users provide no scope rules, the backend should restrict crawling to the derived domains and, for recursive `site_root`, the derived path scope.

---

## 5. URL Identity and Change Detection

### Stable Item Identity

网页内容会变化，但 URL 代表的是同一个页面。因此 web crawl 不能使用内容 hash 作为唯一身份。

明确建议：`SourceItem` 增加稳定条目键，例如：

```text
item_key
```

语义：

| Source Type      | item_key                             |
| ---------------- | ------------------------------------ |
| `local_file`     | storage key or source-local file key |
| `web_crawl`      | normalized URL without fragment      |
| `github_repo`    | repo/ref/path                        |
| `custom_content` | user-defined key                     |

唯一约束应倾向于：

```text
UniqueConstraint(source_id, item_key)
```

`item_hash` 保留为当前内容版本 hash，不作为网页条目的稳定身份。

### URL Normalization

Web crawl 必须在入库前规范化 URL：

- remove fragment (`#section`) from page identity
- remove tracking query params such as `utm_*`
- normalize trailing slash policy
- restrict to `http` / `https`
- resolve relative links against current page
- optionally use canonical URL, but avoid blindly trusting cross-domain canonical links

### Change Detection

增量同步应分为请求层和内容层：

- Request layer: ETag, Last-Modified, HTTP 304.
- Content layer: raw HTML hash and parsed Markdown hash.

索引重建应优先由 parsed Markdown hash 决定。网页模板、导航、脚本变化不一定代表正文变化。

Recommended flow:

```text
discover URLs
-> normalize and filter scope
-> fetch page
-> skip if HTTP 304
-> extract main Markdown
-> compare parsed content hash
-> unchanged: update checked/synced metadata only
-> changed: update DocumentContent and rebuild chunks/vectors
-> missing/deleted: mark stale or failed, do not silently delete content
```

---

## 6. HTML Parsing and Citation Metadata

### Parsing Strategy

HTML crawl should not rely only on generic file parsing. For crawled pages, the MVP parsing flow should be:

```text
raw HTML
-> BeautifulSoup(html, "lxml")
-> remove common noise nodes
-> select main content node
-> extract heading anchors from the real DOM
-> convert cleaned content HTML to Markdown with markdownify
-> emit ParsedDocument text and lightweight section metadata
```

Default cleanup should remove common non-content nodes such as:

- `script`, `style`, `noscript`
- `nav`, `footer`, `aside`
- repeated sidebar and table-of-contents blocks when selectors are configured
- copy buttons and other UI-only controls

For static documentation sites, content selection should prefer explicit configuration when available, then fall back to common containers such as `main`, `article`, or documentation-specific content wrappers. Generic article extraction with `trafilatura` can be added as a fallback when no suitable content container is found, but it should not replace the default BS4-based path.

`parsel` is optional. It may be introduced later for sitemap XML, XPath-heavy extraction, or high-volume selector use, but MVP HTML parsing should not depend on it.

### Heading Anchors

HTML anchor support should be based on real DOM anchors:

```text
<h2 id="install">Install</h2>
-> section_header = "Install"
-> metadata.anchor = "#install"
-> full action URL = origin_url + "#install"
```

The parser should not rely on `markdownify` preserving HTML `id` attributes in Markdown. Anchor mapping must be built by the HTML parser itself while producing the final Markdown text:

```text
cleaned DOM
-> find real heading elements with id attributes
-> convert content to Markdown in section/block order
-> record each section's start/end character offsets in the final Markdown text
-> return ParsedDocument.text plus section metadata
```

Recommended section metadata shape:

```json
{
  "start": 120,
  "end": 860,
  "level": 2,
  "header": "Install",
  "anchor": "#install"
}
```

`start` and `end` must refer to offsets in the exact Markdown string stored in `DocumentContent.content`. This avoids guessing whether a DOM heading still exists in the converted Markdown.

After splitting, each `TextChunk.pos` should be matched to the nearest preceding section metadata entry, then persisted on `DocumentChunk`:

```text
TextChunk.pos
-> nearest section where section.start <= pos
-> DocumentChunk.section_header = section.header
-> DocumentChunk.metadata_json.anchor = section.anchor
```

For MVP, if a chunk spans multiple sections, assign the chunk to the section that contains or immediately precedes the chunk start position. A future refinement may assign by largest character overlap, but that is not required for the first implementation.

If no real anchor exists, MVP should still show the chunk card but should not pretend that an anchor jump is reliable.

The parser should not generate synthetic anchors for external page jumps unless TadaAsk controls the rendered target page. Synthetic anchors are acceptable only for future admin-side parsed Markdown rendering.

### RAG Display

MVP citation card uses minimal fields:

- source type / document type
- title
- filename
- origin URL
- chunk content
- page number for PDF if available
- section header if available
- metadata such as anchor

Full action is resolved by a backend request or URL construction at response time:

- PDF / Markdown / code: download or no full action depending on endpoint support.
- HTML: open original page, optionally with heading anchor.
- Admin Markdown rendering: later reads from `DocumentContent.content`.

Do not store full document content in `RAGSnapshot`. The snapshot may store chunk content for stable citation card display, but full content should be requested separately.

---

## 7. ORM Refactor Direction

The table design should stay lightweight. Avoid adding display-policy fields or many duplicated type/status columns at `SourceItem` level.

### Clear Refactor Candidates

These changes are strongly recommended before implementing web crawl:

1. Add `Source.config_json`
   - Stores crawl configuration such as URL list, root URL, sitemap URL, scope rules, max pages, request delay, content selector options, and future sync behavior.

2. Add `SourceItem.item_key`
   - Provides source-local stable identity.
   - Required because web pages are identified by normalized URL, not content hash.

3. Revisit unique constraints on `SourceItem`
   - Current content-hash-based uniqueness is not sufficient for web pages.
   - Prefer uniqueness by `(source_id, item_key)`.

### Keep Lightweight for MVP

Do not add these as first-class columns unless later requirements prove they are needed:

- display policy
- full action
- source URL with anchor
- line end position
- parser version fields
- full content snapshot

Use existing fields where possible:

- `SourceItem.origin_url` for crawled page URL.
- `SourceItem.item_hash` for current content hash.
- `DocumentContent.content` for parsed Markdown.
- `DocumentChunk.section_header` for nearest heading.
- `DocumentChunk.page_number` for PDF page.
- `DocumentChunk.metadata_json` for HTML anchor and light source metadata.
- `ChatMessage.rag_snapshot` JSON for answer-time citation snapshot.

### RAG Snapshot

Keep `ChatMessage.rag_snapshot` as JSON for MVP. It is appropriate because:

- snapshot belongs to one assistant message;
- citation data is small;
- reading chat history can load citations without extra joins;
- snapshot is not the authoritative content store.

Consider a separate citation table only when TadaAsk needs citation analytics, independent citation pagination, high-volume history, or cross-message citation queries.

---

## 8. Affected Areas

The implementation will likely touch these layers, but exact module boundaries can evolve during development:

| Area                        | Expected Impact                                                                        |
| --------------------------- | -------------------------------------------------------------------------------------- |
| `core.constants` / settings | source types, crawl defaults, allowed limits                                           |
| `db.models` / `db.schemas`  | source config and source item identity                                                 |
| `crud.source`               | upsert source items by stable item key                                                 |
| `services.rag`              | sync orchestration and reindex decisions                                               |
| `parser`                    | HTML extraction result and heading metadata                                            |
| `storage`                   | local storage remains enough for MVP; future S3-compatible download can reuse protocol |
| `api.admin`                 | manual sync endpoint, source configuration, future sync status                         |
| `api.visitor`               | citation card data and full action resolution                                          |

Layer boundaries should remain:

```text
Router -> Service -> CRUD / Parser / Storage / RAG providers
```

Crawler-specific HTTP fetching and parsing should not leak into routers or chat services.

---

## 9. MVP Development Order

Recommended order:

1. Finalize minimal ORM changes: `Source.config_json`, `SourceItem.item_key`, source-item uniqueness.
2. Implement URL normalization and source scope rules.
3. Implement sitemap, site-root, and URL-list discovery.
4. Implement static page fetch and content extraction.
5. Upsert crawled pages into `SourceItem` and `DocumentContent`.
6. Reuse existing ingestion pipeline for split / embed / index.
7. Add minimal citation metadata for HTML anchors.
8. Add sync interval and lightweight manual/periodic trigger.

This keeps TadaAsk focused: crawl enough static documentation to power grounded RAG answers, without becoming a general-purpose crawler or document rendering platform.
