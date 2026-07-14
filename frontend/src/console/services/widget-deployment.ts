export interface WidgetDeploymentInput {
  projectUid: string;
  widgetUid: string;
}

export interface WidgetDeploymentCode {
  apiBaseUrl: string;
  html: string;
  missingConfig: Array<"apiBaseUrl" | "scriptUrl">;
  scriptUrl: string;
}

/** 生成可直接嵌入宿主网站的最小 Widget 部署代码。 */
export function createWidgetDeploymentCode(
  input: WidgetDeploymentInput,
): WidgetDeploymentCode {
  const apiBaseUrl = normalizeUrl(import.meta.env.VITE_API_BASE_URL ?? "");
  const scriptUrl = normalizeUrl(import.meta.env.VITE_WIDGET_SCRIPT_URL ?? "");
  const missingConfig: WidgetDeploymentCode["missingConfig"] = [];

  if (!apiBaseUrl) missingConfig.push("apiBaseUrl");
  if (!scriptUrl) missingConfig.push("scriptUrl");

  const html = [
    `<script type="module" src="${escapeHtmlAttribute(scriptUrl)}"></script>`,
    "",
    "<tada-ask-widget",
    `  api-base-url="${escapeHtmlAttribute(apiBaseUrl)}"`,
    `  project-uid="${escapeHtmlAttribute(input.projectUid)}"`,
    `  widget-uid="${escapeHtmlAttribute(input.widgetUid)}"`,
    "></tada-ask-widget>",
  ].join("\n");

  return { apiBaseUrl, html, missingConfig, scriptUrl };
}

export const WIDGET_CUSTOMIZATION_EXAMPLE = `tada-ask-widget {
  --tada-widget-background: #f7f3eb;
  --tada-widget-foreground: #26231f;
  --tada-widget-accent: #b6533c;
  --tada-widget-color-scheme: light;
}`;

function normalizeUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function escapeHtmlAttribute(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
