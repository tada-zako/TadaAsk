# Visitor Widget 自定义

[English](./visitor-widget-customization.md)

TadaAsk Widget 是一个 Web Component。TadaAsk 允许通过标签属性配置 widget 的内容与展示位置，并通过 CSS variables 调整部分外观。

Widget 使用 Shadow DOM，宿主网站的 `button`、`.class` 等选择器可能不会稳定地修改 Widget 内部样式；
Widget CSS 样式的定义，请使用本文列出的公开 CSS 变量，而不是依赖内部 DOM 结构进行修改。

## 部署示例

```html
<script src="https://your-domain.example/widget/tada-ask-widget.js"></script>

<tada-ask-widget
  api-base-url="https://your-domain.example/api"
  project-uid="your-project-uid"
  widget-uid="your-widget-uid"
  assistant-title="Docs Assistant"
  placeholder="问我关于文档的问题…"
  launcher-position="bottom-right"
  panel-align="right"
></tada-ask-widget>
```

其中 `api-base-url`、`project-uid` 与 `widget-uid` 是运行所必需的配置，应从 Admin Console 的 Project 页面生成的部署代码中获取。

| 属性           | 说明                             |
| -------------- | -------------------------------- |
| `api-base-url` | TadaAsk 后端 API 地址。          |
| `project-uid`  | 对应 Project 的公开标识。        |
| `widget-uid`   | 对应 Widget 部署配置的公开标识。 |


`project-uid` 以及 `widget-uid` 将会用于后端 Widget CORS Middleware 的跨域请求验证，以支持动态 `site-origin` 跨域请求。


## 标签属性

| 属性                | 默认值              | 说明                                            |
| ------------------- | ------------------- | ----------------------------------------------- |
| `assistant-title`   | `TadaAsk Assistant` | Widget 标题。                                   |
| `logo-url`          | 空                  | 标题旁显示的 Logo 图片地址。                    |
| `placeholder`       | `Ask anything…`     | 输入框占位文字。                                |
| `launcher-position` | `bottom-right`      | 启动按钮位置：`bottom-left` 或 `bottom-right`。 |
| `panel-align`       | `right`             | 问答面板对齐方式：`left`、`center` 或 `right`。 |

## 自定义主题

在宿主网站的 CSS 中为 Widget 元素设置变量：

```css
tada-ask-widget {
  --tada-widget-background: #f5f0e5;
  --tada-widget-surface: #ebe3d4;
  --tada-widget-raised: #fffaf0;
  --tada-widget-user: #ded5c5;
  --tada-widget-foreground: #25251f;
  --tada-widget-body: #44453b;
  --tada-widget-muted: #686b5d;
  --tada-widget-faint: #898b7e;
  --tada-widget-border: rgb(43 45 37 / 0.22);
  --tada-widget-border-soft: rgb(43 45 37 / 0.12);
  --tada-widget-accent: #d64f32;
  --tada-widget-accent-foreground: #fff9ed;
  --tada-widget-accent-soft: rgb(214 79 50 / 0.12);
  --tada-widget-citation-background: #e7ded0;
  --tada-widget-citation-border: #a7826d;
  --tada-widget-citation-foreground: #8d3425;
  --tada-widget-color-scheme: light;
  --tada-widget-font: "Manrope", sans-serif;
}
```

| 分组           | 变量                                                                                                                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 基础表面与文字 | `--tada-widget-background`、`--tada-widget-surface`、`--tada-widget-raised`、`--tada-widget-user`、`--tada-widget-foreground`、`--tada-widget-body`、`--tada-widget-muted`、`--tada-widget-faint` |
| 边框与强调色   | `--tada-widget-border`、`--tada-widget-border-soft`、`--tada-widget-accent`、`--tada-widget-accent-foreground`、`--tada-widget-accent-soft`                                                       |
| 引用样式       | `--tada-widget-citation-background`、`--tada-widget-citation-border`、`--tada-widget-citation-foreground`                                                                                         |
| 全局外观       | `--tada-widget-color-scheme`（`light` 或 `dark`）、`--tada-widget-font`                                                                                                                           |

## 尺寸与位置

Widget 允许进行一定的尺寸与位置上的调整，同样在宿主元素上设置以下变量：

```css
tada-ask-widget {
  --tada-widget-panel-width: 72vw;
  --tada-widget-panel-max-width: 920px;
  --tada-widget-panel-max-height: 680px;
  --tada-widget-empty-height: 430px;
  --tada-widget-launcher-size: 60px;
  --tada-widget-offset-x: 30px;
  --tada-widget-offset-y: 30px;
  --tada-widget-z-index: 2147483000;
}
```

- `--tada-widget-panel-width`、`--tada-widget-panel-max-width` 与 `--tada-widget-panel-max-height` 控制问答面板大小。
- `--tada-widget-empty-height` 控制尚无消息时的面板高度。
- `--tada-widget-launcher-size` 控制启动按钮尺寸；实际大小会限制在 48–64px 之间。
- `--tada-widget-offset-x` 与 `--tada-widget-offset-y` 控制距离屏幕边缘的偏移。
- `--tada-widget-z-index` 控制 Widget 的堆叠层级。

在窄屏设备上，Widget 会优先保证不超出视口，因此面板尺寸可能小于指定值。建议使用 `vw`、`px` 等正常 CSS 长度，并在自己的目标页面上实际检查效果。


## 边界

自定义样式设置只覆盖本文的标签属性和 CSS variables。消息流程、Markdown、引用交互、请求逻辑和 Widget 内部 DOM 不属于兼容的自定义接口，后续版本可能调整其内部实现。
