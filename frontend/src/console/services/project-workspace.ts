import { projectApi } from "@/console/api/projects";
import { sourceApi } from "@/console/api/sources";
import type { components } from "@/shared/api/generated/schema";

export type ProjectRead = components["schemas"]["ProjectRead"];
export type ProjectSettingsRead = components["schemas"]["ProjectSettingsRead"];
export type ProjectWidgetRead = components["schemas"]["ProjectWidgetRead"];
export type ProjectWidgetCreate = components["schemas"]["ProjectWidgetCreate"];
export type ProjectWidgetUpdate = components["schemas"]["ProjectWidgetUpdate"];
export type SourceRead = components["schemas"]["SourceRead"];

// project 选择相关字段对象
export interface ProjectOption {
  uid: string;
  name: string;
  description: string | null;
}

// project 相关指标
export interface ProjectMetric {
  key: string;
  label: string;
  value: string;
  foot: string;
  tone: "primary" | "success" | "warning" | "muted";
}

export interface ProjectHealthItem {
  key: string;
  title: string;
  detail: string;
  status: string;
  tone: "success" | "warning" | "muted";
}

export interface ProjectSourceRow {
  uid: string;
  name: string;
  typeLabel: string;
  visibilityLabel: string;
  visibilityTone: "success" | "muted";
  statusLabel: string;
  statusTone: "success" | "warning" | "danger" | "muted";
  lastSyncedLabel: string;
  isPublic: boolean;
}

export interface ProjectWidgetRow {
  uid: string;
  name: string;
  siteOrigin: string;
  isEnabled: boolean;
  enabledLabel: "Enabled" | "Disabled";
  enabledActionLabel: "Enable" | "Disable";
  createdLabel: string;
  updatedLabel: string;
}

// ViewModel 是组件唯一消费的数据形态，避免 Vue 组件理解后端字段细节。
export interface ProjectWorkspaceViewModel {
  project: ProjectRead;
  settings: ProjectSettingsRead;
  metrics: ProjectMetric[];
  healthItems: ProjectHealthItem[];
  sourceRows: ProjectSourceRow[];
  widgetRows: ProjectWidgetRow[];
  availableSources: ProjectSourceRow[];
}

export interface CreateProjectInput {
  name: string;
  description: string | null;
}

/**
 * 统一 API 响应解包处理，
 * 当存在 error 或 data 不存在时抛出异常
 * @param data
 * @param error
 * @param fallbackMessage
 * @returns
 */
function unwrapApiData<T>(
  data: T | undefined,
  error: unknown,
  fallbackMessage: string,
): T {
  // openapi-fetch 的 error 可能是 validation detail，也可能是普通对象。
  if (error) {
    throw new Error(getApiErrorMessage(error, fallbackMessage));
  }

  if (data === undefined) {
    throw new Error(fallbackMessage);
  }

  return data;
}

function getApiErrorMessage(error: unknown, fallbackMessage: string): string {
  if (!error || typeof error !== "object") {
    return fallbackMessage;
  }

  if ("detail" in error) {
    const detail = error.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String(item.msg)
            : String(item),
        )
        .join(", ");
    }
  }

  return fallbackMessage;
}

function toProjectOption(project: ProjectRead): ProjectOption {
  return {
    uid: project.uid,
    name: project.name,
    description: project.description ?? null,
  };
}

/**
 * 根据当前可用 projects 列表和首选 projectUid，
 * 解析最终选中 projectUid
 * @param projects
 * @param preferredUid
 * @returns
 */
export function resolveProjectUid(
  projects: ProjectOption[],
  preferredUid?: string | null,
): string | null {
  if (!projects.length) {
    return null;
  }

  if (
    preferredUid &&
    projects.some((project) => project.uid === preferredUid)
  ) {
    return preferredUid;
  }

  // query 中的 projectUid 失效时，回退到列表中的第一个 project。
  return projects[0].uid;
}

export async function listProjectOptions(): Promise<ProjectOption[]> {
  const { data, error } = await projectApi.list({ limit: 100, offset: 0 });
  const projects = unwrapApiData(data, error, "Unable to load projects.");
  return projects.map(toProjectOption);
}

export async function createProject(
  input: CreateProjectInput,
): Promise<ProjectRead> {
  const { data, error } = await projectApi.create({
    name: input.name.trim(),
    description: normalizeOptionalText(input.description),
  });

  return unwrapApiData(data, error, "Unable to create project.");
}

/**
 * 异步加载 project workspace 相关数据
 * @param projectUid
 * @returns
 */
