import { projectApi } from "@/console/api/projects";
import { translate as t } from "@/console/i18n";
import { unwrapApiData } from "@/console/lib/api-result";
import { normalizeOptionalText } from "@/console/lib/normalize";
import type { components } from "@/shared/api/generated/schema";

// ---- 类型定义 ----
// 从 OpenAPI schema 提取的 DTO 类型，用于 API 请求/响应
export type ProjectRead = components["schemas"]["ProjectRead"];
export type ProjectSettingsRead = components["schemas"]["ProjectSettingsRead"];
type ProjectSettingsUpdate = components["schemas"]["ProjectSettingsUpdate"];
type ProjectUpdate = components["schemas"]["ProjectUpdate"];
type SearchMode = components["schemas"]["SearchMode"];

export type VisitorThinkingLevel = "off" | "low" | "medium" | "high";

// 前端表单草稿类型：所有数值字段均为 string，兼容 v-model 绑定
export interface ProjectGeneralSettingsForm {
  name: string;
  description: string;
}

export interface ProjectVisitorSettingsForm {
  providerUid: string | null;
  modelUid: string | null;
  thinkingLevel: VisitorThinkingLevel;
  systemPrompt: string;
  ragEnabled: boolean;
  ragMode: SearchMode;
  ragTopK: string;
  rerankEnabled: boolean;
  standaloneEnabled: boolean;
  maxOutputTokens: string;
  timeout: string;
  temperature: string;
  topP: string;
  ftsK: string;
  vectorK: string;
  rerankK: string;
  maxAlternativeQueries: string;
  maxKeywords: string;
}

// 一次 load 返回的完整数据，分别用于 General 和 Visitor 面板
export interface ProjectSettingsWorkspace {
  project: ProjectRead;
  settings: ProjectSettingsRead;
}

// 字段级校验错误，key 为表单字段名，value 为错误文案
export type SettingsFieldErrors = Partial<
  Record<
    keyof ProjectGeneralSettingsForm | keyof ProjectVisitorSettingsForm,
    string
  >
>;

// ---- 数据加载与表单构造 ----
// 并行请求 project 和 settings，任一失败通过 unwrapApiData 抛出
export async function loadProjectSettings(
  projectUid: string,
): Promise<ProjectSettingsWorkspace> {
  const [projectResult, settingsResult] = await Promise.all([
    projectApi.get(projectUid),
    projectApi.getSettings(projectUid),
  ]);

  return {
    project: unwrapApiData(
      projectResult.data,
      projectResult.error,
      t("project.service.errors.loadProject"),
    ),
    settings: unwrapApiData(
      settingsResult.data,
      settingsResult.error,
      t("project.service.errors.loadSettings"),
    ),
  };
}

// API 响应 → 表单草稿：数值字段统一 String() 化，可选字段 ?? 兜底
export function createGeneralSettingsForm(
  project: ProjectRead,
): ProjectGeneralSettingsForm {
  return {
    name: project.name,
    description: project.description ?? "",
  };
}

export function createVisitorSettingsForm(
  settings: ProjectSettingsRead,
): ProjectVisitorSettingsForm {
  const thinking = settings.visitorThinking;
  return {
    providerUid: settings.visitorDefaultProvider?.uid ?? null,
    modelUid: settings.visitorDefaultModelProfile?.uid ?? null,
    thinkingLevel:
      thinking === "low" || thinking === "medium" || thinking === "high"
        ? thinking
        : "off",
    systemPrompt: settings.visitorSystemPrompt ?? "",
    ragEnabled: settings.visitorRagEnabled,
    ragMode: settings.ragMode,
    ragTopK: String(settings.ragTopK),
    rerankEnabled: settings.ragRerankEnabled,
    standaloneEnabled: settings.ragStandaloneEnabled,
    maxOutputTokens: String(settings.visitorMaxOutputTokens),
    timeout: String(settings.visitorTimeout),
    temperature: String(settings.visitorTemperature),
    topP: String(settings.visitorTopP),
    ftsK: String(settings.ragFtsK),
    vectorK: String(settings.ragVectorK),
    rerankK: String(settings.ragRerankK),
    maxAlternativeQueries: String(settings.ragMaxAlternativeQueries),
    maxKeywords: String(settings.ragMaxKeywords),
  };
}

export function validateGeneralSettings(
  form: ProjectGeneralSettingsForm,
): SettingsFieldErrors {
  return form.name.trim()
    ? {}
    : { name: t("common.errors.projectNameRequired") };
}

export function validateVisitorSettings(
  form: ProjectVisitorSettingsForm,
): SettingsFieldErrors {
  const errors: SettingsFieldErrors = {};
  validateNumber(errors, "maxOutputTokens", form.maxOutputTokens, {
    min: 1,
    integer: true,
  });
  validateNumber(errors, "timeout", form.timeout, { minExclusive: 0 });
  validateNumber(errors, "temperature", form.temperature, { min: 0 });
  validateNumber(errors, "topP", form.topP, { min: 0, max: 1 });
  validateNumber(errors, "ragTopK", form.ragTopK, { min: 1, integer: true });
  validateNumber(errors, "ftsK", form.ftsK, { min: 0, integer: true });
  validateNumber(errors, "vectorK", form.vectorK, { min: 0, integer: true });
  validateNumber(errors, "rerankK", form.rerankK, { min: 0, integer: true });
  validateNumber(errors, "maxAlternativeQueries", form.maxAlternativeQueries, {
    min: 0,
    max: 10,
    integer: true,
  });
  validateNumber(errors, "maxKeywords", form.maxKeywords, {
    min: 0,
    max: 20,
    integer: true,
  });
  return errors;
}

