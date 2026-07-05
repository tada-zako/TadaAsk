import { providerModelApi } from "@/console/api/provider-model";
import type {
  ModelProfileCreatePayload,
  ModelProfileRead,
  ModelProfileUpdatePayload,
  ProviderRead,
  ProviderUpdatePayload,
  ProviderWithModelsRead,
} from "@/console/api/provider-model";
import { translate as t } from "@/console/i18n";
import { unwrapApiData } from "@/console/lib/api-result";
import { normalizeOptionalText } from "@/console/lib/normalize";

// === ViewModel 类型：供 UI 层消费 ===

export type ProviderTone = "official" | "custom";
export type ProviderModelStatusTone = "success" | "muted";

export interface ProviderRowViewModel {
  uid: string;
  name: string;
  displayName: string;
  initial: string;
  baseUrl: string | null;
  isEnabled: boolean;
  isCustom: boolean;
  hasApiKey: boolean;
  badgeLabel: string;
  statusLabel: string;
  statusTone: ProviderModelStatusTone;
  description: string;
  provider: ProviderWithModelsRead;
}

export interface AvailableProviderViewModel extends ProviderRowViewModel {
  kind: "provider";
}

export interface CustomProviderEntryViewModel {
  kind: "custom-entry";
  displayName: string;
  initial: string;
  badgeLabel: string;
  description: string;
}

export type AvailableProviderEntryViewModel =
  AvailableProviderViewModel | CustomProviderEntryViewModel;

export interface ModelRowViewModel {
  uid: string;
  model: string;
  contextWindowTokens: number | null;
  maxOutputTokens: number | null;
  supportsStream: boolean;
  supportsStructured: boolean;
  isEnabled: boolean;
  statusLabel: string;
  statusTone: ProviderModelStatusTone;
  description: string;
}

export interface ModelProviderGroupViewModel {
  providerUid: string;
  providerName: string;
  providerDisplayName: string;
  initial: string;
  baseUrl: string | null;
  isCustom: boolean;
  badgeLabel: string;
  statusLabel: string;
  statusTone: ProviderModelStatusTone;
  description: string;
  models: ModelRowViewModel[];
}

export interface ProviderModelWorkspaceViewModel {
  savedProviders: ProviderRowViewModel[];
  availableProviders: AvailableProviderEntryViewModel[];
  officialModelGroups: ModelProviderGroupViewModel[];
  customModelGroups: ModelProviderGroupViewModel[];
}

// === 输入 DTO 类型 ===

export interface CreateCustomProviderInput {
  name: string;
  baseUrl: string;
  apiKey: string;
  modelNames: string[];
}

export interface ConnectOfficialProviderInput {
  apiKey: string;
}

export interface UpdateProviderInput {
  name?: string;
  baseUrl?: string;
  apiKey?: string;
  isEnabled?: boolean;
}

export interface CreateCustomModelInput {
  model: string;
  contextWindowTokens?: number | null;
  maxOutputTokens?: number | null;
  isEnabled: boolean;
}

export interface UpdateCustomModelInput {
  model?: string;
  contextWindowTokens?: number | null;
  maxOutputTokens?: number | null;
  isEnabled?: boolean;
}

// API 错误信息映射
export const providerModelErrors = {
  connectProvider: "providerModel.service.errors.connectProvider",
  createModel: "providerModel.service.errors.createModel",
  createProvider: "providerModel.service.errors.createProvider",
  deleteModel: "providerModel.service.errors.deleteModel",
  deleteProvider: "providerModel.service.errors.deleteProvider",
  loadEnabledWorkspace: "providerModel.service.errors.loadEnabledWorkspace",
  loadWorkspace: "providerModel.service.errors.loadWorkspace",
  updateModel: "providerModel.service.errors.updateModel",
  updateProvider: "providerModel.service.errors.updateProvider",
};

// === 数据加载 ===