export async function loadProjectWorkspace(
  projectUid: string,
): Promise<ProjectWorkspaceViewModel> {
  // Project 首屏由多份资源共同决定，集中并行加载后再组装展示模型。
  const [
    projectResult,
    settingsResult,
    sourcesResult,
    widgetsResult,
    allSources,
  ] = await Promise.all([
    projectApi.get(projectUid),
    projectApi.getSettings(projectUid),
    projectApi.listSources(projectUid),
    projectApi.listWidgets(projectUid),
    sourceApi.list({ limit: 100, offset: 0 }),
  ]);

  const project = unwrapApiData(
    projectResult.data,
    projectResult.error,
    "Unable to load project.",
  );
  const settings = unwrapApiData(
    settingsResult.data,
    settingsResult.error,
    "Unable to load project settings.",
  );
  const linkedSources = unwrapApiData(
    sourcesResult.data,
    sourcesResult.error,
    "Unable to load linked sources.",
  );
  const widgets = unwrapApiData(
    widgetsResult.data,
    widgetsResult.error,
    "Unable to load project widgets.",
  );
  const globalSources = unwrapApiData(
    allSources.data,
    allSources.error,
    "Unable to load global sources.",
  );

  return createWorkspaceViewModel({
    globalSources,
    linkedSources,
    project,
    settings,
    widgets,
  });
}

export async function importProjectSources(
  projectUid: string,
  sourceUids: string[],
): Promise<void> {
  const { data, error } = await projectApi.bindSources(projectUid, sourceUids);
  unwrapApiData(data, error, "Unable to import sources.");
}

export async function unbindProjectSource(
  projectUid: string,
  sourceUid: string,
): Promise<void> {
  const { data, error } = await projectApi.unbindSources(projectUid, [
    sourceUid,
  ]);
  unwrapApiData(data, error, "Unable to unbind source.");
}

export async function createProjectWidget(
  projectUid: string,
  input: ProjectWidgetCreate,
): Promise<ProjectWidgetRead> {
  const { data, error } = await projectApi.createWidget(projectUid, {
    name: input.name.trim(),
    siteOrigin: input.siteOrigin.trim(),
    isEnabled: input.isEnabled,
  });

  return unwrapApiData(data, error, "Unable to create widget.");
}

export async function updateProjectWidget(
  projectUid: string,
  widgetUid: string,
  input: ProjectWidgetUpdate,
): Promise<ProjectWidgetRead> {
  const payload: ProjectWidgetUpdate = {};

  // PATCH 只提交显式传入字段，避免未修改字段被 null 覆盖。
  if ("name" in input) {
    payload.name = normalizeOptionalText(input.name);
  }

  if ("siteOrigin" in input) {
    payload.siteOrigin = normalizeOptionalText(input.siteOrigin);
  }

  if ("isEnabled" in input) {
    payload.isEnabled = input.isEnabled;
  }

  const { data, error } = await projectApi.updateWidget(
    projectUid,
    widgetUid,
    payload,
  );

  return unwrapApiData(data, error, "Unable to update widget.");
}

export async function deleteProjectWidget(
  projectUid: string,
  widgetUid: string,
): Promise<void> {
  const { data, error } = await projectApi.removeWidget(projectUid, widgetUid);
  unwrapApiData(data, error, "Unable to delete widget.");
}

/**
 * API 请求结果转换为 ProjectView 组件数据展示对象
 */
function createWorkspaceViewModel(input: {
  project: ProjectRead;
  settings: ProjectSettingsRead;
  linkedSources: SourceRead[];
  globalSources: SourceRead[];
  widgets: ProjectWidgetRead[];
}): ProjectWorkspaceViewModel {
  // 所有展示派生都留在 service，组件只负责渲染和 emit action。
  const sourceRows = input.linkedSources.map(toSourceRow);
  const widgetRows = input.widgets.map(toWidgetRow);
  const linkedUidSet = new Set(input.linkedSources.map((source) => source.uid));
  // availableSources 只包含尚未绑定的全局 Sources
  const availableSources = input.globalSources
    .filter((source) => !linkedUidSet.has(source.uid))
    .map(toSourceRow);

  return {
    project: input.project,
    settings: input.settings,
    metrics: createProjectMetrics(input.settings, sourceRows, widgetRows),
    healthItems: createProjectHealth(input.settings, sourceRows, widgetRows),
    sourceRows,
    widgetRows,
    availableSources,
  };
}

function createProjectMetrics(
  settings: ProjectSettingsRead,
  sourceRows: ProjectSourceRow[],
  widgetRows: ProjectWidgetRow[],
): ProjectMetric[] {
  const publicSourceCount = sourceRows.filter(
    (source) => source.isPublic,
  ).length;
  const enabledWidgetCount = widgetRows.filter(
    (widget) => widget.isEnabled,
  ).length;
  const modelName = settings.visitorDefaultModelProfile?.model ?? "Not set";

  return [
    {
      key: "sources",
      label: "Linked sources",
      value: String(sourceRows.length),
      foot: `${publicSourceCount} public for visitor RAG`,
      tone: publicSourceCount > 0 ? "success" : "muted",
    },
    {
      key: "widgets",
      label: "Widget deployments",
      value: String(widgetRows.length),
      foot: `${enabledWidgetCount} enabled origin${enabledWidgetCount === 1 ? "" : "s"}`,
      tone: enabledWidgetCount > 0 ? "success" : "muted",
    },
    {
      key: "model",
      label: "Provider / model",
      value: modelName,
      foot: settings.visitorDefaultProvider
        ? `${settings.visitorDefaultProvider.name} is configured`
        : "Visitor default is not set",
      tone: settings.visitorDefaultProvider ? "success" : "warning",
    },
    {
      key: "rag",
      label: "RAG status",
      value: settings.visitorRagEnabled ? "Enabled" : "Disabled",
      foot: settings.visitorRagEnabled
        ? "Project sources are used by Ask"
        : "Visitor RAG is currently off",
      tone: settings.visitorRagEnabled ? "primary" : "warning",
    },
  ];
}

