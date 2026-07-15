# Visitor Widget customization

MVP 只允许通过 Web Component 属性和 CSS custom properties 定制外观；内部消息、Markdown、Citation、Sources 与流式交互逻辑不允许修改。Inline citation 的颜色可通过公开变量调整。

## 标签属性

- `assistant-title`
- `logo-url`
- `placeholder`
- `launcher-position`: `bottom-left | bottom-right`
- `panel-align`: `left | center | right`

`api-base-url`、`project-uid`、`widget-uid` 是运行必需配置，不属于外观定制。

## 公开 CSS variables

主题：

- `--tada-widget-background`
- `--tada-widget-surface`
- `--tada-widget-raised`
- `--tada-widget-user`
- `--tada-widget-foreground`
- `--tada-widget-body`
- `--tada-widget-muted`
- `--tada-widget-faint`
- `--tada-widget-border`
- `--tada-widget-border-soft`
- `--tada-widget-accent`
- `--tada-widget-accent-foreground`
- `--tada-widget-accent-soft`
- `--tada-widget-citation-background`
- `--tada-widget-citation-border`
- `--tada-widget-citation-foreground`
- `--tada-widget-color-scheme`
- `--tada-widget-font`

布局：

- `--tada-widget-panel-width`
- `--tada-widget-panel-max-width`
- `--tada-widget-panel-max-height`
- `--tada-widget-empty-height`
- `--tada-widget-launcher-size`
- `--tada-widget-offset-x`
- `--tada-widget-offset-y`
- `--tada-widget-z-index`

尺寸变量仍受 Widget 内部移动端规则和必要的可用性下限约束。

本地验证入口：`/widget/custom-theme.html`。该页面通过宿主 CSS 设置变量，并故意定义冲突的全局控件样式，用于验证 Shadow DOM 隔离。
