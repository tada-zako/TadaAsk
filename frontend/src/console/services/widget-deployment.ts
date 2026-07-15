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

  // 缺少构建配置时仍展示可辨识的代码结构，但禁止直接复制部署。
  const displayApiBaseUrl = apiBaseUrl || "YOUR_API_BASE_URL";
  const displayScriptUrl = scriptUrl || "YOUR_WIDGET_SCRIPT_URL";

  const html = [
    `<script type="module" src="${escapeHtmlAttribute(displayScriptUrl)}"></script>`,
    "",
    "<tada-ask-widget",
    `  api-base-url="${escapeHtmlAttribute(displayApiBaseUrl)}"`,
    `  project-uid="${escapeHtmlAttribute(input.projectUid)}"`,
    `  widget-uid="${escapeHtmlAttribute(input.widgetUid)}"`,
    "></tada-ask-widget>",
  ].join("\n");

  return { apiBaseUrl, html, missingConfig, scriptUrl };
}

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