function createProjectHealth(
  settings: ProjectSettingsRead,
  sourceRows: ProjectSourceRow[],
  widgetRows: ProjectWidgetRow[],
): ProjectHealthItem[] {
  const publicSourceCount = sourceRows.filter(
    (source) => source.isPublic,
  ).length;
  const privateSourceCount = sourceRows.length - publicSourceCount;
  const enabledWidget = widgetRows.find((widget) => widget.isEnabled);
  const hasModel = Boolean(
    settings.visitorDefaultProvider && settings.visitorDefaultModelProfile,
  );

  return [
    {
      key: "ask",
      title:
        sourceRows.length > 0
          ? "Project scoped Ask is available"
          : "Project scoped Ask needs sources",
      detail:
        sourceRows.length > 0
          ? "It uses this project's linked sources by default."
          : "Import at least one source before testing project RAG.",
      status: sourceRows.length > 0 ? "Configured" : "No sources",
      tone: sourceRows.length > 0 ? "success" : "warning",
    },
    {
      key: "widget",
      title: enabledWidget
        ? "Widget origin is explicitly bound"
        : "No enabled widget origin",
      detail: enabledWidget
        ? `${enabledWidget.siteOrigin} is enabled for visitor requests.`
        : "Create or enable a widget deployment before embedding the visitor widget.",
      status: enabledWidget ? "CORS ready" : "Action needed",
      tone: enabledWidget ? "success" : "warning",
    },
    {
      key: "model",
      title: hasModel
        ? "Visitor model is configured"
        : "Visitor model is not configured",
      detail: hasModel
        ? `${settings.visitorDefaultProvider?.name} / ${settings.visitorDefaultModelProfile?.model} is used by default.`
        : "Project settings should select provider and model together.",
      status: hasModel ? "Ready" : "Review",
      tone: hasModel ? "success" : "warning",
    },
    {
      key: "visibility",
      title:
        privateSourceCount > 0
          ? `${privateSourceCount} linked source${privateSourceCount === 1 ? " is" : "s are"} private`
          : "Linked sources are visitor-ready",
      detail:
        privateSourceCount > 0
          ? "Private sources remain available to Admin testing but not visitor RAG."
          : "All linked sources can be used by visitor-facing retrieval.",
      status: privateSourceCount > 0 ? "Review" : "Public",
      tone: privateSourceCount > 0 ? "warning" : "success",
    },
  ];
}

function toSourceRow(source: SourceRead): ProjectSourceRow {
  return {
    uid: source.uid,
    name: source.sourceName,
    typeLabel: sourceTypeLabel(source.sourceType),
    visibilityLabel: source.isPublic ? "Public" : "Private",
    visibilityTone: source.isPublic ? "success" : "muted",
    statusLabel: sourceStatusLabel(source.status),
    statusTone: sourceStatusTone(source.status),
    lastSyncedLabel: formatRelativeDate(source.syncedAt),
    isPublic: source.isPublic,
  };
}

function toWidgetRow(widget: ProjectWidgetRead): ProjectWidgetRow {
  return {
    uid: widget.uid,
    name: widget.name,
    siteOrigin: widget.siteOrigin,
    isEnabled: widget.isEnabled,
    enabledLabel: widget.isEnabled ? "Enabled" : "Disabled",
    enabledActionLabel: widget.isEnabled ? "Disable" : "Enable",
    createdLabel: formatDate(widget.createdAt),
    updatedLabel: formatDate(widget.updatedAt),
  };
}

function sourceTypeLabel(sourceType: SourceRead["sourceType"]): string {
  const labels: Record<SourceRead["sourceType"], string> = {
    custom_content: "Custom",
    github_repo: "GitHub",
    local_file: "Local file",
    web_crawl: "Web crawl",
  };

  return labels[sourceType];
}

function sourceStatusLabel(status: SourceRead["status"]): string {
  const labels: Record<SourceRead["status"], string> = {
    completed: "Indexed",
    failed: "Failed",
    pause_requested: "Pausing",
    paused: "Paused",
    pending: "Pending",
    processing: "Processing",
  };

  return labels[status];
}

function sourceStatusTone(
  status: SourceRead["status"],
): ProjectSourceRow["statusTone"] {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  if (status === "processing" || status === "pause_requested") {
    return "warning";
  }

  return "muted";
}

function normalizeOptionalText(
  value: string | null | undefined,
): string | null {
  if (value === undefined) {
    return null;
  }

  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatRelativeDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not synced";
  }

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.round(diffMs / 60_000));

  if (diffMinutes < 1) {
    return "just now";
  }

  if (diffMinutes < 60) {
    return `${diffMinutes} minutes ago`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} hours ago`;
  }

  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 8) {
    return `${diffDays} days ago`;
  }

  return formatDate(value);
}
