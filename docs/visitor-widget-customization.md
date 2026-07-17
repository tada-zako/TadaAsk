# Visitor Widget customization

[中文](./visitor-widget-customization.zh.md)

TadaAsk Widget is a Web Component. Use element attributes to configure its content and display position, and CSS variables to adjust part of its appearance.

The Widget uses Shadow DOM, so host-page selectors such as `button` or `.class` may not reliably modify its internal styles. Define Widget styles with the public CSS variables listed here instead of relying on internal DOM structure.

## Deployment example

```html
<script src="https://your-domain.example/widget/tada-ask-widget.js"></script>

<tada-ask-widget
  api-base-url="https://your-domain.example/api"
  project-uid="your-project-uid"
  widget-uid="your-widget-uid"
  assistant-title="Docs Assistant"
  placeholder="Ask me about the docs…"
  launcher-position="bottom-right"
  panel-align="right"
></tada-ask-widget>
```

The following attributes are required at runtime. Get them from the embed code generated in the Admin Console.

| Attribute | Description |
| --- | --- |
| `api-base-url` | Base URL of the TadaAsk backend API. |
| `project-uid` | Public identifier of the target Project. |
| `widget-uid` | Public identifier of the target Widget deployment. |

`project-uid` and `widget-uid` are used by the backend Widget CORS middleware to validate cross-origin requests for the configured `site_origin`.

## Element attributes

| Attribute | Default | Description |
| --- | --- | --- |
| `assistant-title` | `TadaAsk Assistant` | Widget title. |
| `logo-url` | Empty | URL for the logo shown beside the title. |
| `placeholder` | `Ask anything…` | Composer placeholder text. |
| `launcher-position` | `bottom-right` | Launcher position: `bottom-left` or `bottom-right`. |
| `panel-align` | `right` | Panel alignment: `left`, `center`, or `right`. |

## Customize the theme

Set variables on the Widget element in your site's CSS:

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

| Group | Variables |
| --- | --- |
| Surfaces and text | `--tada-widget-background`, `--tada-widget-surface`, `--tada-widget-raised`, `--tada-widget-user`, `--tada-widget-foreground`, `--tada-widget-body`, `--tada-widget-muted`, `--tada-widget-faint` |
| Borders and accent | `--tada-widget-border`, `--tada-widget-border-soft`, `--tada-widget-accent`, `--tada-widget-accent-foreground`, `--tada-widget-accent-soft` |
| Citations | `--tada-widget-citation-background`, `--tada-widget-citation-border`, `--tada-widget-citation-foreground` |
| Global appearance | `--tada-widget-color-scheme` (`light` or `dark`), `--tada-widget-font` |

## Size and position

The Widget allows some adjustment of its size and position. Set these variables on the host element:

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

- `--tada-widget-panel-width`, `--tada-widget-panel-max-width`, and `--tada-widget-panel-max-height` control panel size.
- `--tada-widget-empty-height` controls the panel height before the first message.
- `--tada-widget-launcher-size` controls launcher size; the actual size is limited to 48–64px.
- `--tada-widget-offset-x` and `--tada-widget-offset-y` control the distance from the viewport edge.
- `--tada-widget-z-index` controls the Widget's stacking layer.

On narrow screens, the Widget prioritizes staying within the viewport, so the panel can be smaller than the configured value. Use normal CSS lengths such as `vw` or `px`, and check the result on your target page.

## Boundaries

Customization is limited to the attributes and CSS variables in this document. Message flow, Markdown rendering, citation interactions, request behavior, and the Widget's internal DOM are not compatible customization interfaces; their implementation may change in future releases.