export function providerModelError(
  key: keyof typeof providerModelErrors,
): string {
  return t(providerModelErrors[key]);
}

export async function listProvidersWithModels(): Promise<
  ProviderWithModelsRead[]
> {
  const { data, error } = await providerModelApi.listProvidersWithModels();
  return unwrapApiData(data, error, providerModelError("loadWorkspace"));
}

export async function listEnabledProvidersWithModels(): Promise<
  ProviderWithModelsRead[]
> {
  const { data, error } =
    await providerModelApi.listEnabledProvidersWithModels();
  return unwrapApiData(data, error, providerModelError("loadEnabledWorkspace"));
}

// === Provider CRUD ===

export async function connectOfficialProvider(
  providerUid: string,
  input: ConnectOfficialProviderInput,
): Promise<ProviderRead> {
  const { data, error } = await providerModelApi.updateProvider(providerUid, {
    apiKey: input.apiKey.trim(),
    isEnabled: true,
  });

  return unwrapApiData(data, error, providerModelError("connectProvider"));
}

export async function createCustomProvider(
  input: CreateCustomProviderInput,
): Promise<ProviderWithModelsRead> {
  const modelProfiles = normalizeModelNames(input.modelNames).map((model) =>
    createModelProfilePayload({ model, isEnabled: true }),
  );

  const { data, error } = await providerModelApi.createProvider({
    name: input.name.trim(),
    baseUrl: normalizeOptionalText(input.baseUrl),
    apiKey: input.apiKey.trim(),
    isEnabled: true,
    isCustom: true,
    modelProfiles,
  });

  return unwrapApiData(data, error, providerModelError("createProvider"));
}

export async function updateProvider(
  providerUid: string,
  input: UpdateProviderInput,
): Promise<ProviderRead> {
  const payload: ProviderUpdatePayload = {};

  if ("name" in input && input.name !== undefined) {
    payload.name = input.name.trim();
  }

  if ("baseUrl" in input && input.baseUrl !== undefined) {
    payload.baseUrl = normalizeOptionalText(input.baseUrl);
  }

  if ("apiKey" in input && input.apiKey !== undefined) {
    const apiKey = input.apiKey.trim();
    if (apiKey) {
      payload.apiKey = apiKey;
    }
  }

  if ("isEnabled" in input && input.isEnabled !== undefined) {
    payload.isEnabled = input.isEnabled;
  }

  const { data, error } = await providerModelApi.updateProvider(
    providerUid,
    payload,
  );
  return unwrapApiData(data, error, providerModelError("updateProvider"));
}

export async function deleteProvider(providerUid: string): Promise<void> {
  const { data, error } = await providerModelApi.deleteProvider(providerUid);
  unwrapApiData(data, error, providerModelError("deleteProvider"));
}

// === Model CRUD ===

export async function createCustomModel(
  providerUid: string,
  input: CreateCustomModelInput,
): Promise<ModelProfileRead> {
  const { data, error } = await providerModelApi.createModel(
    providerUid,
    createModelProfilePayload(input),
  );

  return unwrapApiData(data, error, providerModelError("createModel"));
}

export async function updateModel(
  providerUid: string,
  modelUid: string,
  input: UpdateCustomModelInput,
): Promise<ModelProfileRead> {
  const payload: ModelProfileUpdatePayload = {};

  if ("model" in input && input.model !== undefined) {
    payload.model = input.model.trim();
  }

  if ("contextWindowTokens" in input) {
    payload.contextWindowTokens = normalizeTokenLimit(
      input.contextWindowTokens,
    );
  }

  if ("maxOutputTokens" in input) {
    payload.maxOutputTokens = normalizeTokenLimit(input.maxOutputTokens);
  }

  if ("isEnabled" in input && input.isEnabled !== undefined) {
    payload.isEnabled = input.isEnabled;
  }

  const { data, error } = await providerModelApi.updateModel(
    providerUid,
    modelUid,
    payload,
  );
  return unwrapApiData(data, error, providerModelError("updateModel"));
}

