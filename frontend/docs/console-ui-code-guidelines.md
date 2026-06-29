# Console UI Code Guidelines

This guide is for small, manual UI edits in the TadaAsk admin console. It is not
a full design system. The goal is to keep Vue templates, Tailwind classes, and
CSS tokens consistent while the MVP UI is still evolving.

## Formatting

- Use `pnpm format` before committing frontend UI changes.
- Use `pnpm format:check` when you only want to verify formatting.
- VS Code should use Prettier as the default formatter. The frontend workspace
  has `prettier.requireConfig` enabled so random editor formatters do not drift.
- Tailwind classes are sorted by `prettier-plugin-tailwindcss`. Do not manually
  fight class order unless the rendered UI is wrong.

## Where Styles Belong

- Put repeated visual rules in `src/shared/styles/style.css`.
- Put page-specific layout composition in the `.vue` template with Tailwind.
- Do not create a new component just to avoid three or four repeated classes.
- Do not add business state, props, emits, stores, or API calls just to support a
  visual adjustment.

Use `style.css` for:

- Console color, text, surface, line, radius, and density tokens.
- Shared console utilities such as `.console-page`, `.console-panel`,
  `.console-table-panel`, and `.console-scrollbar`.
- Rules that should be consistent across Project, Chat, Sources, and Settings.

Use template classes for:

- One-off grid placement.
- Responsive column changes.
- Component-local alignment.
- Small spacing differences that are not a global convention yet.

## CSS Tokens

Prefer existing console tokens before adding new values.

Text:

- `--text-strong`: primary headings and key values.
- `--text-body`: normal table/content text.
- `--text-muted`: secondary copy.
- `--text-faint`: labels, captions, breadcrumbs, helper text.
- `--text-disabled`: low-emphasis section labels or disabled content.

Surface:

- `--surface-base`: page background.
- `--surface-shell`: sidebar/header shell surfaces.
- `--surface-panel`: normal panels and tables.
- `--surface-panel-soft`: lighter-weight cards and empty states.
- `--surface-raised`: dialogs, dropdowns, raised controls.
- `--surface-hover`: nav/table/control hover states.

Lines:

- `--line-soft`: panel borders, table rows, subtle dividers.
- `--line`: normal borders.
- `--line-strong`: scrollbar thumbs or stronger separators.

Radius:

- `--console-radius-sm`: compact controls and small inner elements.
- `--console-radius-md`: nav links, buttons, compact fields.
- `--console-radius-lg`: panels, metric cards, empty states.
- `--console-radius-xl`: only for large framed surfaces.
- `--console-radius-pill`: badges, avatars, scrollbar thumbs.

Avoid mixing random `rounded-xl`, `rounded-[13px]`, or `rounded-full` unless
there is a clear component reason. Prefer the token-backed utilities.

## Key Example: Text And Width

Text width should usually be controlled by the parent container, not each text
node.

Good:

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

Good CSS:

```css
.console-page-head {
  max-width: 58rem;
}
```

Avoid:

```html
<p class="console-page-subtitle w-[720px]">...</p>
```

Use these width rules:

- Use `rem` for reading width, such as `max-width: 58rem`.
- Use `%` or fractional grid tracks for layout relationships.
- Use Tailwind spacing scale when the value is mechanical, such as `max-w-340`
  for 1360px.
- Use arbitrary pixel values only when matching a specific asset, browser API, or
  non-tokenized platform requirement.
- Prefer `max-width` over fixed `width` for text blocks.

## Page Structure

Use this order for admin console pages:

1. `.console-page`
2. `.console-page-head`
3. metric or summary region, if the page needs one
4. `.console-section` blocks
5. `.console-panel` or `.console-table-panel` inside sections

Do not put every section title inside a card. Section headings should often sit
between cards to give the page breathing room.

## Tables

- Use `.console-table-panel` for table shells.
- Keep table panels visually stable with a fixed table area height.
- Let table content scroll inside the panel instead of growing the whole page.
- Table headers should be small, faint, uppercase labels.
- Avoid showing raw IDs such as `source_uid` or `widget_uid` in normal rows.
  Surface them in detail views, tooltips, or debug panels later if needed.

## Buttons And Actions

- Buttons must keep `type="button"` and `aria-label`.
- Prefer short visible labels: `Create`, `Import`, `Global sources`.
- Use dialog titles for longer action context, such as `Create widget`.
- Row-level secondary actions should usually live under a `DropdownMenu`.

## Responsive Rules

- Prefer CSS Grid and `minmax(0, 1fr)` for primary layout.
- Use breakpoints to change columns, not to micromanage every text block.
- Keep stable dimensions for dashboards, table panels, metric cards, and fixed
  tool surfaces.
- Avoid viewport-scaled font sizes. Use responsive layout, not responsive type,
  unless the text is a real page title.

## Tailwind Class Values

Use canonical Tailwind classes when they are clearer and equivalent.

Good:

```html
<div class="max-w-340">...</div>
```

Acceptable arbitrary values:

```html
<div class="grid-cols-[260px_minmax(0,1fr)]">...</div>
<div
  class="bg-[radial-gradient(circle_at_74%_-12%,rgba(36,211,196,0.14),transparent_30rem)]"
>
  ...
</div>
```

Do not replace expressive layout values with canonical classes if it makes the
intent harder to read.

## shadcn-vue

- Use shadcn-vue for standard controls: Button, Badge, Dialog, DropdownMenu,
  Input, Textarea, Label, Switch, Table, Select.
- Keep visual hierarchy in CSS tokens and console utilities rather than forking
  shadcn primitives.
- If a shadcn component needs broad restyling, prefer theme tokens first.

## Adding New Tokens

Add a new token only when:

- The value is repeated across pages.
- The value expresses a real design decision.
- A local Tailwind class would make future edits inconsistent.

Do not add a token for a one-off alignment or temporary placeholder.