// 对比 form 与 baseline，只将变更字段放入 API payload，避免全量覆盖
export async function updateProjectGeneral(
  projectUid: string,
  form: ProjectGeneralSettingsForm,
  baseline: ProjectGeneralSettingsForm,
): Promise<ProjectRead> {
  const payload: ProjectUpdate = {};
  const name = form.name.trim();
  const baselineName = baseline.name.trim();
  const description = normalizeOptionalText(form.description);
  const baselineDescription = normalizeOptionalText(baseline.description);
  if (name !== baselineName) payload.name = name;
  if (description !== baselineDescription) payload.description = description;

  const { data, error } = await projectApi.update(projectUid, payload);
  return unwrapApiData(data, error, t("project.settings.errors.saveGeneral"));
}

// 逐字段对比 form 与 baseline，通过 assignChanged 将变更写入 payload
// provider/model 切换时同时发送两个 uid，其余字段独立比较
export async function updateProjectVisitorSettings(
  projectUid: string,
  form: ProjectVisitorSettingsForm,
  baseline: ProjectVisitorSettingsForm,
): Promise<ProjectSettingsRead> {
  const payload: ProjectSettingsUpdate = {};
  assignChanged(
    payload,
    "visitorRagEnabled",
    form.ragEnabled,
    baseline.ragEnabled,
  );
  assignChanged(
    payload,
    "visitorSystemPrompt",
    normalizeOptionalText(form.systemPrompt),
    normalizeOptionalText(baseline.systemPrompt),
  );
  assignChanged(
    payload,
    "visitorThinking",
    toThinking(form.thinkingLevel),
    toThinking(baseline.thinkingLevel),
  );
  assignChanged(payload, "ragMode", form.ragMode, baseline.ragMode);
  assignChanged(
    payload,
    "ragTopK",
    Number(form.ragTopK),
    Number(baseline.ragTopK),
  );
  assignChanged(
    payload,
    "ragRerankEnabled",
    form.rerankEnabled,
    baseline.rerankEnabled,
  );
  assignChanged(
    payload,
    "ragStandaloneEnabled",
    form.standaloneEnabled,
    baseline.standaloneEnabled,
  );
  assignChanged(
    payload,
    "visitorMaxOutputTokens",
    Number(form.maxOutputTokens),
    Number(baseline.maxOutputTokens),
  );
  assignChanged(
    payload,
    "visitorTimeout",
    Number(form.timeout),
    Number(baseline.timeout),
  );
  assignChanged(
    payload,
    "visitorTemperature",
    Number(form.temperature),
    Number(baseline.temperature),
  );
  assignChanged(
    payload,
    "visitorTopP",
    Number(form.topP),
    Number(baseline.topP),
  );
  assignChanged(payload, "ragFtsK", Number(form.ftsK), Number(baseline.ftsK));
  assignChanged(
    payload,
    "ragVectorK",
    Number(form.vectorK),
    Number(baseline.vectorK),
  );
  assignChanged(
    payload,
    "ragRerankK",
    Number(form.rerankK),
    Number(baseline.rerankK),
  );
  assignChanged(
    payload,
    "ragMaxAlternativeQueries",
    Number(form.maxAlternativeQueries),
    Number(baseline.maxAlternativeQueries),
  );
  assignChanged(
    payload,
    "ragMaxKeywords",
    Number(form.maxKeywords),
    Number(baseline.maxKeywords),
  );

  if (
    form.providerUid !== baseline.providerUid ||
    form.modelUid !== baseline.modelUid
  ) {
    payload.visitorDefaultProviderUid = form.providerUid;
    payload.visitorDefaultModelProfileUid = form.modelUid;
  }

  const { data, error } = await projectApi.updateSettings(projectUid, payload);
  return unwrapApiData(data, error, t("project.settings.errors.saveVisitor"));
}

export async function deleteProject(projectUid: string): Promise<void> {
  const { data, error } = await projectApi.remove(projectUid);
  unwrapApiData(data, error, t("project.settings.errors.deleteProject"));
}

// ---- 内部辅助 ----
// "off" → false（API 用 false 表示关闭思考），其余透传
function toThinking(
  level: VisitorThinkingLevel,
): false | "low" | "medium" | "high" {
  return level === "off" ? false : level;
}

// 仅当 value !== baseline 时才写入 payload，实现增量更新
function assignChanged<K extends keyof ProjectSettingsUpdate>(
  payload: ProjectSettingsUpdate,
  key: K,
  value: ProjectSettingsUpdate[K],
  baseline: ProjectSettingsUpdate[K],
): void {
  if (value !== baseline) payload[key] = value;
}

// 数值字段通用校验：空值/NaN 直接判无效，再按规则检查整数/范围
function validateNumber(
  errors: SettingsFieldErrors,
  key: keyof ProjectVisitorSettingsForm,
  rawValue: string,
  rules: {
    integer?: boolean;
    min?: number;
    minExclusive?: number;
    max?: number;
  },
): void {
  const value = Number(rawValue);
  const invalid =
    rawValue.trim() === "" ||
    !Number.isFinite(value) ||
    (rules.integer && !Number.isInteger(value)) ||
    (rules.min !== undefined && value < rules.min) ||
    (rules.minExclusive !== undefined && value <= rules.minExclusive) ||
    (rules.max !== undefined && value > rules.max);
  if (invalid) errors[key] = t("project.settings.errors.invalidValue");
}