export async function deleteModel(
  providerUid: string,
  modelUid: string,
): Promise<void> {
  const { data, error } = await providerModelApi.deleteModel(
    providerUid,
    modelUid,
  );
  unwrapApiData(data, error, providerModelError("deleteModel"));
}

// === Workspace 工厂：将后端数据组装为 ViewModel 树 ===

export function createProviderModelWorkspace(
  providers: ProviderWithModelsRead[],
): ProviderModelWorkspaceViewModel {
  const savedProviders = providers
    .filter(isSavedProvider)
    .map(toProviderRow)
    .sort(compareProviderRows);
  const availableCatalogProviders = providers
    .filter((provider) => !provider.isCustom && !hasApiKey(provider))
    .map(toAvailableProviderRow);

  const modelGroups = savedProviders.map((provider) =>
    toModelProviderGroup(provider.provider),
  );

  return {
    savedProviders,
    availableProviders: [
      ...availableCatalogProviders,
      {
        kind: "custom-entry",
        displayName: t("providerModel.providers.customEntryName"),
        initial: "+",
        badgeLabel: t("providerModel.badges.custom"),
        description: t("providerModel.providers.openAiCompatibleEndpoint"),
      },
    ],
    officialModelGroups: modelGroups.filter((group) => !group.isCustom),
    customModelGroups: modelGroups.filter((group) => group.isCustom),
  };
}

// === 内部映射：ProviderWithModelsRead → ViewModel ===

function toAvailableProviderRow(
  provider: ProviderWithModelsRead,
): AvailableProviderViewModel {
  return {
    ...toProviderRow(provider),
    kind: "provider",
    badgeLabel: t("providerModel.badges.official"),
    description: t("providerModel.providers.officialCatalogProvider"),
  };
}

function toProviderRow(provider: ProviderWithModelsRead): ProviderRowViewModel {
  const displayName = formatProviderDisplayName(provider.name);
  const isCustom = provider.isCustom;

  return {
    uid: provider.uid,
    name: provider.name,
    displayName,
    initial: providerInitial(displayName),
    baseUrl: provider.baseUrl ?? null,
    isEnabled: provider.isEnabled,
    isCustom,
    hasApiKey: hasApiKey(provider),
    badgeLabel: isCustom
      ? t("providerModel.badges.custom")
      : t("providerModel.badges.apiKey"),
    statusLabel: providerStatusLabel(provider.isEnabled),
    statusTone: providerStatusTone(provider.isEnabled),
    description:
      provider.baseUrl ??
      (isCustom ? t("providerModel.providers.customProvider") : ""),
    provider,
  };
}

function toModelProviderGroup(
  provider: ProviderWithModelsRead,
): ModelProviderGroupViewModel {
  const displayName = formatProviderDisplayName(provider.name);
  const isCustom = provider.isCustom;

  return {
    providerUid: provider.uid,
    providerName: provider.name,
    providerDisplayName: displayName,
    initial: providerInitial(displayName),
    baseUrl: provider.baseUrl ?? null,
    isCustom,
    badgeLabel: isCustom
      ? t("providerModel.badges.custom")
      : t("providerModel.badges.official"),
    statusLabel: providerStatusLabel(provider.isEnabled),
    statusTone: providerStatusTone(provider.isEnabled),
    description: isCustom
      ? t("providerModel.models.customProviderDescription")
      : t("providerModel.models.officialProviderDescription"),
    models: (provider.modelProfiles ?? []).map((model) =>
      toModelRow(model, isCustom),
    ),
  };
}

function toModelRow(
  model: ModelProfileRead,
  isCustomProvider: boolean,
): ModelRowViewModel {
  return {
    uid: model.uid,
    model: model.model,
    contextWindowTokens: model.contextWindowTokens ?? null,
    maxOutputTokens: model.maxOutputTokens ?? null,
    supportsStream: model.supportsStream,
    supportsStructured: model.supportsStructured,
    isEnabled: model.isEnabled,
    statusLabel: providerStatusLabel(model.isEnabled),
    statusTone: providerStatusTone(model.isEnabled),
    description: isCustomProvider
      ? modelTokenDescription(model)
      : modelCapabilityDescription(model),
  };
}

