# 控制台 UI 代码规范 (Console UI Code Guidelines)

本指南适用于 TadaAsk 管理控制台（admin console）中轻量、手动的 UI 修改。它并不是一个完整的、繁重的设计系统，其目的是在 MVP（最小可行性产品）阶段的 UI 持续演进过程中，保持 Vue 模板、Tailwind 类和 CSS 变量（Tokens）的一致性。

## 格式化 (Formatting)

- 在提交前端 UI 更改之前，请运行 `pnpm format` 进行格式化。
- 如果只想验证格式，请运行 `pnpm format:check`。
- VS Code 应使用 Prettier 作为默认格式化程序。前端工作区已启用 `prettier.requireConfig`，以防止因不同的编辑器格式化设置导致代码冲突。
- Tailwind 类名由 `prettier-plugin-tailwindcss` 自动排序。除非渲染的 UI 出现错误，否则请勿手动调整类名顺序。

## 样式归属 (Where Styles Belong)

- 将重复的视觉规则放入 `src/shared/styles/style.css` 中。
- 页面特有的布局组合应直接在 `.vue` 模板中通过 Tailwind 类实现。
- 不要仅仅为了避免三四个重复的类而创建一个新的组件。
- 不要仅仅为了支持视觉调整而添加业务状态、Props、Emits、Stores 或 API 调用。

在 `style.css` 中编写：

- 控制台的颜色、文本、表面（Surface）、边框线（Line）、圆角（Radius）和密度（Density）等 Tokens。
- 共享的控制台实用类，例如 `.console-page`、`.console-panel`、`.console-table-panel` 和 `.console-scrollbar`。
- 需要在项目（Project）、聊天（Chat）、数据源（Sources）和设置（Settings）页面之间保持一致的样式规则。

在模板类（Template Classes）中编写：

- 一次性的网格定位（Grid placement）。
- 响应式列数变化。
- 组件局部的对齐方式。
- 尚未成为全局约定的微小间距差异。

## CSS 变量 (CSS Tokens)

在添加新值之前，请优先使用现有的控制台 Tokens。

文本 (Text):

- `--text-strong`: 主要标题和关键数值。
- `--text-body`: 普通表格/内容文本。
- `--text-muted`: 次要副本/辅助文本。
- `--text-faint`: 标签、说明文字、面包屑、帮助文本。
- `--text-disabled`: 低强调度的板块标签或禁用内容。

表面 (Surface):

- `--surface-base`: 页面背景。
- `--surface-shell`: 侧边栏/头部外壳背景。
- `--surface-panel`: 普通面板和表格背景。
- `--surface-panel-soft`: 较轻量的卡片和空白状态背景。
- `--surface-raised`: 对话框、下拉菜单、浮动控件背景。
- `--surface-hover`: 导航/表格/控件的悬停状态。

边框线 (Lines):

- `--line-soft`: 面板边框、表格行、微妙的分割线。
- `--line`: 普通边框。
- `--line-strong`: 滚动条滑块或较强的分割线。

圆角 (Radius):

- `--console-radius-sm`: 紧凑型控件和微小内部元素。
- `--console-radius-md`: 导航链接、按钮、紧凑型输入框。
- `--console-radius-lg`: 面板、指标卡片、空白状态。
- `--console-radius-xl`: 仅用于大型框架表面。
- `--console-radius-pill`: 徽章（Badges）、头像、滚动条滑块。

避免混用随机的 `rounded-xl`、`rounded-[13px]` 或 `rounded-full`，除非有明确的组件设计原因。请优先使用基于 Token 的实用类。

## 文本与宽度 (Text And Width)

文本的宽度通常应由其父容器控制，而不是由每个文本节点单独控制。

推荐做法：

```html
<header class="console-page-head">
  <p class="console-kicker">Docs Assistant</p>
  <h1 class="console-page-title">Project</h1>
  <p class="console-page-subtitle">
    Project workspace for deployed widgets, linked sources, and visitor-facing
    RAG configuration.
  </p>
</header>
```

推荐的 CSS：

```css
.console-page-head {
  max-width: 58rem;
}
```

避免做法：

```html
<p class="console-page-subtitle w-[720px]">...</p>
```

请遵循以下宽度规则：

- 阅读宽度使用 `rem`，例如 `max-width: 58rem`。
- 布局关系使用 `%` 或比例网格轨道（Fractional grid tracks）。
- 当数值是机械性的，使用 Tailwind 的间距比例，例如 1360px 对应 `max-w-340`。
- 仅在匹配特定资源、浏览器 API 或非 Token 化的平台要求时，才使用绝对像素值（px）。
- 文本块优先使用 `max-width` 而非固定的 `width`。

## 页面结构 (Page Structure)

管理控制台页面请使用以下结构顺序：

1. `.console-page` (页面容器)
2. `.console-page-head` (页面头部)
3. 指标或摘要区域（如果页面需要）
4. `.console-section` (板块区块)
5. 板块内部的 `.console-panel` 或 `.console-table-panel`

不要把每个板块的标题都塞进卡片里。板块标题通常应该放在卡片之间，给页面留出呼吸空间。

## 表格 (Tables)

- 表格的外壳使用 `.console-table-panel`。
- 保持表格面板的视觉稳定性，使用固定的表格区域高度。
- 让表格内容在面板内部滚动，而不是撑大整个页面。
- 表格头部应为小号、低强调度、大写的标签。
- 避免在普通行中显示原始 ID（如 `source_uid` 或 `widget_uid`）。如有需要，可在后续的详情视图、工具提示或调试面板中展示。

## 按钮与操作 (Buttons And Actions)

- 按钮必须保留 `type="button"` 和 `aria-label` 属性。
- 优先使用简短的可见标签：`Create`、`Import`、`Global sources`。
- 较长的操作上下文使用对话框标题，例如 `Create widget`。
- 行级的次要操作通常应放在 `DropdownMenu`（下拉菜单）中。

## 响应式规则 (Responsive Rules)

- 主布局优先使用 CSS Grid 和 `minmax(0, 1fr)`。
- 使用断点（Breakpoints）来改变列数，而不是去微调每个文本块。
- 仪表盘、表格面板、指标卡片和固定工具表面保持稳定的尺寸。
- 避免使用视口缩放的字体大小（Viewport-scaled font sizes）。除非是真正的页面大标题，否则应使用响应式布局，而非响应式字号。

## Tailwind 类名取值 (Tailwind Class Values)

当规范的 Tailwind 类名更清晰且等价时，请优先使用。

推荐做法：

```html
<div class="max-w-340">...</div>
```

可接受的任意值（Arbitrary values）：

```html
<div class="grid-cols-[260px_minmax(0,1fr)]">...</div>
<div
  class="bg-[radial-gradient(circle_at_74%_-12%,rgba(36,211,196,0.14),transparent_30rem)]"
>
  ...
</div>
```

如果使用规范的类名会让设计意图变得难以阅读，请不要替换那些具有表现力的布局值。

## shadcn-vue

- 标准控件使用 shadcn-vue：Button、Badge、Dialog、DropdownMenu、Input、Textarea、Label、Switch、Table、Select。
- 保持视觉层级在 CSS Tokens 和控制台实用类中，而不是去派生（fork）shadcn 基础组件。
- 如果 shadcn 组件需要大范围的样式重构，请优先考虑调整主题 Tokens。

## 添加新 Tokens (Adding New Tokens)

仅在满足以下条件时才添加新 Token：

- 该值在多个页面中重复出现。
- 该值表达了真正的设计决策。
- 使用局部的 Tailwind 类会让未来的修改变得不一致。

不要为了一次性的对齐或临时占位符添加 Token。