function createModelProfilePayload(
  input: CreateCustomModelInput,
): ModelProfileCreatePayload {
  return {
    model: input.model.trim(),
    contextWindowTokens: normalizeTokenLimit(input.contextWindowTokens),
    maxOutputTokens: normalizeTokenLimit(input.maxOutputTokens),
    supportsStream: true,
    supportsStructured: true,
    isEnabled: input.isEnabled,
  };
}

function normalizeTokenLimit(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }

  return value > 0 ? Math.trunc(value) : null;
}

function normalizeModelNames(modelNames: string[]): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const modelName of modelNames) {
    const model = modelName.trim();
    if (!model || seen.has(model)) {
      continue;
    }

    seen.add(model);
    normalized.push(model);
  }

  return normalized;
}

function isSavedProvider(provider: ProviderWithModelsRead): boolean {
  return provider.isCustom || hasApiKey(provider);
}

/** 辅助 saved providers 排序；official provider 位于 custom provider 之前 */
function compareProviderRows(
  left: ProviderRowViewModel,
  right: ProviderRowViewModel,
): number {
  if (left.isCustom !== right.isCustom) {
    return left.isCustom ? 1 : -1;
  }

  return 0;
}

// === 内部工具函数 ===

function hasApiKey(provider: ProviderWithModelsRead | ProviderRead): boolean {
  return Boolean(provider.encryptedApiKey);
}

function modelCapabilityDescription(model: ModelProfileRead): string {
  if (model.supportsStream && model.supportsStructured) {
    return t("providerModel.models.capabilities.streamAndStructured");
  }

  if (model.supportsStream) {
    return t("providerModel.models.capabilities.stream");
  }

  if (model.supportsStructured) {
    return t("providerModel.models.capabilities.structured");
  }

  return t("providerModel.models.capabilities.catalog");
}

function modelTokenDescription(model: ModelProfileRead): string {
  const context = formatTokenCount(model.contextWindowTokens ?? null);
  const output = formatTokenCount(model.maxOutputTokens ?? null);

  if (context && output) {
    return t("providerModel.models.tokens.contextAndOutput", {
      context,
      output,
    });
  }

  if (context) {
    return t("providerModel.models.tokens.contextOnly", { context });
  }

  if (output) {
    return t("providerModel.models.tokens.outputOnly", { output });
  }

  return t("providerModel.models.tokens.providerDefaults");
}

function providerStatusLabel(isEnabled: boolean): string {
  return isEnabled
    ? t("providerModel.status.enabled")
    : t("providerModel.status.disabled");
}

function providerStatusTone(isEnabled: boolean): ProviderModelStatusTone {
  return isEnabled ? "success" : "muted";
}

function formatTokenCount(value: number | null): string | null {
  if (!value) {
    return null;
  }

  return new Intl.NumberFormat("en-US").format(value);
}

function formatProviderDisplayName(name: string): string {
  const normalized = name.trim().toLowerCase();
  const specialNames: Record<string, string> = {
    anthropic: "Anthropic",
    google: "Google AI",
    "google-ai": "Google AI",
    googleai: "Google AI",
    ollama: "Ollama",
    openai: "OpenAI",
  };

  if (specialNames[normalized]) {
    return specialNames[normalized];
  }

  return name
    .split(/([\s_-]+)/)
    .map((part) =>
      /^[\s_-]+$/.test(part)
        ? " "
        : part.charAt(0).toUpperCase() + part.slice(1),
    )
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}

function providerInitial(displayName: string): string {
  return displayName.match(/[a-z0-9]/i)?.[0]?.toUpperCase() ?? "*";
}
